# OpenClaw live trace: cold hydration versus warm turns

This sanitized trace records a real OpenClaw session evaluated by Francis on
2026-10-30. Prompt text, tool output, request identifiers, client addresses and
session identifiers are intentionally omitted. The server configuration was
the production Q4 preset: one 245,760-token slot, Q8_0 target KV, DFlash2 width
4, F16 vision projector and a 24 GiB host prompt cache.

## Headline result

The inference server was healthy throughout. A single warm OpenClaw session
was usable, but OpenClaw's cold request was far too large for interactive use.

| Measurement | Result |
|---|---:|
| Cold prompt | 152,781 tokens |
| Cold prompt processing | 545.25s at 280.20 tok/s |
| Cold generation | 321 tokens in 26.44s at 12.10 tok/s |
| Cold total | 571.69s (9m32s) |
| Cold DFlash acceptance | 40.78% |
| Ten cached turns, median | 47.5s |
| Ten cached turns, mean | 53.6s |
| Cached turns under 60s | 8/10 |
| Cached turns under 120s | 10/10 |

The cold request was not stalled: progress advanced continuously. At this
context size, the prompt alone required more than nine minutes before a useful
answer could finish.

## Cached tool loop

The first follow-up had 96.6% longest-common-prefix similarity; subsequent
turns typically showed 98--99%. The cache therefore worked once the initial
session was hydrated.

| Turn | New prompt tokens | Prompt time | Output tokens | Generation time | Total |
|---:|---:|---:|---:|---:|---:|
| 1 | 5,344 | 28.9s | 309 | 24.1s | 53.0s |
| 2 | 4,708 | 25.4s | 137 | 11.9s | 37.4s |
| 3 | 1,401 | 9.0s | 434 | 33.1s | 42.1s |
| 4 | 1,803 | 11.4s | 351 | 26.6s | 38.0s |
| 5 | 1,911 | 11.1s | 1,077 | 82.1s | 93.1s |
| 6 | 2,577 | 15.8s | 427 | 29.8s | 45.6s |
| 7 | 2,196 | 14.0s | 475 | 35.4s | 49.4s |
| 8 | 2,344 | 15.3s | 386 | 29.8s | 45.2s |
| 9 | 4,998 | 28.3s | 399 | 29.9s | 58.2s |
| 10, vision in history | 5,537 | 31.8s | 531 | 42.4s | 74.1s |

At approximately 153K--166K live context, decode ranged from 11.4 to 14.3
tok/s and DFlash acceptance ranged from 37.3% to 53.5%. The 93-second turn was
output-bound rather than prompt-bound: generating 1,077 tokens took 82
seconds. Sub-minute interaction consequently requires concise intermediate
responses as well as prefix reuse.

Two `non-consecutive token position` warnings appeared while extending one
cached turn. That request recovered, generated normally and completed without
an API error. This is worth monitoring, but it was not a failure in this run.

## A second session missed the hot prefix

After the cached loop, a materially different OpenClaw request arrived. Its
prefix similarity was too low for LCP selection, so llama.cpp selected the
only slot by LRU and began another approximately 150K-token cold prefill. A
further distinct request arrived while it was running and queued behind it.

The test was deliberately stopped after the second cold request had processed
roughly 74K tokens. At that point the proxy reported two active distinct
flights, no coalesced follower and no upstream error. Because the service was
restarted to cancel the workload, this run did not test whether the 24 GiB
host prompt cache could later restore the first session.

This demonstrates two separate latency problems:

1. A new 150K-token OpenClaw prefix takes minutes to hydrate.
2. With the measured one-slot winner, that cold request causes head-of-line
   blocking for other independent requests.

Adding slots is not the answer on this build: the controlled slot comparison
showed that two and four slots worsened first-result and total-drain latency.

## Practical OpenClaw changes

- Measure the assembled request by component: system/SOUL, agent files,
  memories, conversation, tool schemas, runtime context and images.
- Target about 15K cold input tokens for the normal 60-second budget and stay
  below roughly 30K for the 120-second ceiling. Context capacity is not a
  latency target.
- Put stable material first. Move timestamps, request IDs, runtime state and
  the latest user message after the stable prefix.
- Keep memory, tool ordering and schema serialization deterministic.
- Defer non-core tool schemas and discover or load only the tools needed for
  the current task. The live request exposed a very large tool catalogue.
- Keep local evaluation in one stable session until multi-session cache
  restoration has been measured.
- Keep tool-loop reasoning and intermediate output concise. Around 500 output
  tokens can consume 35--45 seconds at this context depth.
- Avoid automatic retries that mutate the body. Concurrent byte-identical
  retries coalesce; changed timestamps or other dynamic fields create separate
  queued inference requests.

The next controlled OpenClaw test should use a minimal agent with essential
system material, deferred tools and no bulk memory hydration. Record the final
input-token estimate before sending it; do not start the run if it exceeds 30K.

## Operational follow-up

The coalescer intentionally keeps upstream inference alive if the leading
client disconnects, so a concurrent follower can still receive the complete
response. For multi-minute cold requests this can also leave useful GPU time
assigned to an abandoned request. Subscriber-aware cancellation when the last
downstream client disappears is therefore a worthwhile follow-up.
