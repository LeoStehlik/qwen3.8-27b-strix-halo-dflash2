# Flash-Next first GPU load — 2026-11-07

Flash-Next UD-Q4_K_XL is loaded on the packaged HIP-Halo engine and has passed
a direct completion and a synthetic tool/continuation check. This is a working
local evaluation listener, not a completed OpenClaw deployment or a long-context
performance result.

Acquisition and preparation finished at 01:34:37 UTC. At the user's request,
`qwen38-dflash2.service` was stopped and disabled before loading Flash-Next.
Its weights, runtime, service definition, configuration and existing local edits
were retained. No OpenClaw routing, Mac service, GPU driver or boot parameter
was changed. Stopping the old unit released its GPU allocations and left about
113 GiB of available system RAM. Its intentional SIGINT exit was recorded as
status 130; the failed-unit marker was cleared after confirming its processes
were gone.

## Running configuration

- Unit: `strata-flash-next.service`, running but **not enabled at boot**;
  automatic restart is off during evaluation.
- API: `http://127.0.0.1:8083/v1`, loopback only.
- Model: `qwen3.8-flash-next-unsloth-ud-q4_k_xl`.
- Strata v0.2.11, engine/control 0.1.57, HIP-Halo build `0bdcef4682c5+rocm`.
- Context 262,144, INT8 KV, one slot, MTP depth 4, GPU vision encoder.
- Prefill 16,384; `STRATA_ROUTE_TAIL_SKIP=0`.
- Installer-selected resident budget 38 GiB and requested expert cache 5,080.
  The engine reports an effective GPU cache of 6,474 experts / 18.89 GiB and
  a 38 GiB page-locked host complement. The file tier remains active: this
  configuration does not hold every expert permanently in GPU memory.
- Bundled gfx1151 hipBLASLt tuning table selected automatically.
- Upstream Halo defaults are preserved, including Q8 hyper-connection weights;
  the engine notes that these can alter near-tie tokens. No output-equivalence
  claim against the old backend is made.

The service started at 13:23:00 UTC and reported ready at 13:23:29. The vision
encoder warmed successfully. System RAM available after the smoke requests was
about 38 GiB; kernel taint remained zero. These are startup/small-request
observations, not a peak-memory measurement at 256K context.

## Checks completed

1. All four target shards and the vision projector have installer verification
   markers; model pack and MTP preparation completed. The signed engine's full
   282-file verification passed. The prepared MTP GGUF is about 0.889 GB;
   the earlier 5.2 GB download estimate is not its final retained size.
2. `/health` and `/v1/models` report the expected loaded model, 262,144 context
   and image input support.
3. A direct request returned exactly `READY`, normal stop, in 1.29 seconds.
   This two-token response is not a throughput benchmark.
4. The existing synthetic tool smoke test passed: one `lookup_record` call,
   exact typed arguments, valid call ID, and a continuation containing the
   returned verification code `R7P2` without another tool call.
5. That continuation reused 540 prompt tokens and processed 39 new tokens.
   This demonstrates in-memory prefix reuse for this case, not disk checkpoint
   restoration or broad agent quality.

Evidence is under [`evidence/strata-2026-11-07/`](../evidence/strata-2026-11-07/).
The requests are synthetic and execute no tools. No OpenClaw/channel turns were
sent. The old 27B listener is offline; no replacement has been exposed remotely.

## Reproduce this evaluation service

Run the pinned installer from the deployment guide first. Its generated config
uses absolute paths for the installing user. Set the planned prefill explicitly:

```bash
python3 - <<'PY'
import json
from pathlib import Path
p = Path.home() / '.local/share/strata/flash-next/strata-unsloth-ud-q4_k_xl.json'
d = json.loads(p.read_text())
for key in ('args', 'args_written'):
    a = d[key]
    a[a.index('--prefill') + 1] = '16384'
p.write_text(json.dumps(d, indent=2) + '\n')
PY
systemctl --user disable --now qwen38-dflash2.service
install -m 644 systemd/strata-flash-next.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user start strata-flash-next.service
journalctl --user -u strata-flash-next.service -f
```

Wait for actual readiness, then run:

```bash
python3 benchmarks/strata-tool-smoke.py \
  --model qwen3.8-flash-next-unsloth-ud-q4_k_xl \
  --out /tmp/flash-next-tools.json
```

Do not run both model services together. To deliberately return to the old
deployment, stop Flash-Next first, then `systemctl --user enable --now
qwen38-dflash2.service`. No deletion or reinstall is needed.

## Remaining validation

Cold 64K/128K performance, above-150K capacity, streaming tools, an actual image
request, disk state save/restore, repeated fresh starts, private endpoint
reachability and user-supplied real OpenClaw prompts remain to be tested. The
published 1,211 tok/s at 128K is still upstream historical evidence, not a local
result. Enable a persistent replacement only after the deployment checks pass.
