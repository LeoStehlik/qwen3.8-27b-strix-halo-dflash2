# Architecture and decisions

## Request path

```text
OpenAI-compatible client
        |
        v
127.0.0.1:8080 router
        |
        +-- qwen3.8-27b-q4-fast       (loads at startup)
        |
        `-- qwen3.8-27b-q5-quality    (loads on request)
                 |
                 +-- shared DFlash2 Q4_K_M drafter
                 +-- shared F16 vision projector
                 `-- one 245,760-token slot, Q8_0 target KV
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

The target workload is a single interactive agent. A second active slot would
divide the context budget and can reduce DFlash acceptance under concurrent
sequences. One slot gives predictable latency and preserves the full window.

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

The runtime enables prompt caching. This llama.cpp build also defaults to an
8 GiB RAM prompt cache, context checkpoints and idle-slot caching. Exact-prefix
reuse therefore works without an additional flag. `--cache-reuse` for shifted
chunks after compaction is an untested optional experiment.
