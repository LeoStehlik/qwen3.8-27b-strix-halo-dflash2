# Flash-Next performance investigation — November 7, 2026

**Resumed after the user's clean reboot at 14:51:52 UTC.** Strata is active only
on loopback 8084 for isolated comparisons; all inference boot startup remains
disabled. The first clean-boot results are below. Prefill is the user's first
priority, including gains beyond 1,400 tok/s; generation comes next.

Target: at least 1,100 tokens/s cold prefill and
50–60 tokens/s generation on the existing UD-Q4_K_XL model. Tool-call debugging
is explicitly deferred. Do not substitute a smaller quant or context to meet
the target.

## Initial deployment missed the target

The first real OpenClaw request supplied 187,737 input tokens. It was cancelled
after the engine processed 80,551 uncached tokens in 154.462 seconds: 521.5
tokens/s. This was a partial prompt, not a completed 187K benchmark.

After the user reset the session, a 15,388-token request reused 15,015 tokens;
only 373 were newly processed. Its 36.8 tokens/s generation and short prompt
delay must not be presented as cold 15K performance. Later live generation
ranged roughly 25.5–42 tokens/s.

At 13:59 UTC a native verification watchdog timed out at layer 45 during
generation. The engine exited with SIGTERM and the control server loaded it
again for the retry. No assistant restart caused this incident. Kernel logs
reported long-running `amdgpu_amdkfd_restore_userptr_worker` work, but no GPU
reset or OOM was observed. Causation is unproven. An engine that recovers on
retry has not thereby passed stability validation.

## Controlled comparison

Strata release v0.2.11, engine/control 0.1.57, build `0bdcef4682c5+rocm`,
HIP gfx1151 on the 128 GB Ryzen AI Max+ 395. Same model revision and quant,
262,144 context capacity, INT8 KV, MTP, vision and route-tail skipping disabled.
The bundled 90-row hipBLASLt table is active.

`benchmarks/strata-prefill.py` sends public source text at approximately the
specified sizes. It places a fresh nonce at the start, records actual token
counts and cache reuse, and requests 512 output tokens at temperature zero,
thinking disabled. This is an inference benchmark, not an OpenClaw task or a
claim about tool quality. The output allowance applies only to these requests.
Cold means no reused prompt state; it does not mean cleared OS file caches.

Fixture SHA-256:
`6efd5cb8693d5c7fc9fa826da0e454895172071c7d30283f6eb6c04978875346`.
The fixture contains repeated source material; its expert distribution and
draft acceptance need not match a real conversation. Each arm receives a short
warm-up. The original baseline was measured on the previously loaded engine;
other arms were freshly loaded. Repeated and larger-context checks follow any
promising screening result.

| Configuration | Actual cold input | Prefill tok/s | Generation tok/s | Output tokens |
|---|---:|---:|---:|---:|
| Installer layout, explicit 16K chunks | 16,394 | 540.3 | 32.7 | 512 |
| Same layout, auto chunks (selected 8K) | 16,392 | 463.5 | 33.8 | 512 |
| Same layout, fast prompt kernels, 16K chunks | 16,393 | 1,027.3 | 32.0 | 512 |
| Fast prompt kernels, repeat | 16,397 | 1,082.3 | 32.9 | 512 |
| Fast prompt kernels, 64K | 65,547 | 1,234.0 | 30.7 | 512 |
| Fast prompt kernels, 128K | 131,078 | 1,211.3 | 32.2 | 512 |
| All GPU experts, direct PLE, own prompt buffers | 16,393 | 990.2 | 28.4 | 512 |
| All GPU experts, mmap PLE, own prompt buffers | 16,392 | 1,223.6 | 42.2 | 512 |
| Same layout, full GPU KV | 65,548 | 1,240.1 | 39.3 | 512 |
| Same layout, full GPU KV | 131,073 | 1,202.1 | 37.9 | 512 |

The fast prompt set is opt-in on Linux Halo in this release. It was absent
from the generated installation. The benchmark changes only these environment
settings from the original 16K arm:

```sh
STRATA_PF_FUSED=1
STRATA_PF_FUSED_KQ=1
STRATA_PF_GEMM=1
STRATA_HC_UPMIX=1
STRATA_PA_FAST=1
STRATA_HIP_WMMA=1
STRATA_SELECT_WMMA=1
STRATA_PF_SWITCH_MIN_T=4096
STRATA_PREFILL_STREAM_MIN=128
```

