# ROCm and vLLM investigation

This is a research backend, not the current production path. Production remains
the llama.cpp Vulkan deployment documented elsewhere in this repository. Build
ROCm/vLLM beside it, use a separate API port, and retain immediate rollback to
Vulkan.

## Why investigate it

Qwen3.8-27B NVFP4 with DFlash2 under vLLM on one NVIDIA GB10 produced an
observed user experience around 39--45 tok/s. That felt substantially more
interactive than the current 18--25 tok/s Vulkan range. The AMD counterpart is
not NVFP4: the interesting route is an AMD-oriented MXFP4/MXFP6 target, a BF16
DFlash2 drafter and tuned ROCm kernels.

The comparison must answer two different questions:

1. llama.cpp Vulkan versus llama.cpp HIP/ROCm with the same GGUF artifacts,
   isolating the backend.
2. The complete Vulkan/GGUF stack versus vLLM/ROCm with an appropriate
   Hugging Face quant, comparing deployable outcomes rather than one backend
   in isolation.

## Upstream state on 2026-10-30

- AMD documents native Strix Halo `gfx1151` support on Ubuntu 26.04 with a
  sufficiently new kernel. This machine runs Ubuntu 26.04.1 and kernel 7.0.
- vLLM lists Ryzen AI MAX / `gfx1151` as a ROCm target and publishes ROCm
  wheels and images.
- DFlash2 shipped in vLLM 0.28. The Qwen3.8 recipe attaches
  `incoai/Qwen3.8-27B-DFlash2` with seven speculative tokens.
- vLLM's ROCm platform contains explicit `gfx1151` handling.
- ROCm DFlash2 performance work is active upstream. Optimised AITER paths are
  strongest on MI-series/CDNA hardware; RDNA 3.5 can fall back to less tuned
  paths.
- AMD-oriented MXFP4/MXFP6 plus DFlash2 artifacts exist, but published support
  is early and has not established a production recipe for this exact APU.
- Prefix caching and draft-attention backend interactions have caused DFlash2
  acceptance regressions in some ROCm configurations. Prefix reuse must be
  validated explicitly rather than assumed.

## Local prerequisites and current state

The machine has a 2 TB NVMe. Its root LV was initially only 100 GiB; it has now
been expanded online to 1.60 TiB, leaving about 266 GiB unallocated in LVM.
Storage is no longer a blocker.

ROCm and a container runtime are not currently installed. The kernel exposes
`/dev/kfd` and `/dev/dri/renderD128`, but the service user should be placed in
the `render` and `video` groups for predictable container access.

The current TTM page limit is 15,112,930 pages, approximately 57.65 GiB. AMD
recommends a small firmware carve-out and a larger shared TTM/GTT allocation on
Strix Halo. Set approximately 90--100 GiB for the experiment and reboot before
attempting large BF16 or long-context vLLM allocations.

## Staged bring-up

1. Preserve the Vulkan service, configuration and benchmark baseline.
2. Install a pinned official vLLM ROCm image or wheel in an isolated
   environment. Start with the current stable ROCm path; use a source/TheRock
   build targeted explicitly at `gfx1151` only if the published artifact lacks
   the required kernels.
3. Verify HIP/PyTorch and memory allocation with a small model.
4. Prove stock Qwen3.8-27B correctness at a 64K context before attempting the
   performance quant.
5. Enable reasoning and tools with:

   ```text
   --reasoning-parser qwen3
   --enable-auto-tool-choice
   --tool-call-parser qwen3_coder
   ```

6. Attach DFlash2 with an initial seven-token budget:

   ```json
   {"method":"dflash","model":"incoai/Qwen3.8-27B-DFlash2","num_speculative_tokens":7}
   ```

7. Start with eager execution if graph capture is unstable. Test graph capture
   only after the eager baseline is correct.
8. Validate text, tools and vision before connecting OpenClaw.
9. Test prefix caching off and on while recording accepted/drafted tokens.
10. Increase context from 64K toward 245,760 only after stable memory and
    latency measurements.
11. Serve the candidate on a separate port and route traffic explicitly. Never
    overwrite the Vulkan runtime in place.

## Comparison matrix

Hold prompts, sampler, output limit and seeds constant where the engine permits.
Measure:

- Cold prefill and warm-prefix time to first token at 8K, 32K, 50K and 128K
- Single-stream decode and DFlash acceptance
- Exact duplicate requests
- Independent concurrent sessions and aggregate output throughput
- Tool selection, argument validity and multi-tool completion
- Vision correctness and image preprocessing latency
- Resident memory, peak mapped memory, power and temperature
- Restart behaviour and cold-prefix cost

vLLM offers continuous batching and in-process prefix caching, but it does not
provide the same durable llama.cpp slot checkpoint used by the current
deployment. Treat restart recovery as a separate product-level comparison.

## Success criteria

The vLLM route is worth promoting only if it remains correct and either:

- approaches the 39--45 tok/s single-stream responsiveness target, or
- materially improves aggregate concurrent OpenClaw throughput without making
  individual first-token latency unacceptable.

A generic fallback path that merely loads is not a win. If MXFP4 kernels fall
back to unquantized or poorly tuned operations, performance can be below the
Vulkan baseline despite the more sophisticated serving engine.

## Primary references

- [AMD Strix Halo system optimisation](https://rocm.docs.amd.com/en/docs-7.2.0/how-to/system-optimization/strixhalo.html)
- [vLLM GPU and ROCm installation](https://docs.vllm.ai/en/latest/getting_started/installation/gpu/)
- [vLLM Qwen3.8-27B recipe](https://recipes.vllm.ai/Qwen/Qwen3.8-27B)
- [vLLM DFlash2 ROCm performance RFC](https://github.com/vllm-project/vllm/issues/61761)
- [DFlash2 ROCm attention-backend issue](https://github.com/vllm-project/vllm/issues/53323)
- [AEON Qwen3.8 DFlash2 model card](https://huggingface.co/AEON-7/AEON-DFlash2-Qwen3.8-27B)
