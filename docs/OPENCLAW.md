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

## Interactive latency and cache-friendly prompts

Use 60 seconds as the normal user-facing target and 120 seconds as the hard
threshold for a Discord interaction. The client should post progress or a
clear timeout before that threshold; increasing an HTTP timeout only hides the
problem.

The live 100K-plus OpenClaw prompts cold-prefilled at roughly 300--310 tok/s.
That implies five to seven minutes of prefill before the first generated token,
even when decode is healthy. For a cold request, keep initial hydration around
15K tokens for the normal target and below roughly 30K tokens for the hard
target, leaving time for reasoning and generation. These are latency budgets,
not context-window limits.

The server's 24 GiB prompt cache can make a long session fast when the leading
token sequence is unchanged. To maximise reuse:

- Put stable system, SOUL, agent and tool-schema material first.
- Put timestamps, request IDs, current state and the new user message later.
- Avoid injecting changing values near the beginning of the assembled prompt.
- Keep canonical ordering and serialization for tool schemas and memory files.
- Prewarm the exact production prefix after a service or model switch when a
  large stable prefix is unavoidable.
- Expect compaction to create a cold prefix unless its compacted form has
  already been warmed.

Exact-request coalescing is separate: it saves concurrent duplicate requests,
but cannot merge requests whose bodies or suffixes differ. One-slot queueing
is also intentional; controlled one/two/four-slot testing found one slot gave
both the earliest first result and the shortest total drain time.

## Compaction

The server exposes 245,760 active tokens, while Qwen reports a 262,144 training
context. OpenClaw should compact before reaching the hard server limit and
leave room for the next response, tool results and image tokens. The exact
percentage is an OpenClaw policy and deliberately not enforced here.
