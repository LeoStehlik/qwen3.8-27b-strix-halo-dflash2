# Sources and references

## Model and runtime sources

- [Qwen/Qwen3.8-27B model card](https://huggingface.co/Qwen/Qwen3.8-27B)
- [Unsloth Qwen3.8-27B GGUF repository](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF)
- [incoai Qwen3.8-27B DFlash2 GGUF](https://huggingface.co/incoai/Qwen3.8-27B-DFlash2-GGUF)
- [Strix Halo llama.cpp portable runtime](https://github.com/Nathanw1014/strix-halo-llamacpp)
- [llama.cpp speculative decoding documentation](https://github.com/ggml-org/llama.cpp/blob/master/docs/speculative.md)

Exact revisions, sizes and checksums are pinned in [INSTALL.md](INSTALL.md) and
the download scripts.

## Tool calling and agent integration

- [Qwen function calling guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/framework/function_call.md)
- [OpenClaw model configuration](https://docs.openclaw.ai/gateway/config-agents/models)
- [OpenClaw local model guidance](https://docs.openclaw.ai/gateway/local-models)

## Backend and Strix Halo context

- [“I tuned llama.cpp”](https://medium.com/@bkpaine1/i-tuned-llama-cpp-33d68b1c851d), the article that prompted a more careful discussion of workload-dependent Vulkan/ROCm results
- [llama.cpp Strix Halo Vulkan performance discussion](https://github.com/ggml-org/llama.cpp/discussions/10879)
- [Known-good Strix Halo ROCm/Vulkan discussion](https://github.com/ggml-org/llama.cpp/discussions/20856)

Community benchmark reports are useful hypotheses, not substitutes for a
same-model, same-commit test on the local machine.
