# Agent-client benchmark plan

Raw llama.cpp probes are necessary but do not predict whether a complete agent
feels usable. Benchmark the same local Qwen service through OpenClaw, OpenCode
and OpenWork. Treat each client as a separate workload generator: system
prompts, tool schemas, context assembly, compaction, retries and streaming can
change latency more than a small server-side throughput difference.

Do not rank clients from one ad-hoc task. Pin the client version and record its
configuration before every published comparison.

## Shared server configuration

Unless the test explicitly changes a server factor, hold these constant:

- API model `qwen3.8-27b-q4-fast`
- Temperature 0.2, top-p 0.95, top-k 20 and min-p 0
- DFlash2 width 4
- One 245,760-token slot
- Q8_0 target K/V and F16 draft K/V
- Same runtime commit and bundled RADV driver
- No unrelated inference traffic

Run the Q5 quality preset separately rather than mixing model switches into a
Q4 latency series.

## Client metadata to capture

For OpenClaw, OpenCode and OpenWork record:

- Exact version or commit
- Provider/API configuration and model alias
- System/agent instruction token estimate
- Number and serialized size of tool schemas
- Enabled tools, MCP servers and plugins
- Repository/workspace size when relevant
- Context, memory and compaction policy
- Reasoning and sampling configuration
- Streaming mode and time until the first visible text
- HTTP timeout, retry and cancellation policy
- Whether the session is cold, warm-prefix or post-compaction

Never publish secrets, Tailscale addresses, Discord identifiers, private prompt
text, repository contents or raw tool output. Sanitized token counts and timing
records are sufficient.

## Workload suite

Use tasks whose result can be checked rather than subjective chat alone:

1. A short factual response with no tool call.
2. A forced single-tool call with exact expected arguments.
3. A two- or three-tool sequence with an objectively verifiable final answer.
4. Inspect a small pinned code fixture, locate a known defect and explain it.
5. Make a bounded code edit and run its test suite.
6. Resume the same task in a warm session.
7. Trigger or simulate compaction and continue correctly afterward.
8. Send two concurrent byte-identical requests and verify one upstream flight.
9. Send two independent sessions and measure queueing or continuous batching.
10. Where the client supports it, interpret the same local vision fixture.

OpenCode and OpenWork should use the same pinned fixture repository for coding
tasks. OpenClaw should receive equivalent task text and tool capability where
practical, but differences in each client's native workflow must be documented
rather than hidden.

## Metrics

Capture two layers of timing.

Server-side:

- Total and newly processed prompt tokens
- Prefix similarity/cache reuse
- Prompt evaluation time and tok/s
- Output tokens, generation time and tok/s
- DFlash drafted/accepted tokens and mean accepted length
- Queue time, model switch time and errors

Client-side:

- Time to first visible text or progress indication
- Time to first useful answer content
- Tool round-trip count and duration
- End-to-end task completion time
- Retries, duplicate calls and timeouts
- Correct tool choice and valid arguments
- Final task correctness and whether manual recovery was required

Report both. Preview streaming can make a 60-second generation feel responsive
without changing server time, while a client can also add minutes of context
assembly or repeated model calls that llama.cpp never sees as one request.

## Test order

For each client:

1. Cold start with a new session.
2. Three warm follow-ups in the same session.
3. Tool sequence.
4. Coding edit/test task where supported.
5. Post-compaction continuation.
6. Duplicate and independent concurrency tests.

Repeat each stable case at least three times. Change labels or session IDs when
a deliberately cold prefix is required; keep serialization identical when
testing prefix reuse. Publish medians and the individual runs rather than only
the fastest result.

## Questions the comparison should answer

- Which client creates the smallest useful cold prompt?
- Which keeps the most stable cache-friendly prefix?
- Which streams useful answer text earliest?
- Which generates unnecessary tool loops or duplicate requests?
- Which compacts without destroying task state?
- Which completes real work fastest at equal model quality?
- Does a client benefit enough from the Q5 preset to justify slower decode and
  model-switch latency?

The primary outcome is successful agent work per minute, not token rate in
isolation.
