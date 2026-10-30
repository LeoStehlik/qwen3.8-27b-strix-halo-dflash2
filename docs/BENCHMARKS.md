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

## Later live streaming and tool-loop trace

A later sanitized OpenClaw/Discord run exercised preview streaming and several
consecutive model calls at approximately 43K--50K populated context. The API
returned HTTP 200 when each streaming request opened; the backend continued
generating while the client was able to update its preview. The calls were a
tool loop, not repeated full prefills: longest-common-prefix similarity was
typically 97--99.9% and some follow-ups processed only tens or hundreds of new
prompt tokens.

Representative completed calls were:

| Output tokens | Decode | DFlash acceptance | Mean accepted length |
|---:|---:|---:|---:|
| 1,160 | 20.42 tok/s | 60.04% | 3.40 |
| 169 | 17.25 tok/s | 58.33% | 3.33 |
| 134 | 22.14 tok/s | 83.06% | 4.32 |
| 165 | 20.61 tok/s | 62.77% | 3.51 |
| 82 | 24.38 tok/s | 94.12% | 4.76 |
| 405 | 19.99 tok/s | 50.00% | 3.00 |
| 2,668 | 17.97 tok/s | 49.61% | 2.98 |

The 1,160-token call needed 7.11 seconds for 1,803 new prompt tokens and 56.77
seconds for generation. The 2,668-token call needed 13.76 seconds for 3,256
new prompt tokens and 148.43 seconds for generation. This confirms two things:

1. Warm prefix reuse keeps prompt work manageable.
2. Long responses remain output-bound even after preview streaming makes them
   feel alive.

During the 2,668-token call, GPU utilisation samples were mostly 62--74%, GPU
clock was approximately 2.0--2.3 GHz against a reported 2.9 GHz top state, and
temperature was about 62 C. The run was not thermally throttled. Power policy,
host scheduling and dispatch gaps are therefore valid A/B targets.

High acceptance did not by itself produce 30 tok/s: the short 94.12%-acceptance
call reached 24.38 tok/s. The path to 30 tok/s must also improve verification
and scheduling efficiency or use a better target-specific drafter.

## Persistent slot checkpoint candidate

The live host also validated a local checkpoint-persistence backport based on
llama.cpp commit `a82001bd3`. This candidate preserves the hybrid model's
recurrent context state when a server slot is saved and restored. It is not yet
the portable runtime downloaded by this repository's installer.

The sanitized live checkpoint contained 35,074 saved tokens and five recurrent
checkpoints. Its file size was 2,373,324,072 bytes, with mode `0600`. Saving
took 399.65 ms and restoring took 327.73 ms. The launcher restored slot 0 before
starting the public proxy, preventing an incoming remote request from racing
the restore.

The first measured request after restart reused 26,926 cached tokens, processed
8,326 new prompt tokens in 24.13 seconds, generated 502 tokens at 18.76 tok/s
and completed in 50.84 seconds. The following steady-state request reused
34,221 tokens, processed 1,660 new tokens in 5.67 seconds, generated 947 tokens
at 21.09 tok/s and completed in 50.53 seconds.

This proves useful restart recovery, but not indefinite cache durability across
model, template or runtime changes. Treat checkpoint files as runtime-specific
cache artifacts, keep restrictive permissions, and regenerate them after a
material model or chat-template change.

## Live OpenClaw cold and warm trace

Francis ran a real OpenClaw tool session against the production Q4 preset. The
first assembled request contained 152,781 prompt tokens. Cold prompt processing
took 545.25 seconds at 280.20 tok/s; generating 321 tokens took another 26.44
seconds at 12.10 tok/s. Total server time was 571.69 seconds, or 9m32s.

The next ten tool-loop turns retained 96.6--99% prefix similarity. Their median
total time was 47.5 seconds, mean was 53.6 seconds, eight finished inside 60
seconds, and all finished inside 120 seconds. A later independent approximately
150K-token request missed the live prefix and queued another request behind it.

The inference stack therefore delivers usable warm-session latency, but cannot
make OpenClaw's 150K-token cold hydration interactive. The sanitized per-turn
record and OpenClaw action items are in
[OPENCLAW-LIVE-TRACE.md](OPENCLAW-LIVE-TRACE.md).

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
- Vulkan FA Wave32 enabled versus disabled
- GPU/CPU performance policy, polling, priority and physical-core affinity
- DFlash widths 3/4/5 on representative OpenClaw-like outputs
- Q4 versus Q8 versus F16/BF16 draft weights
- F16 versus Q8 draft KV for throughput
- Q8_0 versus Q4_0 versus IQ4_NL target KV at populated context
- Hard vision accuracy and latency
- OpenClaw compaction behaviour
- Quality delta between Q4 and Q5 on representative tasks

`p_split` and `p_min` were removed from the DFlash2 plan after source
inspection showed that the selector-lattice path does not consume them as
general acceptance controls.

Do not present planned tests as completed results.
