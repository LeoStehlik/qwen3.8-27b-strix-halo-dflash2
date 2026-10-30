# Benchmarks and validation record

All results below were measured on the reference machine on 2026-10-30. They
are engineering probes, not vendor-neutral model benchmarks. Results are
sensitive to prompt shape, reasoning length, sampling, cache state, driver,
runtime commit and DFlash acceptance.

## Environment

| Component | Value |
|---|---|
| CPU / GPU | Ryzen AI Max+ 395 / Radeon 8060S Strix Halo |
| Installed memory | 128 GB unified |
| OS | Ubuntu 26.04.1, kernel 7.0.0-42-generic |
| Host RADV | Mesa 26.0.8 |
| Runtime RADV | bundled Mesa 26.2.4 |
| llama.cpp | build 11001, commit `629d2f7b4` |
| Original context / slots | 245,760 / 1 |
| Target KV | Q8_0 K and V |
| Batch / ubatch | 2048 / 2048 |
| Threads | 16 / 16 batch |

## Artifact verification

All four model files passed `sha256sum --check models/SHA256SUMS`. Exact sizes,
sources, revisions and hashes are recorded in [INSTALL.md](INSTALL.md).

## Router and model loading

The following request sequence completed successfully:

```text
Q4 request -> Q5 request -> Q4 request
```

The router evicted the previous resident target at each change, loaded the
requested target, and retained the same API endpoint, vision configuration and
DFlash2 drafter.

## DFlash2 width sweep

The repeatable probe is `dflash-width-bench.py`. Each cell is the mean of two
192-token generations using two technical prose prompts, temperature 0.2,
top-p 0.95, top-k 20, min-p 0 and seed 12345.

To reproduce one row, change only `spec-draft-n-max` in `models.ini`, restart
the service, wait for Q4 to finish loading, then run:

```bash
./dflash-width-bench.py qwen3.8-27b-q4-fast --label width-N
./dflash-width-bench.py qwen3.8-27b-q5-quality --label width-N
```

Restore width 4 and restart after the sweep.

| Width | Q4 tok/s | Q4 accepted / drafted | Q5 tok/s | Q5 accepted / drafted |
|---:|---:|---:|---:|---:|
| 2 | 21.61 | 63.77% | 18.59 | 62.72% |
| **4** | **24.87** | **48.26%** | **20.73** | **47.42%** |
| 6 | 20.36 | 32.85% | 17.23 | 32.68% |

Acceptance percentage alone does not determine throughput. Width 4 verifies
more useful candidates per speculative step than width 2, while width 6 spends
too much work on candidates that the target rejects.

Earlier general short-prose probes observed approximately 24.5 tok/s on Q4 and
17.6 tok/s on Q5, with Q4 varying from roughly 23 to 30.7 tok/s across prompts.
Those numbers are retained to show workload variance; the controlled width
sweep is the better like-for-like comparison.

After enabling reasoning preservation, a temperature-0.2 weather-tool smoke
request completed with a valid `get_weather` call, valid JSON arguments,
26.64 tok/s and 79.17% draft acceptance for that short response.

## One versus two versus four slots

Four simultaneous clients each sent a distinct cold prompt containing 9,263
input tokens and requested 64 output tokens. The Q4 target, DFlash2 width 4,
Q8_0 target KV, batch/ubatch 2,048 and all other inference settings were held
constant. Labels changed between configurations to prevent prompt-cache reuse.

| Slots | First result | Mean | p50 | p95 | Last / wall | Delivered tok/s | Mean reported decode | Draft acceptance |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **1** | **25.06 s** | **62.89 s** | **62.81 s** | **97.05 s** | **100.88 s** | **2.54** | **18.83 tok/s** | 35.37% |
| 2 | 52.71 s | 86.43 s | 92.12 s | 108.62 s | 108.79 s | 2.35 | 3.61 tok/s | 33.97% |
| 4 | 102.56 s | 105.00 s | 105.16 s | 107.02 s | 107.11 s | 2.39 | 2.56 tok/s | 33.73% |

