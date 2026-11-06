# Flash-Next on packaged Strata — deployment in progress

Status on 2026-11-06: the packaged Terminal and HIP-Halo engine are installed and the pinned model
download is underway. **Flash-Next is not yet serving. No local performance or
tool-quality result has been established.** The dense 27B service remains the
active endpoint. These scripts are preparation for a separate backend; this
repository's existing llama.cpp deployment remains available for rollback.

## Why this direction

Qwen3.6's performance work succeeded, but it failed the operational requirement
for reliable OpenClaw tool use and recovery. The
[setback report](https://github.com/LeoStehlik/qwen3.6-35b-a3b-strix-halo/blob/main/docs/OPERATIONAL-SETBACK.md)
records the observations without claiming an isolated model/runtime root cause.
The user has already tested Flash-Next successfully through Ollama Cloud with
OpenClaw. That motivates the local trial; it is not a quality test of this quant
or this server. Further dense-27B kernel work is deferred.

## Pinned installation

- Host: Ryzen AI Max+ 395, Radeon 8060S (`gfx1151`), nominal 128 GB RAM,
  Ubuntu 26.04, kernel `7.0.0-42-generic`; 115 GiB visible to the OS.
- Release: [Strata v0.2.11](https://github.com/Niko1221/Strata/releases/tag/v0.2.11),
  Terminal/control and HIP-Halo engine version `0.1.57`.
  The installed engine is signed, build `0bdcef4682c5+rocm`; all 282 package files
  passed verification, GPU backend auto-detection passed, and `--version` ran.
  These checks establish installation integrity, not successful model inference.
  [Recorded engine metadata and hashes](../evidence/strata-2026-11-06/engine.json).
- Target: `unsloth/Qwen3.8-Flash-Next-GGUF`, `UD-Q4_K_XL`, revision
  `38bb39ee97821de2c9009abb7e93950eec396e66`.
- About 111.3 GB of target shards plus the 5.2 GB MTP companion and 0.9 GB image
  projector. Keep at least 150 GB of free storage for preparation and artifacts.
- Target configuration: 262,144 context, INT8 KV, one slot, MTP depth 4,
  16,384-token prefill chunks, vision enabled, route-tail skipping explicitly off.
  Request-specific test output caps do not impose a serving output limit.
- First listener: loopback port 8083. Do not configure OpenClaw to use it until
  actual generation, tools, and remote reachability have passed.

Acquire without starting a model:

```bash
bash scripts/install-strata-flash-next.sh
```

The installer verifies the signed component feed and the model's pinned hashes.
It uses the packaged engine; no driver, ROCm toolchain, or llama.cpp fork is built.
Model preparation may acquire the upstream preparation sources when required.
`STRATA_MODEL_DIR`, `STRATA_INSTALL_DIR`, and `STRATA_BIN` can override the local
paths. Preserve the generated config and the component manifest with results.

On the current host, `strata-flash-next-prepare.service` finishes acquisition and
preparation in the background after the active shard downloads. It writes
`~/.cache/strata-evaluation-20261106/preparation-status.json` and
`finish-preparation.log`. It does not load the new model, stop the old service,
or change OpenClaw routing. A `prepared-awaiting-validation` status is not readiness.

After the download and memory preflight, free the GPU of other model servers,
inspect the plan, then launch the isolated evaluation listener:

```bash
bash scripts/launch-strata-flash-next.sh --plan
bash scripts/launch-strata-flash-next.sh
python3 benchmarks/strata-tool-smoke.py --out /tmp/flash-next-tools.json
```

The smoke check verifies exact typed tool arguments and result continuation
using synthetic data. It does not execute tools, send OpenClaw messages, or
establish broad agent quality. Real OpenClaw requests follow the technical checks.

## Deployment checks still required

1. Finish and verify every model/component download; prepare the model pack.
2. Resolve the GPU memory limit. This host reports 61,905,670,144 bytes of GTT
   (about 57.7 GiB), plus an 8 GiB BIOS carve-out. The published benchmark host
   used a 112 GiB GTT. Linux initializes the AMD GTT manager and KFD limits from
   TTM at driver initialization; writing a larger sysfs TTM number alone does
   not prove that the active GPU limit increased. No driver reload or reboot
   has been performed for this deployment.
3. Review the effective memory plan, expert residency, image encoder and native
   context. A small GPU cache with pinned host experts can count memory twice;
   do not force a large cache/budget merely to match a headline.
4. Test first-request readiness across fresh starts. The launcher warns about
   UD-Q4_K_XL first-request hangs observed on engine 0.1.54/0.1.55. Its presence
   is a reason to test 0.1.57, not evidence that 0.1.57 hangs here.
5. Verify ordinary output, exact tool arguments, streaming tool calls, tool
   result continuation, warm-prefix reuse, and explicit state save/restore.
6. Measure cold 64K and 128K prompts: actual token count, uncached tokens,
   engine prompt time, client first-token latency, decode speed, peak memory,
   configuration, fixture hash and at least two comparable runs. Test a prompt
   above 150K as a capacity check. Keep cold and cached results separate.
7. Only then switch the private endpoint and make the validated service the
   persistent default. The OpenClaw gateway on the Mac must not be restarted.

## Performance evidence and next experiments

The upstream [Halo guide](https://github.com/Niko1221/Strata/blob/v0.2.11/docs/STRIX_HALO.md)
reports **1,211 tok/s prefill and 42.64 tok/s decode at 128K** for this quant on
the maintainers' 395/128GB Linux machine, using engine 0.1.40. These are historical
upstream measurements, not results from this installation or a promise for
0.1.57. The guide calls Halo support experimental.

First measure the packaged baseline. Then compare the documented fused prefill
experts (`STRATA_PF_FUSED` plus `STRATA_PF_FUSED_KQ` for this quant), prefill GEMM,
attention and hyperconnection switches independently. Preserve tool behavior
and assess numerical changes; do not enable an entire bundle and attribute its
gain to one switch. Profile the winning configuration before new kernel work.
Prefix reuse complements cold-prefill acceleration; it does not replace it.

The deployment is not an engine fork. Maintain reproducible configuration and
evidence here; consider upstream contributions only after a measured improvement.
