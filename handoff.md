# Handoff for Francis — Flash-Next performance investigation, 2026-11-07

**PAUSED FOR USER REBOOT, approximately 14:49 UTC.** All three inference services
are stopped and disabled; ports 8080, 8083 and 8084 are closed. The user will
reboot. The agent has not rebooted or changed sysctls. The runtime benchmark
override is removed. OpenClaw on the Mac was not restarted.

Last completed F16 results: cold 16K **1,390.5 / 41.8 tok/s** prefill/generation;
cold 64K **1,411.7 / 37.9**. The 128K run was cancelled for this pause. Some
first requests suffer multi-second GPU queue evictions coinciding with Linux
memory compaction. `kernel.numa_balancing=0`, `vm.compaction_proactiveness=20`.
The early PLE flag did not fix all pauses. Generation target remains unmet.

After the user confirms reboot completion, resume the goal and first repeat
the same F16 configuration under the original host policy. Local runner:
`python3 ~/.cache/strata-evaluation-20261107/performance/run-arm.py gpu-mmap-f16-cleanboot --sizes 16384 65536 131072`.
It starts an isolated 8084 service without enabling boot startup. Then consider
the reversible compaction experiment documented in the performance record.
The 8083 production config is still the original installer layout. Do not
blindly enable it; select and validate the intended configuration before
restoring the private listener and boot startup. No winning config is promoted.

The following paragraphs summarize the investigation before the pause.

**Performance work is active; Tiercel is temporarily offline for isolated
configuration comparisons at loopback port 8084.** The user set a target of
1,100 tok/s prefill and 50–60 tok/s generation and explicitly parked tool-call
debugging. Do not send real traffic until the private endpoint is restored.

Packaged Linux Halo prompt kernels were not enabled by the installer. Enabling
the upstream opt-in set raised cold 16K prefill from 540 to 1,027–1,082 tok/s.
Completed cold 64K/128K requests reached 1,234/1,211 tok/s. The first all-GPU
expert layout with mmap PLE reached 1,224 prefill / 42.2 generation at 16K;
its large-context check is pending. Generation profiling is next. The target
has not been fully reached and the investigation is not done.
Read the [performance record](docs/STRATA-PERFORMANCE-2026-11-07.md) first.

**Flash-Next is connected to the existing `tiercelmoe` provider.** Select
`/model qwen-flash-next`, or the full reference
`tiercelmoe/qwen3.8-flash-next-unsloth-ud-q4_k_xl`.
The Mac mini's authenticated streaming check and Francis's live gateway catalog
passed. OpenClaw applied the provider/alias change through hot reload, with PID
369 unchanged. Subsequent real traffic exposed low throughput and one native
verification watchdog exit/reload. Broader quality validation remains pending.

Read the [connection record and reproducible provider patch](docs/STRATA-OPENCLAW-2026-11-07.md),
[first-load evidence](docs/STRATA-FIRST-LOAD-2026-11-07.md) and
[deployment checklist](docs/STRATA-FLASH-NEXT.md).

**Picker correction:** the initial configured-catalog check did not catch the
old Qwen3.6 references in agent allowlists. At 13:52 UTC those were replaced for
Francis and discord-local, and the new reference added to the default policy.
Both agents' live `models.list` **default/allowed** views now include Flash-Next.
The gateway was not restarted. Reopen an already-sent chat model menu to refresh it.
See the [policy check evidence](evidence/strata-2026-11-07/openclaw-picker-policy.json).

## Current listener and resources

- API: `http://100.96.8.54:8083/v1`, Tailscale address only, existing provider credential required.
- Model: `qwen3.8-flash-next-unsloth-ud-q4_k_xl`.
- Unit: `strata-flash-next.service`, stopped and disabled for the user reboot;
  runtime benchmark override removed. Automatic systemd restart
  after failure remains off. Boot validation for this unit is pending.
- Strata v0.2.11, engine/control 0.1.57, signed HIP-Halo build `0bdcef4682c5+rocm`.
- Context 262,144, INT8 KV, one slot, MTP depth 4, prefill 16,384, GPU vision.
- Route-tail skipping explicitly off; bundled gfx1151 hipBLASLt tuning active.
- Installer memory budget: 38 GiB page-locked host experts; effective GPU expert
  cache 6,474 slots / 18.89 GiB. File-tier reads remain active.
- About 38 GiB system RAM available after the small checks; this is not the
  long-context peak. GPU driver is live, taint zero, 112 GiB GTT active.

The user explicitly authorized stopping the old 27B server and retaining it.
`qwen38-dflash2.service` is stopped and disabled to prevent resource competition.
Its old `http://100.96.8.54:8080/v1` listener is offline. Its weights, source,
configuration and pre-existing local edits remain intact. To roll back, stop
Flash-Next before enabling/starting the old unit; do not run both together.
Qwen3.6 also remains stopped and disabled, with frozen evidence and files retained.

## Evidence and next work

The direct completion returned exactly `READY`. The synthetic tool check passed
exact typed arguments and tool-result continuation; the continuation reused 540
prompt tokens. A streamed completion from the Mac also passed. Disk checkpoints, streaming
tool calls, an actual image request, above-150K completion
and broader fresh-start reliability remain untested. The upstream historical 1,211 tok/s is not a local
measurement. Do not claim broad agent quality from this smoke check.

The user has tested Flash-Next successfully through Ollama Cloud. Continue with
local performance and real-prompt checks. Only the existing Tiercel provider and
its model alias were changed; agent defaults and current session selections were
not. Do not restart/reboot the Mac or send synthetic agent/channel turns.
The user can select the new alias after the private listener is restored.

Implementation worktree: `/home/less/worktrees/qwen38-strata-20261106`, branch
`investigate/strata-performance-20261107` (branched from deployment commit
`92c5521`). Current local results:
`~/.cache/strata-evaluation-20261107/`; public synthetic evidence:
`evidence/strata-2026-11-07/`. Model data: `~/models/strata-flash-next/`.
Config and engine log: `~/.local/share/strata/flash-next/`.

The [November 6 recovery record](docs/STRATA-RECOVERY-RESULT-2026-11-06.md) and
[pre-reboot incident](docs/STRATA-RECOVERY-2026-11-06.md) are historical.
**Do not repeat the failed live amdgpu reload.** The authorized reboot applied
112 GiB GTT successfully; no additional driver reload or reboot occurred here.

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
