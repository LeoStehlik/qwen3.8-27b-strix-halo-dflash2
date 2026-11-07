# Rejected experiment: bounded F16 expert dispatch

**Do not enable this in the serving configuration.** All five tested persistent
grid sizes were slower on the dominant Q4_K / Q5_1 expert format at a 16,384-token
chunk. This directory preserves the code and the negative result.

The original F16 path launches an upper bound on the number of tiles. Blocks
beyond the actual expert batch return without matrix work. The experiment
limits blocks to `STRATA_PF_F16_KQ_PERSIST` times the device's compute-unit count
and iterates over actual tiles. It preserves arithmetic, tile selection and
expert ownership, with a block barrier before reusing shared memory.
Zero/unset retains the original path. Q8_0 down projection is unchanged.

## Results on gfx1151, 2026-11-07

| Dispatch | Median full expert operator, ms |
|---|---:|
| Original control, before / after | 54.000 / 54.326 |
| Patched, disabled, before / after | 54.148 / 54.261 |
| 1 block per CU | 85.467 |
| 2 blocks per CU | 62.468 |
| 4 blocks per CU | 65.332 |
| 8 blocks per CU | 58.897 |
| 16 blocks per CU | 58.651 |

These are eight back-to-back timings per invocation, 512 experts, top-10
routing, default tile selector and all weights resident. The test also times
an alternating sequence. `S20_NOMMQ=1` disables the MMQ comparison, so the
printed placeholder MMQ time and speedup ratio must be ignored. No concurrent
GPU work or inference server was running. Host compaction remained at 20.

Every timing output hash was `507bd523cd60c84a`, including the original binary
and the patched binary with dispatch disabled. CPU-reference tests also passed
for Q4_K/Q5_1, Q4_K/Q8_0 and Q5_K/Q8_0, forced 64/128-row tiles, original and
permuted routing, and grid factors 0, 1 and 16: 36 format-level checks across
24 processes. The permutation places zero-row experts between active experts,
exercises empty launch ranges and keeps first/final experts active. Full output
hashes match across dispatch modes; row ownership is one-to-one and every output
is finite. The reference tolerance is the upstream F16 tolerance, not exact
agreement with FP32. No model-level speed or quality result is claimed.

The fastest opt-in case is still about 8% slower than the control. The empty
launch bound alone is not a demonstrated useful target. No full-model run was
warranted, and this patch was not promoted. CUDA and other GPU targets were not
built or tested; this is archived experimental code, not an upstream PR.

## Reproduction

Use a separate checkout of [Strata v0.2.11](https://github.com/Niko1221/Strata/tree/v0.2.11),
commit `c3b3f5035506f3e966f1b4b7b188aeaabae92f1d`, and GGML from llama.cpp commit
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. The packaged engine's build ID differs;
compare the two binaries built from this same source, not a package/source pair.

We used the user-local [TheRock gfx1151 7.14.1 SDK](https://repo.amd.com/rocm/tarball-multi-arch/therock-dist-linux-gfx1151-7.14.1.tar.gz):
1,713,467,716 bytes, SHA256
`c40e8f2bd6630a7d11557c762b99c6fa8afb04c9bd0e51ed1675ee1ca24afb00`.
The unpacked SDK is about 8.3 GB. No system driver replacement is needed or was
performed. The pinned GGML archive SHA256 was
`c076d7534afa0e5d0ec2a0d425b11e791c16f3de0d727221aea071cef156a280`.

[Exact CMake arguments and SDK environment](../../evidence/strata-performance-2026-11-07/kernel-dispatch/configure-command.json)
record the build. Substitute your checkout and SDK paths. Build only the
`hip_prefill_fused_iq` target, then preserve that unmodified executable beside
it as `hip_prefill_fused_iq.control` (same directory preserves its runtime
library search paths). Apply `rejected.patch` to the checkout with `git apply`,
then rebuild the same target. Both builds used `--parallel 8`.

With no other GPU workloads running:

```sh
python3 check-reference.py --build-dir /path/to/build --sdk /path/to/sdk --output /path/to/new-reference-results
python3 screen-timing.py --build-dir /path/to/build --sdk /path/to/sdk --output /path/to/new-screen-results
```

The runners refuse to overwrite existing logs and abort on failed validation
or unequal hashes. Evidence and the exact executed commands are under
[`kernel-dispatch`](../../evidence/strata-performance-2026-11-07/kernel-dispatch/).
The portable runners have the same cases as the recorded machine-local runners.
