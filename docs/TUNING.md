# Tuning cookbook and roadmap

Change one factor at a time, warm the model before recording results, and keep
the prompt, token limit, seed and sampler fixed. Record both throughput and
draft acceptance; neither metric is sufficient alone.

## Current production settings

```ini
ctx-size = 245760
parallel = 1
batch-size = 2048
ubatch-size = 2048
cache-type-k = q8_0
cache-type-v = q8_0
threads = 16
threads-batch = 16
spec-draft-n-max = 4
spec-draft-n-min = 0
flash-attn = on
```

The draft KV types are not specified, so the runtime default is F16.

## 1. OpenClaw evaluation

This will be run inside OpenClaw using its real prompts and tools. Compare Q4
and Q5 at temperatures 0.1, 0.2 and 0.3. Record:

- Correct tool selection and valid arguments
- Unnecessary tool calls
- Multi-tool completion rate
- Behaviour around compaction
- Time to first token and decode speed
- DFlash acceptance
- Human preference / task correctness

## 2. DFlash probability sweep

Width 4 is fixed unless a runtime or draft model changes. Test the smaller
matrix:

```text
spec-draft-p-split: 0.05, 0.10, 0.20
spec-draft-p-min:   0.00, 0.05, 0.10
```

Use several workload shapes: prose, code, structured JSON/tool calls and
reasoning. A candidate setting must improve the aggregate and avoid a severe
regression on any important class.

## 3. Draft KV F16 versus Q8

Memory saving is not the objective on this machine. Compare draft F16 and Q8_0
only for throughput at empty, 32K and 128K context depth. Quantized KV reduces
bandwidth but adds dequantization work, so the winner may change with depth.

Measure:

- End-to-end decode tok/s
- Draft acceptance
- Draft generation time
- Target verification time

Keep F16 unless Q8 gives a repeatable gain above normal run-to-run noise. The
target verifies every draft, so speculative decoding remains output-correct;
draft quantization can nevertheless alter acceptance and performance.

## 4. Prefill sweep

Test context depths 8K, 32K and 128K with:

```text
ubatch:  512, 1024, 2048
threads: 8, 16, 32
```

Only test logical batch 4096 after the ubatch sweep. Record prompt tok/s,
time-to-first-token, peak memory and decode speed immediately after prefill.
Large ubatches can improve GPU utilisation but also increase temporary memory
and scheduling cost.

## 5. Vision suite

Use a stable local fixture set:

- Dense desktop or browser screenshot
- Small-font document page
- Chart requiring value extraction
- Natural photograph
- Multiple-image comparison

Compare image-token floors 512, 1024 and 2048. Record correctness, visual token
count, prompt time and total latency. The existing 1024 floor is provisional.

## 6. Vulkan versus ROCm

Build a separate ROCm runtime from the same llama.cpp source commit. Do not
replace the working Vulkan service during the experiment. Use the same model
hashes, KV types, context, prompts, DFlash parameters and power state.

Compare separately:

- Short and long prefill
- Decode without speculation
- Decode with DFlash2
- Vision prefill
- Cold load and steady-state power

Backend conclusions must name the phase and workload. “Vulkan always wins” and
“ROCm always wins” are both too broad for this system.

## 7. Prompt-cache reuse

Exact-prefix caching and an 8 GiB RAM prompt cache are already enabled by
runtime defaults. After OpenClaw compaction is operational, test
`--cache-reuse 256` and `512` for shifted common chunks. Retain it only if it
improves post-compaction time to first token without incorrect reuse.

## Power policy

The GPU currently uses the kernel's `auto` DPM policy. Do not permanently lock
high clocks without measuring wall-power, temperature and idle behaviour. If a
performance policy is tested, apply it only for the service lifetime and
restore `auto` when the service stops.

## When to fine-tune weights

Do not begin LoRA/QLoRA work merely to make sampling feel different. First
collect repeated failures from the real OpenClaw evaluation. Weight fine-tuning
is justified only when prompt/template/sampling changes cannot correct a
well-defined behaviour and the evaluation set can measure improvement without
regression.