One slot won every user-facing latency measure and the total-drain comparison.
Two slots roughly doubled time to first result; four made all clients wait for
almost the full batch. Production therefore uses one 245,760-token slot. This
is an empirical conclusion for this particular Vulkan/DFlash2 build and
workload, not a general statement about llama.cpp or continuous batching.

The same conclusion appeared more strongly with real OpenClaw-sized traffic.
Two simultaneous cold prompts of roughly 112K--120K tokens reduced prefill to
about 145 tok/s for the older request and took approximately 14 minutes to
finish it. A short generation sharing the other slot reported only 0.46 tok/s.
The original one-slot cold-prefill traces were roughly 310 tok/s. Large cold
OpenClaw prefixes still take minutes even with one slot; reducing, prewarming,
or reusing that prefix is required for sub-minute interaction.

Reproduce the controlled test with `concurrency-bench.py`, changing both the
server slot configuration and `--label` for every run:

```bash
./concurrency-bench.py qwen3.8-27b-q4-fast --concurrency 4 \
  --pad-words 8192 --max-tokens 64 --label slots-N
```

## Coalescing deployment check

Q4, DFlash2 width 4 and the F16 vision projector loaded with full GPU offload.

During the temporary two-slot test, two concurrent byte-identical 32-token
requests were sent while OpenClaw was cold-prefilling an unrelated
approximately 112K-token request in the other slot. Both clients received the
same complete response. Coalescer deltas were:

```text
upstream requests: 1
followers:         1
upstream errors:   0
```

This proves the production single-flight path, including real GPU contention.
It is not a decode-speed baseline: the small generation took 81.61 seconds and
reported only 0.46 tok/s while sharing execution with the large prefill. That
reveals a latency-fairness problem with 2,048-token physical prefill batches.
The planned 512/1,024/2,048 ubatch sweep must therefore record small-request
latency during a concurrent long prefill, not merely aggregate prefill speed.

## Tool sampling probe

`tool-temperature-test.py` defines three tools and five cases:

- Explicit weather request
- Implicit umbrella/weather request
- Exact calculation request
- Current-information web-search request
- A control that explicitly forbids tool use

Each temperature accumulated 15 exploratory outcomes: the initial five-case
pass plus repeated implicit-weather and no-tool controls.

| Temperature | Valid outcomes |
|---:|---:|
| 0.0 | 15/15 |
| 0.2 | 15/15 |
| 0.3 | 15/15 |
| 0.7 | 15/15 |
| 1.0 | 14/15 |

The one failure at 1.0 took a much longer reasoning path, hit the output length
limit and emitted malformed/truncated tool arguments. Five later repetitions
at 1.0 passed, so this does not prove that 1.0 cannot call tools. It shows no
local tool-use benefit from the higher variance. Temperature 0.2 is therefore
the conservative OpenClaw starting point, with 0.3 as a reasonable alternative.

This test is intentionally small. The authoritative agent evaluation will use
OpenClaw's real system prompt, tools, multi-turn history and compaction.

Run the complete exploratory probe with:

```bash
./tool-temperature-test.py --case all --trials 1
./tool-temperature-test.py --case implicit --trials 5
./tool-temperature-test.py --case control --trials 5
```

## Vision validation

The matching F16 projector loaded successfully with DFlash2 and both target
presets. A natural cat image was correctly identified. The repository also
contains a deterministic generated-card test that checks basic geometry and
colour recognition without redistributing a third-party image.

In the repeat run, Q4 accurately described the card's white field, red
upper-left shape, blue upper-right shape and yellow bottom band, but
unsupportedly labelled it as Rotterdam's flag. Treat this as a feature-extraction
pass and a semantic-grounding warning, not a full vision-quality pass.

This is a functional smoke test only. The planned suite covers UI screenshots,
small-text OCR, charts, photographs and multiple images per turn while sweeping
the image-token floor.

## Not yet measured

- Prefill at 8K, 32K and 128K across ubatch sizes
- DFlash `p_split` and `p_min`
- F16 versus Q8 draft KV for throughput
- Hard vision accuracy and latency
- Real OpenClaw agent/tool/compaction behaviour
- Quality delta between Q4 and Q5 on representative tasks

Do not present planned tests as completed results.
