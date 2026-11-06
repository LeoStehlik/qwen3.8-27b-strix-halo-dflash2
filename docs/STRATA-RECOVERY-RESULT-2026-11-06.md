# Recovery verified; Flash-Next acquisition resumed

The authorized Linux-host reboot completed. At 19:04–19:08 UTC on 2026-11-06,
the boot ID differed from the pre-reboot record, `amdgpu` was `live`, the kernel
taint value was zero, and `/dev/kfd` and `/dev/dri/renderD128` were accessible to
the normal user through its `render`/`video` groups. Both TTM limits were
29,360,128 pages; the driver reported **120,259,084,288 bytes / 112 GiB GTT**.
No additional reboot or driver reload was needed for these checks.

The existing dense 27B service started automatically. Its llama-server process
held the GPU render node and used about 34.5 GB of GTT. A direct API request to
`http://100.96.8.54:8080/v1` returned the requested `READY` response with a normal
stop reason. This establishes recovery/readiness, not throughput or broad quality.
The Mac and its OpenClaw gateway were not restarted or reconfigured.

## Acquisition wrapper correction

The persistent acquisition unit did start after boot, but preparation repeatedly
failed with exit 5: `this folder has no installer (setup.py)`. No further target
download happened through that failing path.

Our wrapper exported `STRATA_INSTALL_DIR` as the destination for model run configs,
then called `strata install`. In packaged 0.1.57, that CLI first treats this variable
as the directory containing `setup.py`, so it looked in the new destination
instead of the installed bundle. This was a deployment-wrapper error.

The corrected script invokes the packaged `setup.py` using its bundled Python,
with `STRATA_CONTROL_INSTALL=1` and `STRATA_INSTALL_DIR` still set to the destination.
This keeps the source bundle separate from writable installation state and uses
the packaged Control preparation path. `STRATA_BUNDLE_DIR` optionally overrides
the default pinned bundle location. No installed engine/installer source was edited.

The acquisition unit was restarted after the correction. The installer now
recognizes the HIP-Halo engine and its image reader, reuses the completed first
shard, and resumes shard 2 at about 18.35 GB. Shard 3's partial pieces and the
completed fourth shard remain intact. A subsequent 20-second check saw another
134,217,728 bytes recorded in completed download pieces.

## Current boundary

At 19:08 UTC, about **48.34 GB of target data** was durably recorded. The target
totals 111.33 GB, with approximately another 6.1 GB for MTP and the image projector.
This progress snapshot counts completed/fsynced pieces, not sparse file lengths.
The supervisor's `preparing` phase includes downloading; it does not mean inference
has started. The actual stage is visible in `finish-preparation.log`.

**Flash-Next is still not serving.** Final pack preparation, model loading,
startup reliability, tools, vision, state/cache restoration, long-context
capacity and cold-prefill performance remain untested. Keep the 27B service as
the current endpoint during acquisition; free its GPU allocation before loading
Flash-Next for the isolated evaluation.

See the [recorded recovery evidence](../evidence/strata-2026-11-06/post-reboot-recovery.json),
[historical incident and pre-reboot record](STRATA-RECOVERY-2026-11-06.md), and
[deployment/validation procedure](STRATA-FLASH-NEXT.md). The old incident remains
documented; its pre-reboot table is historical and does not describe the recovered host.
