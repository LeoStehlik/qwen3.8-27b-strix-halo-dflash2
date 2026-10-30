# Troubleshooting

## Service does not start

```bash
systemctl --user status qwen38-dflash2
journalctl --user -u qwen38-dflash2 -n 200 --no-pager
./scripts/verify-install.sh
```

The launcher exits immediately if any required model file is missing or empty.
Run the checksum verifier to detect an incomplete or wrong artifact.

## CPU fallback instead of Vulkan

```bash
./runtime/vulkan/llama-bench \
  -m models/Qwen3.8-27B-UD-Q4_K_XL.gguf \
  -ngl 99 -p 128 -n 8 -r 1
```

The output must identify the Radeon Vulkan backend. Invoke the top-level
`runtime/vulkan/llama-bench` wrapper, not `runtime/vulkan/bin/llama-bench`, so
the bundled RADV driver is selected.

Check `/dev/dri` permissions if no GPU appears. The login user normally needs
membership in the distribution's `render` and/or `video` group.

## Health is ready but the first request is slow

The router can answer health checks while its startup Q4 child is still loading.
Initial model load and a Q4/Q5 switch are expected to take several seconds.
Wait for the journal to report `model loaded` when scripting cold benchmarks.

## Q5 appears to hang immediately after restart

Avoid requesting the non-startup model while the Q4 startup child is still
loading. Wait for Q4 to report ready, or issue a small Q4 warm-up request before
switching. This was observed once during rapid automated restart/switch testing.

## Tool calls appear as text

Confirm all of the following:

- The request reaches `/v1/chat/completions`.
- `--jinja` is enabled.
- Tools use OpenAI function-tool schemas.
- Thinking is not accidentally disabled by the client template.
- `finish_reason` and `tool_calls` are inspected, not just message content.
- Tool arguments parse as JSON before execution.

Run `tool-temperature-test.py` to separate server/template behaviour from the
agent framework.

## Vision input is ignored

Check that the selected model metadata in the client declares image input and
that the request sends an OpenAI `image_url` content part. The server accepts
HTTP(S) URLs and base64 data URLs. Confirm the journal reports the F16
multimodal projector loading successfully.

## Out of memory or severe swapping

Confirm the router is still using `--models-max 1` and `parallel = 1`. Do not
attempt to keep both 27B targets with full 245K KV arenas resident merely to
avoid model-switch latency. Check host swap and GPU memory pressure before
reducing quantization or context.

## Benchmark numbers differ

Record the exact runtime commit, bundled driver, model hashes, context, KV
types, sampler, prompt, seed, token limit, DFlash drafted/accepted counts and
whether the run was cold or warm. Short generations can vary considerably
because reasoning length and speculative acceptance differ by prompt.
