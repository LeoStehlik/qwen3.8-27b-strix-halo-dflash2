# Return to Qwen3.8 and dense-prefill investigation — 2026-11-05

Qwen3.8-27B Q4 + DFlash2 is serving again on the Strix Halo GPU. The user retired
Qwen3.6 from daily OpenClaw use after real-task failures despite its approximately
1,047 tok/s prefill result. The [setback record](https://github.com/LeoStehlik/qwen3.6-35b-a3b-strix-halo/blob/main/docs/OPERATIONAL-SETBACK.md)
keeps observations separate from unproven causes. Qwen3.6 weights, builds and
its frozen tag remain available offline.

## Verified deployment

The service uses the existing checkpoint-persistence candidate at
`a82001bd382ea54481603be113ced229a21db8d2`, with bundled Mesa RADV 26.2.4. Installed
llama/Vulkan libraries match the preserved source build by SHA-256. This is
llama.cpp Vulkan, not vLLM/ROCm. The former CPU-loaded child was replaced during
the authorized service restart; the live child now owns the AMD render device,
GPU allocations and compute activity. No model download was necessary.

- Target: existing `Qwen3.8-27B-UD-Q4_K_XL.gguf`; this is a mixed-quant file.
- Draft: existing `Qwen3.8-27B-DFlash2-Q4_K_M.gguf`, width 4, default F16 draft KV.
- Target KV: Q8_0; context 245,760; one slot; batch/ubatch 2048/2048.
- Vision projector and 24 GiB RAM prompt cache retained; checkpoint support retained.
- Q4 loads at startup; Q5 remains available on demand, one resident target at a time.
- The old October 30 conversation snapshot remains on disk, but its automatic
  startup restore is disabled. Start with a fresh slot instead of that old history.
- Completion, exact tool arguments and tool-result continuation passed direct API
  checks. The Mac mini can reach the service. No gateway restart or routing edit.

This is basic endpoint readiness, not a new broad agent-quality certification.
[Handover evidence](../evidence/prefill-2026-11-05/handover.json).

## Baseline and diagnostic are separate

The earlier uninstrumented cold 64K fixture measured **367.33 tok/s** at
2048/2048 and **354.59 tok/s** at 2048/1024, one run each. Decode was about
16.1 tok/s with 128 output tokens. The smaller ubatch did not help this model;
retain 2048/2048. [Historical measurements](../evidence/prefill-2026-11-05/prior-ubatch-comparison.json).

The new run uses the same source fixture, target, draft, Q8 KV and existing
runtime, with per-operator Vulkan timestamps. It measured 176.46 s prompt time
and 172.25 s summed GPU operator time. **Its 371.40 tok/s is instrumented and is
not a claimed improvement over 367.33.** Timestamp barriers can perturb execution;
this run establishes where time went, not a new throughput baseline.

The public service remained resident and idle throughout; the diagnostic watched
its slot and would terminate if live traffic arrived. No live request arrived.
There was no concurrent compilation. A mid-run sample recorded GPU 89% busy,
2354 MHz, 81 C, auto DPM and CPU balance_performance/powersave. One sample does
not establish thermal, power, compute, occupancy or bandwidth saturation.

## Where the cold 64K time goes

32 target and 32 draft-prefill graphs cover all 65,536 tokens. Warmup and decode
are excluded. Percentages below use summed GPU operator time, not wall time.

| Work | GPU seconds | Share |
|---|---:|---:|
| Quantized dense matrix multiplication | **107.91** | **62.65%** |
| Attention compute | **34.80** | **20.20%** |
| Gated DeltaNet | 8.47 | 4.92% |
| Activation conversion to F16 | 4.17 | 2.42% |
| Fused convolution | 1.54 | 0.89% |
| Attention preparation | 1.27 | 0.74% |
| F32 matrix multiplication | 0.72 | 0.42% |
| Other operations | 13.37 | 7.76% |

Q5_K matrix work takes **52.14 s**, IQ4_XS **22.91 s**, Q4_K **17.54 s**, Q6_K
**9.27 s**. The Q4 filename does not mean every matrix uses Q4_K. The largest
individual dense shapes are:

| Weight type / M × N × K | GPU seconds |
|---|---:|
| Q5_K / 17408 × 2048 × 5120 | 21.58 |
| IQ4_XS / 17408 × 2048 × 5120 | 16.34 |
| Q5_K / 5120 × 2048 × 17408 | 12.59 |

The entire draft-prefill contribution is only **0.86 s**, about 0.50% of GPU
prefill. Dropping DFlash2 is not a useful raw-prefill project.

Attention grows with context: its share of target GPU time is 6.3% in tokens
0–16K, 16.0% at 16–32K, 24.0% at 32–48K and 30.4% at 48–64K. Dense matrix work
still accounts for 54.5% in the last band. Do not extrapolate these shares to a
150K cold prompt or short cached append without measuring those shapes.

[Complete summary](../evidence/prefill-2026-11-05/profile-summary.json),
[per-graph operator records](../evidence/prefill-2026-11-05/profile-records.json).

## Existing optimizations are already in this baseline

The pinned [Vulkan implementation](https://github.com/LeoStehlik/llama.cpp/blob/a82001bd382ea54481603be113ced229a21db8d2/ggml/src/ggml-vulkan/ggml-vulkan.cpp)
already contains Q8-to-F16 attention staging, eligible multi-row attention with
its scheduling knobs enabled by default, shape-gated XL dense tiles and F16
activation staging. The profile directly shows `FA_KV_DEQUANT`, `FA_V_TRANSPOSE`,
`MM_B_TO_F16` and `CONCAT_SSM_CONV_SILU` executing. The MR gate is eligible for the
observed 256-wide heads on RADV; this capture does not log each shader dispatch.
Do not count re-enabling or re-porting existing work as a fresh optimization.
The dense shaders also already reuse Q5_K high-bit and IQ4_XS scale data across
K steps; their source records rejected broader reuse attempts. Inspect actual
selected dispatches before proposing that same optimization again. MoE expert
selectors do not apply to this dense target.

## Ranked experiments

1. **Dense GEMM at the measured shapes and weight types.** Isolate the three
   largest buckets above. Measure selected tile, subgroup, register/LDS pressure,
   repeated weight decoding and load stalls before changing scheduling. Existing
   XL/F16-B paths are controls, not proposed inventions. Keep each candidate
   independently switchable; start with operator correctness and then the real
   64K distribution. No saturation diagnosis follows from elapsed time alone.
2. **Test a prefill-only decoded/prepacked weight cache.** Reuse the current
   quantized weight values, without replacing the model or lowering precision.
   Compare today's fused dequant+GEMM against one-time decode plus an F16 GEMM
   on those same shapes, including preparation and memory costs. Keep quantized
   weights for decode. This is a hypothesis: wider weights can make memory
   traffic worse. An all-weight F16 representation is roughly 55 GB before KV,
   original weights, draft and workspace, so measure a selective cache first.
   Check the actual rounding/accumulation path rather than assuming equivalence.
3. **Attention for genuinely longer prefixes and continuations.** Profile a
   128K-or-longer cold request and a cached append separately before a new kernel.
   The existing MR path already helps; Q8 staging and recurrent checkpoints
   must remain correct. The 64K preparation total is small, so it is not the
   first target for a major cold-prefill gain.
4. **Stable-prefix reuse alongside raw prefill.** Measure the actual common token
   prefix across real OpenClaw requests before designing a warm-start path.
   Retain tools and context; do not require stripping the agent to a small prompt.
   Cache full hybrid/recurrent and draft state, enforce model/runtime/token
   compatibility, and test cold misses, partial reuse, invalidation and restore.
   Existing slot persistence is useful infrastructure, not proof of reusable
   OpenClaw prompt layout.

Using this diagnostic wall-time fraction only as an Amdahl estimate, 1.2× faster
quantized dense GEMM would mean approximately **11%** overall improvement; 1.5×
would mean **26%**. Doubling attention alone would mean about **11%**. These are
conditional bounds, not measured gains. Going from 367 to 1,000 tok/s requires
about 2.72× overall; another modest kernel patch is not evidence that we can get
there. Useful action latency, cold and warm, remains the operational criterion.

## Reproduce the diagnostic

Use the pinned runtime and driver above, exact model hashes from
`models/SHA256SUMS`, and the public fixture referenced by the
[protocol](../evidence/prefill-2026-11-05/protocol.json). The fixture is identical
to the Qwen3.6 repository's frozen benchmark fixture; no private prompt is used.
The saved argv uses `$DEPLOYMENT` as a path placeholder, not shell-expanded JSON.

1. Verify no competing GPU work. The diagnostic uses loopback port 18083 and a
   disposable 131,072-token context; the public service retains 245,760.
2. Start the saved argv with `GGML_VK_PERF_LOGGER=1`,
   `GGML_VK_PERF_LOGGER_FREQUENCY=1`, `GGML_VK_PERF_SHAPES=1`; capture stdout/stderr.
   Cache RAM and context checkpoints are disabled only in this disposable server.
3. Tokenize `Warmup: explain matrix multiplication. ` repeated 1,024 times,
   take the first 2,048 tokens and call `/completion` for 16 tokens. Use
   temperature 0, seed 12345, `cache_prompt:false`, `ignore_eos:true`.
4. Verify the public fixture round-trips to its exact 65,536 token IDs with
   `add_special:false` and `parse_special:true`. Submit those IDs to `/completion`
   with the same options and `n_predict:8`. Save its JSON result. Require
   `timings.prompt_n == 65536` and `timings.cache_n == 0`.
5. Stop only the disposable process. Identify the measured task ID in its log
   (5 in this run). Parse and validate all 32+32 graphs:

```bash
python3 benchmarks/analyze-dense-prefill.py profile-server.log \
  --response response.json --output analysis --task 5
```

For a subsequent performance A/B, disable all profiler variables and use the
historical 128-output-token protocol with repeated interleaved controls. This
initial investigation does not install a kernel change or promote a new build.

## Checks for this record

The parser reproduces the committed summary and all per-graph records, validates
32 target plus 32 draft-prefill graphs, and checks per-graph timing sums. Shell
syntax, Python compilation, JSON and local documentation links pass. All four
installed model hashes match `models/SHA256SUMS`. The legacy installation check
prints bundled stock build 11001; the running candidate is separately identified
by its matching library hashes and source commit in the protocol. No runtime
binary or model was changed by this analysis.
