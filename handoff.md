# Handoff for Francis — Flash-Next staging, 2026-11-06

**Linux reboot and GPU recovery verified at 19:04–19:08 UTC on 2026-11-06.**
The driver is live, kernel taint is zero, GPU nodes are accessible and the
112 GiB GTT limit is active. The 27B endpoint is back on the GPU and answered a
direct completion. The Mac/OpenClaw gateway remains out of scope for restart.
Start with the [recovery result and corrected acquisition wrapper](docs/STRATA-RECOVERY-RESULT-2026-11-06.md).
The [pre-reboot record](docs/STRATA-RECOVERY-2026-11-06.md) and
[pre-reboot snapshot](evidence/strata-2026-11-06/pre-reboot-snapshot.json) are historical.

The next backend is Qwen3.8-Flash-Next UD-Q4_K_XL on packaged Strata v0.2.11
(engine/control 0.1.57). The user has already tested Flash-Next successfully on
Ollama Cloud; focus this work on local deployment, cold prefill and real tool use.
The model download is in progress. **Flash-Next is not serving or validated yet.**
At 16:50 UTC the attempted headless `amdgpu` reload crashed in the kernel's ISP
teardown and stopped GPU service. The authorized reboot recovered it. Do not
repeat that hot reload; preserve the recorded failure and recovery evidence.
The signed HIP-Halo engine is installed, auto-detected and fully hash-verified;
only its version probe has executed, not inference.

[Deployment procedure, exact pins, pending checks and performance attribution](docs/STRATA-FLASH-NEXT.md).
The published 1,211 tok/s at 128K is an upstream 0.1.40 result, not our result.
The pre-fault GPU had a 57.7 GiB GTT limit; the upstream benchmark used 112 GiB.
Do not treat a writable TTM sysfs parameter as proof that
the already-initialized GTT/KFD limits changed. The prepared boot configuration
has now taken effect, with 120,259,084,288 GTT bytes verified after reboot.

Implementation worktree: `/home/less/worktrees/qwen38-strata-20261106`, branch
`deploy/strata-flash-next-20261106`. Acquisition logs are under
`~/.cache/strata-evaluation-20261106/`. Model data is under
`~/models/strata-flash-next/`. Installation scripts acquire and prepare only;
the launch script is a separate, explicit action on loopback port 8083.
The enabled user service `strata-flash-next-acquire.service` completes acquisition and
preparation after the active transfers. Inspect `preparation-status.json` and
`finish-preparation.log` in the acquisition log folder; it does not switch models.
Linger and the unit's boot startup worked. The install wrapper initially failed
because `strata install` interpreted `STRATA_INSTALL_DIR` as a source directory.
It now calls the pinned bundled setup.py in Control mode, with that variable as
the destination. Acquisition has demonstrably resumed. At about 19:08 UTC,
48.34 GB of target data was durably recorded; shards 1 and 4 were complete and
verified, with shards 2 and 3 partial. MTP and the image projector remain pending.
The supervisor phase `preparing` includes downloading; inspect the actual log.

The dense-kernel investigation below is deferred. The frozen Qwen3.6 evidence
and operational setback remain intact; that model stays stopped and disabled.
Do not publish private OpenClaw transcripts as validation evidence.

## Current restored endpoint — dense 27B during acquisition

- Base URL: `http://100.96.8.54:8080/v1`
- Model: `qwen3.8-27b-q4-fast`; Q5 remains available on demand.
- Unit: `qwen38-dflash2.service`, active and enabled; boot startup verified.
- Deployment: `/home/less/qwen38-dflash2`; preserve its pre-existing uncommitted
  `models.ini`, `run-router.sh` and `runtime-candidate/` work.
- Runtime: `runtime-candidate/vulkan`, source `a82001bd3`, bundled Mesa 26.2.4.
- Source: `/home/less/src/llama.cpp-tiercel`, branch `fix/slot-checkpoint-persistence`.
- Context 245,760; Q8 target KV; batch/ubatch 2048/2048; one slot; DFlash width 4.
- Old October 30 snapshot auto-restore disabled; file retained. Cache and
  checkpoint support remain enabled. Existing 27B weights are retained for reuse.

Completion, tool arguments, continuation and Mac reachability passed on November
5. GPU access and a direct completion were rechecked after reboot; no new broad
tool/remote-reachability test is claimed. OpenClaw gateway and routing were not
changed. Do not reboot/restart the Mac or send synthetic channel/agent turns;
the user supplies real OpenClaw prompts.

## Deferred dense-model investigation

The cold 64K profile is complete: quantized dense GEMM 62.65% of GPU time,
attention 20.20%. Q5_K and IQ4_XS are the largest dense buckets. Multi-row attention,
F16 staging and fused convolution already exist in this runtime. Draft prefill
is only 0.50%; removing the drafter will not solve prefill.

The earlier next step was a selective dense prefill weight-cache experiment.
That work is deferred for the packaged Flash-Next trial; do not restart it merely
because it appears in the historical handoff. No new dense kernel was applied.
[Full analysis, conditions and ranked experiments](docs/PREFILL-RETURN-2026-11-05.md).

Historical uninstrumented baseline: 367.33 tok/s at cold 64K, one sample. The
new 371.40 tok/s run is instrumented and is not a speedup claim. Preserve the
model/context; judge useful task completion, not isolated throughput alone.

Local raw evidence: `~/.cache/qwen38-return-20261105/`; historical comparison:
`~/.cache/qwen38-ubatch-compare.fp9Hef/`. Public evidence excludes user transcripts.
That profiling work is isolated in `/home/less/worktrees/qwen38-prefill-analysis-20261105` on
`investigate/dense-prefill-20261105`; no source changes or deployment replacement
were made by the profiling investigation. The diagnostic listener is stopped.
