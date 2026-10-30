# Tuning cookbook and roadmap

Change one factor at a time, warm the model before recording results, and keep
the prompt, token limit, seed and sampler fixed. Record both throughput and
draft acceptance; neither metric is sufficient alone.

## Current production settings

```ini
ctx-size = 245760
parallel = 1
kv-unified = true
batch-size = 2048
ubatch-size = 2048
cache-type-k = q8_0
cache-type-v = q8_0
cache-prompt = true
cache-ram = 24576
cache-idle-slots = true
threads = 16
threads-batch = 16
spec-draft-n-max = 4
spec-draft-n-min = 0
flash-attn = on
```

The draft KV types are not specified, so the runtime default is F16.

The production runtime is the checkpoint-persistence candidate based on
llama.cpp commit `a82001bd3`, with bundled Mesa RADV 26.2.4. Its Strix Halo
Vulkan path already includes GQA-folded speculative verification, dense
matrix-multiply tuning and graph reuse. The remaining work is therefore a
measured search for smaller gains rather than a stock-runtime tuning exercise.

## 1. OpenClaw evaluation

The first real Francis/OpenClaw tool session is complete. Its 152,781-token
cold request took 9m32s; ten prefix-cached turns had a 47.5-second median and
all completed within two minutes. See
[OPENCLAW-LIVE-TRACE.md](OPENCLAW-LIVE-TRACE.md).

The next evaluation must reduce cold input below 30K tokens by measuring prompt
components, deferring non-core tool schemas and avoiding bulk memory hydration.
Then compare Q4 and Q5 at temperatures 0.1, 0.2 and 0.3. Continue to record:

- Correct tool selection and valid arguments
- Unnecessary tool calls
- Multi-tool completion rate
- Behaviour around compaction
- Time to first token and decode speed
- DFlash acceptance
- Human preference / task correctness

## 2. Decode-throughput target and live evidence

The controlled short-prompt Q4 result is 24.87 tok/s and prompt-dependent
bursts have reached about 30.7 tok/s. Real OpenClaw traffic at roughly 43K--50K
live context has recently ranged from 17.25 to 24.38 tok/s. One long sanitized
turn generated 2,668 tokens at 17.97 tok/s with 49.61% DFlash acceptance and a
mean accepted length of 2.98. A short highly predictable turn reached 24.38
tok/s with 94.12% acceptance. High acceptance alone therefore does not close
the entire gap; target verification, Vulkan scheduling and context depth also
matter.

Use 30 tok/s sustained as the practical tuning target and 35 tok/s as a stretch
target. The 39--45 tok/s Qwen3.8-27B NVFP4 plus DFlash2 experience observed on
one NVIDIA GB10 is the responsiveness reference, not a like-for-like benchmark:
that path uses vLLM and native Blackwell FP4 kernels rather than GGUF Q4 and
Vulkan. Do not promise 50 tok/s from configuration tuning of this dense 27B
target.

The deployment deliberately retains a 27B intelligence floor. A 12B--14B
speed tier is not planned because agent reasoning and reliable tool use are
more important than an isolated token-rate number.

## 3. Vulkan and host scheduling A/B tests

The candidate launcher currently exports `GGML_VK_FA_WAVE32=0`, overriding the
runtime's newer safe Wave32 heuristic. The source default only narrows the
subgroup when the attention head geometry can do so without increasing the
per-lane output state. Test `0` versus `1` first; do not force diagnostic mode
`2` in production.

During the 17.97 tok/s live turn, GPU utilisation was mostly 62--74%, GPU clock
was approximately 2.0--2.3 GHz against a 2.9 GHz top state, and temperature was
only 62 C. This was not a thermal limit. Test these independently:

```text
GGML_VK_FA_WAVE32:       0, 1
GPU DPM policy:          auto, high
CPU EPP:                 balance_performance, performance
generation threads:      8, 12, 16
poll level:              50, 100
CPU placement:           scheduler default, strict physical CPUs 0-15
process priority:        normal, high
```

Record idle power and restore the normal policy after each run. Do not combine
settings until their individual effects are known. Logical and physical batch
size primarily affect prefill; they are unlikely to explain a large sustained
decode gain by themselves.

## 4. DFlash2 width and acceptance

The controlled width sweep selected width 4 over widths 2 and 6. Recheck widths
3, 4 and 5 using OpenClaw-like prose, code, structured tool JSON and reasoning
at empty and approximately 50K context. Width 4 aligns well with the fork's
GQA-folded verification shape, so retain it unless the representative aggregate
shows a repeatable improvement.

```text
spec-draft-n-max: 3, 4, 5
```

Do **not** spend time sweeping `spec-draft-p-split` or `spec-draft-p-min` for
this DFlash2 selector model. Inspection of the pinned implementation shows that
DFlash2 consumes its selector lattice directly: `p_split` is not used by this
path, while confidence-based `p_min` truncation is a DSpark feature. Backend
sampling is also bypassed for DFlash2. The earlier probability-sweep plan was
incorrect and has been removed.

Compare client temperatures 0.0, 0.1, 0.2 and 0.3. Lower temperature may
increase acceptance and is already compatible with the tool-use preference,
but correctness and unnecessary tool calls remain the deciding metrics.

