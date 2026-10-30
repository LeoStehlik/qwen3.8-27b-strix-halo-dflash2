# OpenClaw integration

The local service implements the OpenAI-compatible Chat Completions endpoint at
`http://127.0.0.1:8080/v1` and accepts text, tools and `image_url` content.
Remote clients should use the machine's Tailscale address when
`QWEN_BIND_HOST` is configured accordingly.

Concurrent byte-identical inference requests are coalesced while they are in
flight. This is useful when OpenClaw retries a request after its own timeout.
The response is not retained after completion, and merely sharing a prompt
prefix does not coalesce requests; that case is handled by llama.cpp's KV
prompt cache.

OpenClaw changes quickly; validate the final configuration against the version
being installed. The following is a starting shape, not a substitute for the
real Francis/OpenClaw evaluation:

```json5
{
  models: {
    providers: {
      localqwen: {
        baseUrl: "http://127.0.0.1:8080/v1",
        apiKey: "local-only",
        api: "openai-completions",
        models: [
          {
            id: "qwen3.8-27b-q4-fast",
            name: "Qwen3.8 27B Q4 Fast",
            input: ["text", "image"],
            contextWindow: 245760,
            compat: { thinkingFormat: "qwen-chat-template" },
          },
          {
            id: "qwen3.8-27b-q5-quality",
            name: "Qwen3.8 27B Q5 Quality",
            input: ["text", "image"],
            contextWindow: 245760,
            compat: { thinkingFormat: "qwen-chat-template" },
          },
        ],
      },
    },
  },
  agents: {
    defaults: {
      model: { primary: "localqwen/qwen3.8-27b-q4-fast" },
      models: {
        "localqwen/qwen3.8-27b-q4-fast": {
          alias: "qwen-fast",
          params: {
            temperature: 0.2,
            topP: 0.95,
            chat_template_kwargs: { enable_thinking: true },
            extra_body: {
              top_k: 20,
              min_p: 0.0,
              presence_penalty: 0.0,
              repeat_penalty: 1.0,
            },
          },
        },
        "localqwen/qwen3.8-27b-q5-quality": {
          alias: "qwen-quality",
          params: {
            temperature: 0.2,
            topP: 0.95,
            chat_template_kwargs: { enable_thinking: true },
            extra_body: {
              top_k: 20,
              min_p: 0.0,
              presence_penalty: 0.0,
              repeat_penalty: 1.0,
            },
          },
        },
      },
    },
  },
}
```

OpenClaw supports model-scoped `params.temperature`, `params.topP`,
`chat_template_kwargs`, and `extra_body` pass-through for OpenAI-compatible
providers. The server itself also has `--reasoning-preserve` enabled so that a
compatible client can retain Qwen reasoning across tool-result turns.

## Evaluation plan

Francis, the OpenClaw-resident agent, will conduct the authoritative evaluation
with the actual system prompt and tools. Each run should capture:

- API model ID and sampler
- Prompt/cache/completion token counts
- Tool selected, argument validity and execution result
- Spurious or missed tool calls
- Time to first token and generation rate
- DFlash drafted/accepted counts when available
- Compaction occurrence and behaviour afterward
- Human judgement of task correctness

The Q5 preset should not automatically be used for every long task. The
evaluation should determine which task classes actually benefit enough to
justify its slower decode and model-switch latency.

## Compaction

The server exposes 245,760 active tokens, while Qwen reports a 262,144 training
context. OpenClaw should compact before reaching the hard server limit and
leave room for the next response, tool results and image tokens. The exact
percentage is an OpenClaw policy and deliberately not enforced here.
