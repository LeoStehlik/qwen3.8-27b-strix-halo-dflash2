# Archived host records — before reboot, 2026-11-06

These are records of the performed deployment work, not scripts to run in order.
Executable scripts/units are saved with `.txt` suffixes so they are not confused
with the supported installation scripts in `scripts/`.

**Do not execute `raise-gtt-failed-attempt.py.txt`.** Its `amdgpu` removal crashed
the current kernel. It also restarted the old server through `finally`, which
fell back to CPU; that server was subsequently stopped explicitly. This file
preserves the exact failed attempt for review, not a recovery recipe.

| Record | Purpose |
|---|---|
| `manifest.json` | Capture time, original local paths, sizes and SHA-256 hashes of copied files |
| `fetch-shard.py.txt` | Helper used to fetch pinned target shards with Strata's downloader |
| `finish-preparation.py.txt` | Actual acquisition supervisor, with local paths and terminal states |
| `preparation-wait-pids.json` | Original downloader identities; start times are checked before waiting |
| `strata-flash-next-acquire.service.txt` | Enabled user unit; no inference launch or promotion |
| `70-strata-halo-ttm.conf.txt` | Prepared 112 GiB TTM limit for next driver initialization |
| `gtt-before.json` | Original TTM/GTT limits observed before the failed maintenance |
| `kfd-acl-before.txt` | Original KFD ACL before granting access to the existing login |
| `raise-gtt-failed-attempt.py.txt` | Exact failed maintenance helper; evidence only |
| `gtt-maintenance.log.txt` | Python error path showing removal SIGKILL and reload failure |
| `kernel-fault-excerpt.txt` | Relevant AMD kernel fault/stack; unrelated host/network logs excluded |
| `initramfs-update.log.txt` | Successful initramfs rebuild output |
| `install-engine.json` | Signed-feed update result, including binary-only test scope |
| `engine-component.json` | Published signed component manifest, file hashes and target architecture |

The snapshot one directory above contains the service state, boot ID, download
pieces, initramfs hash and pending authorization. Configuration/recovery intent
must not be confused with a successful reboot or model validation. See the
[recovery handoff](../../../docs/STRATA-RECOVERY-2026-11-06.md).