## 5. Draft precision: weights and KV

Memory saving is not the objective on this machine. Compare draft F16 and Q8_0
KV for throughput at empty, 32K and 128K context depth. Also obtain or convert
Q8 and F16/BF16 versions of the DFlash2 drafter and compare them with the
current Q4_K_M weights. Higher precision costs bandwidth but can win end to end
if it raises target acceptance enough.

Measure:

- End-to-end decode tok/s
- Draft acceptance
- Draft generation time
- Target verification time

Keep F16 unless Q8 gives a repeatable gain above normal run-to-run noise. The
target verifies every draft, so speculative decoding remains output-correct;
draft quantization can nevertheless alter acceptance and performance.

If these tests plateau, the deeper route is a target- and workload-specific
DFlash2 drafter trained against the exact Q4 target, low-temperature sampler,
Qwen tool syntax and sanitized OpenClaw-like trajectories. This can improve
acceptance without changing target-model output, but it is a training project,
not a server flag.

## 6. Target KV and prefill sweep

At approximately 50K and 128K actual context, compare target KV `q8_0`, `q4_0`
and `iq4_nl`. Quantized KV may reduce long-context attention bandwidth, but a
candidate must pass text, tool and vision quality checks. Allocating a 245,760
token capacity does not itself make every token slow; the live populated depth
is the relevant decode cost.

Test context depths 8K, 32K and 128K with:

```text
ubatch:  512, 1024, 2048
threads: 8, 16, 32
```

Only test logical batch 4096 after the ubatch sweep. Record prompt tok/s,
time-to-first-token, peak memory and decode speed immediately after prefill.
Large ubatches can improve GPU utilisation but also increase temporary memory
and scheduling cost.

## 7. Vision suite

Use a stable local fixture set:

- Dense desktop or browser screenshot
- Small-font document page
- Chart requiring value extraction
- Natural photograph
- Multiple-image comparison

Compare image-token floors 512, 1024 and 2048. Record correctness, visual token
count, prompt time and total latency. The existing 1024 floor is provisional.

## 8. Concurrent serving

The production default is one slot with DFlash2 enabled. A controlled four-
client comparison has already rejected two and four slots for this stack: both
first-result latency and total drain time were worse. Repeat that comparison
after a material runtime, backend or batching change; do not infer that more
slots improve useful concurrency.

Compare separately:

- Exact concurrent duplicates, which should coalesce to one upstream request
- Shared-prefix requests with different suffixes
- Independent sessions
- Aggregate throughput and per-request decode speed
- Median and p95 time to first token
- Tool-call correctness and DFlash acceptance

The Vulkan/DFlash2 route remains the selected production backend. A separate
ROCm/vLLM experiment is now planned, but must not replace this known-good path
until it wins the same-model correctness, tools, vision, prefix-reuse,
single-stream and concurrent-session tests. See [ROCM-VLLM.md](ROCM-VLLM.md).

Run a small distinct-request and duplicate-request pair with:

```bash
./concurrency-bench.py qwen3.8-27b-q4-fast --concurrency 2
./concurrency-bench.py qwen3.8-27b-q4-fast --concurrency 2 --duplicates
```

For the duplicate run, the coalescer metric delta should report one upstream
request and one follower.

For a repeat cold 1-versus-2-versus-4 slot comparison, use four clients and
change the label between configurations so no prior prefix can be reused.
First-completed latency matters alongside aggregate throughput:

```bash
./concurrency-bench.py qwen3.8-27b-q4-fast --concurrency 4 \
  --pad-words 8192 --max-tokens 64 --label slots-N
```

Use the mixed prefill/decode probe when sweeping physical batch size:

```bash
./prefill-fairness-bench.py qwen3.8-27b-q4-fast --long-words 32768 --label ubatch-512
```

Change the label between runs so the long request cannot reuse an earlier
prompt cache entry.

## 9. Prompt-cache reuse

Exact-prefix caching and a 24 GiB RAM prompt cache are explicitly enabled.
After OpenClaw compaction is operational, test
`--cache-reuse 256` and `512` for shifted common chunks. Retain it only if it
improves post-compaction time to first token without incorrect reuse.

## Power policy

The GPU currently uses the kernel's `auto` DPM policy. Do not permanently lock
high clocks without measuring wall-power, temperature and idle behaviour. If a
performance policy is tested, apply it only for the service lifetime and
restore `auto` when the service stops.

## Effective latency

Raw decode rate is not the only user-facing lever. The 2,668-token live turn
took 148.43 seconds to generate at 17.97 tok/s; even 30 tok/s would take about
89 seconds. Discord partial preview streaming, concise intermediate responses
and dynamic reasoning budgets can therefore improve usability more than a
small token-rate gain. Preserve deep reasoning for tasks that require it rather
than imposing one large reasoning budget on every tool turn.

## When to fine-tune weights

Do not begin LoRA/QLoRA work merely to make sampling feel different. First
collect repeated failures from the real OpenClaw evaluation. Weight fine-tuning
is justified only when prompt/template/sampling changes cannot correct a
well-defined behaviour and the evaluation set can measure improvement without
regression.
