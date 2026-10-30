# Architecture and decisions

## Request path

```text
OpenAI-compatible client
        |
        v
127.0.0.1:8080 coalescing proxy
        |
        v
127.0.0.1:8081 router
        |
        +-- qwen3.8-27b-q4-fast       (loads at startup)
        |
        `-- qwen3.8-27b-q5-quality    (loads on request)
                 |
                 +-- shared DFlash2 Q4_K_M drafter
                 +-- shared F16 vision projector
                 `-- one 245,760-token Q8_0 KV context
```

`--models-max 1` ensures that only one 27B target is resident. This avoids
allocating two large target models and two full-length KV arenas at once while
still making both qualities available behind one endpoint.

## Why Q4 and Q5

UD-Q4_K_XL is the default because it provides the best measured latency for
interactive and agent traffic. UD-Q5_K_XL costs additional storage, load time
and decode latency but is retained for requests where a smaller quantization
error is worth that cost. A real OpenClaw evaluation will determine practical
routing criteria; the current names describe intent rather than a proven
quality boundary.

## Why DFlash2 width 4

The local width sweep tested 2, 4 and 6 on both targets. Width 4 won on both.
At width 2 the percentage acceptance was higher, but too few candidates were
verified per step. At width 6, lower acceptance and additional verification
work outweighed the extra candidates. See [BENCHMARKS.md](BENCHMARKS.md).

## Why Q8 target KV

The configured window is close to the model's native 262,144-token context.
Q8_0 K/V substantially reduces cache bandwidth and capacity compared with F16
while being a conservative quality choice. The DFlash draft KV remains F16 by
default. Because this machine has ample memory, a draft-Q8 test is only useful
if it improves throughput; it is not currently deployed.

## Why one slot

The production workload can issue simultaneous OpenClaw requests, but local
measurement showed that admitting more of them to the GPU at once is worse on
this Vulkan/DFlash2 stack. With four distinct cold 9,263-token prompts, one
slot returned the first result in 25.1 seconds and drained all four in 100.9
seconds. Two slots took 52.7 and 108.8 seconds respectively; four took 102.6
and 107.1 seconds. Multi-slot runs also reduced reported decode throughput
from 18.8 tok/s to 3.6 and 2.6 tok/s on average.

The deployed one-slot setting gives predictable queueing and the best observed
first-response and total-drain latency. The front proxy still collapses exact
concurrent duplicates to one generation, while the 24 GiB prompt cache retains
reusable prefixes across independent calls. Unified KV remains enabled because
that is the exact configuration used in the winning controlled run.

## Exact-request coalescing

The public endpoint is a dependency-free streaming reverse proxy. The first
copy of a byte-identical inference request opens the upstream generation;
concurrent copies subscribe to the same response stream. Authentication and
tenant headers are part of the identity key. The proxy deliberately drops the
entry as soon as the upstream response finishes, so later intentional repeats
are generated independently.

This is primarily retry protection. Prefix caching still handles requests that
share a long prefix but differ in their final messages.

The `X-Qwen-Coalescer` response header reports `leader` or `follower`. This
layer deduplicates model inference only; clients remain responsible for making
downstream tool execution idempotent.

## Why Vulkan first

The selected runtime is a Strix Halo-specific llama.cpp Vulkan build with a
bundled and validated RADV stack. It requires no host ROCm SDK and performed
well immediately. This is not a claim that Vulkan universally beats ROCm:
decode, prefill, model architecture, quantization and speculative verification
exercise different kernels. A same-commit ROCm sidecar comparison remains on
the roadmap.

## Reasoning and tool use

The server uses llama.cpp's Jinja template support, automatic reasoning mode,
DeepSeek-compatible `reasoning_content` extraction, and
`--reasoning-preserve`. The latter retains reasoning across the full tool-turn
history when the template supports it.

Sampling is a client policy. Tool traffic currently starts at temperature 0.2,
top-p 0.95, top-k 20 and min-p 0. This keeps direct interactive clients free to
choose a more creative profile.

## Vision

The matching F16 multimodal projector is loaded for both targets and offloaded
to the GPU. Dynamic-resolution images receive a minimum of 1,024 image tokens.
That floor passed basic photo and generated-card checks; dense screenshots,
OCR and chart tasks remain to be benchmarked.

## Caching

Prompt caching, idle-slot caching and a 24 GiB host-RAM cache are explicitly
enabled. Live measurements showed an OpenClaw prefix snapshot consuming about
6 GiB, so the runtime default of 8 GiB repeatedly evicted the previous entry.
The larger cache should retain several such prefixes. `--cache-reuse` for
shifted chunks after compaction remains an untested optional experiment.
