# Handoff for Francis — Qwen3.8 return, 2026-11-05

Qwen3.8-27B Q4 + DFlash2 is running on the Strix Halo GPU again. Qwen3.6 is stopped
and disabled at boot, with its weights, code, builds and frozen performance tag
retained offline. Its [operational setback](https://github.com/LeoStehlik/qwen3.6-35b-a3b-strix-halo/blob/main/docs/OPERATIONAL-SETBACK.md)
is documented separately from its successful performance work.

## Current endpoint

- Base URL: `http://100.96.8.54:8080/v1`
- Model: `qwen3.8-27b-q4-fast`; Q5 remains available on demand.
- Unit: `qwen38-dflash2.service`, active and enabled.
- Deployment: `/home/less/qwen38-dflash2`; preserve its pre-existing uncommitted
  `models.ini`, `run-router.sh` and `runtime-candidate/` work.
- Runtime: `runtime-candidate/vulkan`, source `a82001bd3`, bundled Mesa 26.2.4.
- Source: `/home/less/src/llama.cpp-tiercel`, branch `fix/slot-checkpoint-persistence`.
- Context 245,760; Q8 target KV; batch/ubatch 2048/2048; one slot; DFlash width 4.
- Old October 30 snapshot auto-restore disabled; file retained. Cache and
  checkpoint support remain enabled. No new model download.

Actual completion, exact tool arguments, result continuation and Mac-mini
reachability passed. Basic readiness is not a broad quality guarantee.
OpenClaw gateway and routing were not changed. Do not reboot/restart the Mac or
send synthetic channel/agent turns; the user supplies real prompts.

## Next optimization target

The cold 64K profile is complete: quantized dense GEMM 62.65% of GPU time,
attention 20.20%. Q5_K and IQ4_XS are the largest dense buckets. Multi-row attention,
F16 staging and fused convolution already exist in this runtime. Draft prefill
is only 0.50%; removing the drafter will not solve prefill.

Start with the measured dense shapes and a selective prefill weight-cache
experiment; do not port MoE selectors or repeat the old batch sweep. Longer
context/append profiling and exact-prefix reuse are complementary next steps.
No new kernel has been applied. [Full analysis, conditions and ranked experiments](docs/PREFILL-RETURN-2026-11-05.md).

Historical uninstrumented baseline: 367.33 tok/s at cold 64K, one sample. The
new 371.40 tok/s run is instrumented and is not a speedup claim. Preserve the
model/context; judge useful task completion, not isolated throughput alone.

Local raw evidence: `~/.cache/qwen38-return-20261105/`; historical comparison:
`~/.cache/qwen38-ubatch-compare.fp9Hef/`. Public evidence excludes user transcripts.
Work is isolated in `/home/less/worktrees/qwen38-prefill-analysis-20261105` on
`investigate/dense-prefill-20261105`; no source changes or deployment replacement
were made by the profiling investigation. The diagnostic listener is stopped.