These are packaged upstream kernels, not a locally modified engine. Some
change floating-point rounding; output identity or model-level equivalence
has not been established by this performance comparison.

The 128K request completed with zero reused prompt tokens in 108.209 seconds
of prefill, then generated 512 tokens. This reproduces the vicinity of the
published prefill result on our custom fixture; it does not reproduce the
upstream benchmark protocol or its decode result.

To reproduce the input, download the [pinned public fixture](https://github.com/LeoStehlik/qwen3.6-35b-a3b-strix-halo/blob/4c1186a727b8e3b45422266563b6cee089f89679/benchmarks/fixtures/prompt.txt)
and verify the SHA-256 above. With the isolated server loaded and the API key
available as `STRATA_API_KEY`, run:

```sh
python3 benchmarks/strata-prefill.py \
  --url http://127.0.0.1:8084 \
  --model qwen3.8-flash-next-unsloth-ud-q4_k_xl \
  --fixture /path/to/prompt.txt \
  --sizes 16384 65536 131072 --repeat 1 --max-tokens 512 \
  --out results.json
```

## Memory layout to investigate next

The installer selected 38 GiB of pinned host experts and a numeric GPU cache
of 5,080 maximum-sized slots, realized as 6,474 variable-sized slots / 18.89 GiB.
Total expert storage is about 71.7 GiB. The 26.8 GiB PLE table is faulted into
RAM but its lock is refused by the service's 8 MiB memlock limit. KV data beyond
32K cells per attention layer streams from 3.09 GiB of pinned RAM.

Prompt scratch space borrows GPU expert-cache slots. Host and GPU copies share
the same physical RAM on this APU. Logs show expert file reads and non-GPU
execution during generation. This makes residency a concrete experimental
target; it is not yet proof that residency explains the full decode deficit.

The all-expert GPU layout removes `--resident-budget-gib 38`, sets
`--expert-cache auto`, adds `--mmap-experts --no-prefill-borrow`, and changes
`--ple-io ram` first to `direct`, then independently to `mmap`. The automatic
cache realized all 24,576 experts / 71.73 GiB, with no host expert arena and
about 25 GiB OS memory available during loading. Context and KV settings were
unchanged. Startup took about 90 seconds.

Direct PLE was slower overall despite eliminating expert misses. Changing
only PLE access to mmap improved both measures: 1,223.6 prefill / 42.2 generation
at 16K. No expert-file reads occurred during that measured request. The first
small warm-up had a 6.6-second prefill, so cold lookup-table access still matters.
These are single screening runs; larger-context validation and a generation
profile are next. The memory-layout bundle is not evidence for attributing the
whole gain to any one of cache size, arena removal or prompt-buffer ownership.

Do not simply increase the pinned host budget: driver accounting and duplicate
storage can exhaust the shared pool. The PLE table is still used in every arm;
`--no-ple` is not a performance option for a real deployment.

## Generation profile and rejected experiments

With the all-expert GPU / mmap PLE layout, `STRATA_DECODE_TIMING=1` and
`STRATA_VERIFY_PROFILE=1` measured 229 generation windows after a cold 16K
prompt, averaging 2.24 emitted tokens/window:

| Wall-time component | ms/window | Share |
|---|---:|---:|
| Main-model verification | 49.80 | 84.8% |
| Drafting | 8.94 | 15.2% |
| Other, commit/emission, adaptation | about 0.02 | below 0.1% |

CPU expert work, PCIe expert work and adaptive swaps were zero in this layout.
The GPU event profile reported 49.62 ms/window (cumulative over 230 windows),
with expert matrix operations at 17.70 ms: about 35.7% of profiled GPU work.
This is not the same denominator as total request wall time. The profiler
slows generation: this instrumented run reached 38.0 tok/s, versus 42.2 in the
earlier uninstrumented screen. Do not quote the instrumented result as a new
speed baseline.

Adding `--mtp-q4 all` quantizes only the draft projections/head. Its first
16K run stalled for several seconds around output token 238, resumed without
an engine restart, and averaged 24.3 tok/s. An SVM restore workqueue warning
appeared around the same time; this is correlation, not an established cause.
A repeat without the stall reached 41.4 tok/s. Request-local draft confidence
floors 0.7 and 0.3 reached 41.0 and 40.7 respectively, versus 0.5's 41.4. These
single screens show no benefit over the original drafter's 42.2; neither the
smaller drafter nor a new confidence floor is selected.

The telemetry and unsuccessful arms are retained alongside successful ones.
The main-model quant, context and user-facing sampling settings were unchanged.
`--spec-min-p` in the benchmark sets only a request-local proposal-confidence
threshold; it does not change the request's sampling temperature.

Full GPU KV residency completed 64K and 128K requests as recorded above.
Its first 16K request also stalled
and measured 1,092.7 prefill / 27.1 generation. The new layout is therefore
not yet a stable deployment recommendation. A relevant existing safeguard is
`STRATA_VERIFY_EARLY_PLE_FLAG=1`: the release-pinned verifier documents raising
the lookup-table-ready flag before *every* graph launch, whereas HIP normally
does so only for each graph's first launch. Testing it may distinguish the
lookup/GPU wait interaction from ordinary compute cost; no fix is claimed yet.

With that safeguard, the first 16K request completed at 1,224.7 / 40.6 tok/s
without a generation stall, although the tiny warm-up still took 7.35 seconds
in prefill. Adding the existing `STRATA_EXPERT_V2K=1` kernel gave 1,020.2 / 41.8;
the small generation difference is insufficient to select it from one run.
The initial stall is not proven fixed.

### Protocol correction for subsequent comparisons

Version 1's tiny warm-up plus a random hexadecimal nonce ranged across the
engine's 64-token short-read boundary. In particular the V2K arm warmed with
64 input tokens, taking a different prompt path from the preceding arm's 67.
This confounds small first-request prefill differences. The source-text probe
itself still used fresh nonces and reported zero prompt reuse.

Protocol version 2 uses the same fixed 151-token warm-up for each fresh load,
above that threshold. The measured request retains its fresh nonce. A new
control and F16 prompt-kernel comparison use this corrected protocol; old
results are preserved under version 1, not silently rewritten.

### Last results before the reboot pause

| Protocol v2 configuration | Actual input | Prefill tok/s | Generation tok/s |
|---|---:|---:|---:|
| All experts + KV on GPU, mmap PLE, early PLE flag | 16,395 | 815.4 | 41.4 |
| Same, `STRATA_PF_F16=1` | 16,394 | 1,390.5 | 41.8 |
| Same F16, 64K | 65,547 | 1,411.7 | 37.9 |

All three generated 512 tokens and reused zero prompt tokens. The control
contained a several-second pause during prefill; do not attribute its entire
gap to F16. F16's 151-token warm-up also paused (8.772 seconds). The F16 128K
request was deliberately cancelled for the user's reboot; it is incomplete,
not a failed correctness or throughput result. F16 changes rounding and has
not received model-quality validation here. No candidate was promoted.

The new kernel-memory sampler records a stronger explanation for the pauses:
the inference process's KFD `evicted_ms` reached 12,433 ms while background
compaction scanned about 25.8 million pages and successful page migrations
rose sharply. The vision process was also evicted. This establishes actual
GPU queue eviction overlapping memory compaction, but does not yet prove
which migration policy triggered it. NUMA balancing is already zero on this
single-node machine. `vm.compaction_proactiveness` is still its original 20.

After reboot, repeat the same F16 configuration with the original host policy
first. If pauses recur, compare a fresh load with
`sudo sysctl -w vm.compaction_proactiveness=0`, recording/restoring the original
20 as appropriate. This is a proposed reversible experiment, not a change
already made. [Kernel documentation](https://docs.kernel.org/admin-guide/sysctl/vm.html#compaction-proactiveness)
describes both the background migration and the potential latency spikes.

Generation's 50–60 tok/s target remains unmet. The public workload subset in
`benchmarks/strata-generation.py` is prepared and syntax-checked but has **not
been run**. Tool-call investigation remains parked.

## Clean-boot comparison and remaining stalls

Boot ID `35917f23-eead-456d-8ed2-d368f0e68f36`, kernel taint zero, original
`vm.compaction_proactiveness=20`, `kernel.numa_balancing=0`. Only the same F16
candidate was loaded. It took 88.04 seconds; the 151-token warm-up prefill
completed in 631 ms.

| Cold input | Prefill tok/s | Generation tok/s | Reused / output tokens |
|---:|---:|---:|---:|
| 16,393 | 1,074.3 | 40.3 | 0 / 512 |
| 65,550 | 1,417.5 | 40.9 | 0 / 512 |
| 131,075 | 1,363.2 | 38.9 | 0 / 512 |

KFD reported 2.801 seconds evicted at readiness and 7.097 seconds during the
first 16K prefill. Successful page migrations reached 1,416,691 while daemon
compaction scanned 2,924,729 pages. This reproduces the pauses after reboot;
stale processes from earlier installations cannot be their sole explanation.
A fresh identical arm with temporary `vm.compaction_proactiveness=0` completed:

| Cold input | Prefill tok/s | Generation tok/s | Reused / output tokens |
|---:|---:|---:|---:|
| 16,392 | 1,388.5 | 42.5 | 0 / 512 |
| 65,551 | 1,397.5 | 41.4 | 0 / 512 |
| 131,072 | 1,350.2 | 37.5 | 0 / 512 |

After readiness, inference-process eviction increased by only 130 ms, versus
4,339 ms with policy 20. Successful page migrations after readiness fell from
1,186,367 to 4,780. Eviction during loading still occurred (2.010 seconds by
readiness). Large-prompt throughput differed by approximately 1–2%, so this
supports a reduction in pauses, not a compute-speed gain. The runs occurred
sequentially in different memory/cache states; an interleaved repeat is needed
before claiming a durable fix. The setting remains temporary, not persisted.
The next arm profiles prefill on this configuration; generation tuning is
parked until the user's prioritized prefill work is finished.

**Later counterexample:** with the same temporary zero policy, the chunked-GDN
arm's 151-token warm-up stalled again: 2.647 seconds prefill and 7.152 seconds
generation. KFD eviction rose from 4.301 seconds at readiness to 13.921 seconds,
while successful page migrations rose from 2.787 million to 4.178 million.
The long measured request then ran without that pause. This refutes treating
`compaction_proactiveness=0` alone as a fix: allocation-driven background/direct
compaction is still possible. No persistent change or stability claim is made.

### Public generation subset and sampling caveat

`benchmarks/strata-generation.py` completed its three public cases on the
clean-boot F16 candidate: 49.8 tok/s for the short prose question, 45.2 for the
16,347-token document (1,476.1 tok/s cold prefill), and 57.7 for the LRU code
prompt. Each generated 512 tokens. This is a custom subset, not the official
full Strata protocol, and does not establish 50–60 tok/s on long agent turns.

The server source also establishes an inherited setting omitted from the
initial benchmark report: non-thinking Flash-Next requests default to
`presence_penalty=1.5`. The private config has no sampling block and
`GET /settings` returned no shared defaults. Our temperature-zero probes did
not override that penalty. OpenClaw explicitly sends zero. Existing results
remain valid for their actual requests but are not sampling-matched OpenClaw
results. Both probes now accept an explicit `--presence-penalty`; a comparison
with zero is deferred until after the prioritized prefill work. Historical
measurements are not overwritten.

## Profile of the faster prefill path

With `STRATA_PREFILL_TIMING=1` and `STRATA_DRAFT_TIMING=1`, the F16 candidate
processed a cold 65,552-token request at 1,380.7 tok/s (47.477 seconds).
The prompt-path timer covers 65,545 tokens and reports a 47.319-second GPU
timeline. Event intervals include waiting gaps; this is not a memory-bandwidth
or occupancy counter capture. The 16-token completion is only a termination
check, not a generation benchmark.

| Aggregate on that timeline | Time | Share |
|---|---:|---:|
| Routed expert computation | 11.796 s | 24.9% |
| GDN projections, convolution/gates, recurrence and output | 11.319 s | 23.9% |
| Hyper-connection read/write | 9.904 s | 20.9% |
| QSA projections, selection, attention and preparation | 9.515 s | 20.1% |
| Remaining routing/shared, combine, lookup and setup | about 4.785 s | 10.1% |

The fused-expert interval is labelled `gemm gate/up` but includes the fused
expert down work; the tiny separate `gemm down` entry is not its total cost.
GDN recurrence alone is 3.163 seconds (6.7%), actual QSA attention 4.745 seconds
(10.0%), HC write 4.026 seconds (8.5%). Host grouping is 6 ms, below 0.02%.
CPU expert staging is zero. Draft-layer work after chunks is 379 ms. Do not
optimize host grouping or treat the full old attention share as current.

Next experiments keep every model/context setting fixed: first a 32K chunk
versus the current 16K, then the existing chunked GDN kernel independently.
The latter changes recurrence rounding and needs quality validation before
promotion. Its theoretical gain from a 1.6x recurrence speedup here is about
2.6% overall, not 60%. The broader profile also gives concrete targets for
further kernel work if the packaged switches stop paying.

### Larger-chunk screen: not selected

Changing only `--prefill 16384` to `32768` with automatic expert-cache sizing
reached 1,375.0 tok/s on 65,546 uncached input tokens. Automatic sizing reduced
the GPU expert cache from 24,576 to 23,083 slots (67.38 GiB). The measured
request read 9.502 GB of expert blobs and caused 1.094 GB of OS storage reads.
It is therefore a combined chunk/residency outcome, not an isolated tile-size
comparison. It showed no gain and is not selected. OS memory available during
prefill was approximately 18.5 GiB; a later fixed-residency comparison can
hold all 24,576 slots explicitly, with memory telemetry retained.

The independent screen kept the 16K/all-resident layout and changed only
`STRATA_GDN_CHUNKED=1`: 65,552 uncached tokens at 1,404.5 tok/s and 131,075 at
1,363.1. Those differences are within the observed control spread, so this
rounding-changing path is not selected. Both generated 16 tokens only; their
reported decode rates are not sustained-speed comparisons. `STRATA_PF_BATCH=512` is not a candidate for this packaged
HIP build: `kBatchRoom` is capped at 128 in `moe_fused.hpp`, so that setting
would not perform the hoped-for larger expert launch.

The follow-up explicitly held `--expert-cache 24576` at 32K chunks. It loaded
all experts, completed 65,547 uncached input tokens at **1,392.5 tok/s**, and
left about 14.3 GiB OS memory available during prefill. This resolves the
residency confounder and shows no useful advantage over 16K. The automatic
conversation-cache budget also shrank from 6,912 to 4,864 MiB due to the larger
scratch buffers. That cache was not reused in the cold request. Keep 16K unless
the following 8K screen establishes a better tradeoff.

## Operational state during measurements

The production private listener at `100.96.8.54:8083` is unavailable.
During the comparisons the service ran isolated arms at `127.0.0.1:8084`, using a runtime
drop-in at `$XDG_RUNTIME_DIR/systemd/user/strata-flash-next.service.d/90-benchmark.conf`.
The override was removed for the reboot pause, then recreated for the resumed
comparisons. Boot startup remains disabled. Persistent production configuration is preserved, but it is
the original slow installer layout. Do not enable it blindly on boot; finish
the clean-boot comparison and select a validated configuration first.

No OpenClaw restart, Mac reboot, GPU driver reload, model download or engine
source patch was performed for these comparisons. Old 27B and Qwen3.6 remain
stopped, disabled and retained.

Local private artifacts: `~/.cache/strata-evaluation-20261107/performance/`.
Files ending in `.private.json` contain the API key and must not be published.

## Upstream references and limits

- [Halo guide](https://github.com/Niko1221/Strata/blob/main/docs/STRIX_HALO.md):
  the historical Q4_K_XL 128K result is 1,211 prefill and **42.64 generation**,
  not 50–60 generation at 128K. Its all-resident setup and older engine differ
  from our initial deployment. The 50–60 goal at long context is additional work.
- [PLE memlock issue](https://github.com/Niko1221/Strata/issues/4671): explains
  the refused lock. Its reported speedup was measured on a discrete NVIDIA GPU;
  it is not an established speedup on this Halo.
- [Release-pinned architecture defaults](https://github.com/Niko1221/Strata/blob/v0.2.11/include/strata/core/arch_defaults.hpp)
  and [engine configuration](https://github.com/Niko1221/Strata/blob/v0.2.11/src/program/generate.cpp).
