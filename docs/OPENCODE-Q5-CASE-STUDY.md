# OpenCode Q5 security-remediation case study

This is a dated, real-agent observation from 2026-10-30. It is not a
vendor-neutral model benchmark. The workload, client, repository state,
reasoning mode, context depth and DFlash acceptance all affect the result.

## Task and outcome

OpenCode used the `qwen3.8-27b-q5-quality` API model to inspect a public
TypeScript monorepo's Dependabot alerts, prepare isolated dependency fixes,
wait for repository checks and merge successful pull requests. The client ran
with its `high` reasoning variant.

The run produced four merged pull requests with signed commits and green DCO
and repository-regression checks:

| Pull request | Change | Alerts addressed |
|---|---|---:|
| [#139](https://github.com/wrenlore/wrenlore/pull/139) | Fastify 5.12.5 to 5.12.6 | 1 low |
| [#140](https://github.com/wrenlore/wrenlore/pull/140) | follow-redirects 1.16.0 to 1.16.1 | 2 high |
| [#141](https://github.com/wrenlore/wrenlore/pull/141) | Hono 4.13.7 to 4.13.11 | 1 medium |
| [#142](https://github.com/wrenlore/wrenlore/pull/142) | MCP TypeScript SDK 1.31.0 to 1.32.0 | 2 high, 2 medium |

The alert-to-version mappings and final diffs were independently checked
against GitHub's advisory data. The final merge was commit `8eb6036`. At the
measurement cutoff, Dependabot had not yet completed its post-merge rescan, so
the eight logically addressed alerts were still temporarily reported as open.

The run also exposed useful failure modes. An initial Fastify pull request was
closed and superseded after branch-lifecycle confusion. The agent spent
unproductive turns polling a closed pull request, then recovered. It also
replaced a broken Dependabot MCP update with a consistent three-file change to
the direct manifest, root override and lockfile.

## Inference configuration

| Component | Value |
|---|---|
| Machine | Ryzen AI Max+ 395 / Radeon 8060S, 128 GB unified memory |
| Runtime | llama.cpp Vulkan build 11003, commit `a82001bd3` |
| Target | Qwen3.8-27B UD-Q5_K_XL |
| Drafter | Qwen3.8-27B DFlash2 Q4_K_M |
| DFlash width | 4 |
| Context / slots | 245,760 / 1 |
| Target KV | Q8_0 K and V |
| Draft KV | F16 |
| Batch / ubatch | 2,048 / 2,048 |
| Threads | 16 generation, 16 batch |
| Vision | F16 projector loaded; unused by this task |
| Client | OpenCode v2.0.11 |
| Reasoning | OpenCode `high`; mapped by the model template to `xhigh` guidance |

This used the local persistent-slot candidate runtime rather than the portable
runtime downloaded by the repository installer. Persistent restart recovery
was available but was not needed during the continuous run.

Request-level sampling fields were not captured. Do not treat this trace as a
controlled comparison with another client or quantization.

## Complete server-side totals

The model loaded at approximately 20:16 UTC and the fourth merge completed at
21:50 UTC, an observed wall interval of about 94 minutes. The server recorded:

| Metric | Result |
|---|---:|
| Completed model turns | 122 |
| Newly evaluated prompt tokens | 84,499 |
| Prompt-evaluation time | 397.98 s |
| Weighted prompt rate | 212.32 tok/s |
| Generated tokens | 72,053 |
| Generation time | 4,552.65 s |
| Weighted generation rate | 15.83 tok/s |
| Weighted DFlash acceptance | 62.57% |
| Backend inference time | 4,950.63 s / 82m31s |
| Generation share of backend time | 91.96% |
| Final populated context | 155,534 tokens / 63.3% |

Backend inference occupied roughly 88% of the observed wall interval. Tool
execution, GitHub operations, CI waits and client orchestration together were
therefore much smaller than model inference. Within backend time, generation
was overwhelmingly dominant.

The per-turn prompt total is not expected to equal final context exactly.
Prefix reuse, replaced suffixes and prompt-layout changes make those different
measurements.

## Context-depth scaling

The following rows aggregate completed calls by their ending slot depth. Token
rate is weighted by generation time rather than averaging per-call rates.

| Ending context | Turns | Generated | Weighted decode | DFlash acceptance |
|---:|---:|---:|---:|---:|
| 0--25K | 13 | 5,776 | 21.68 tok/s | 62.52% |
| 25--50K | 3 | 4,984 | 20.94 tok/s | 68.18% |
| 50--75K | 23 | 14,943 | 17.78 tok/s | 59.88% |
| 75--100K | 13 | 5,672 | 16.48 tok/s | 64.29% |
| 100--125K | 22 | 16,651 | 14.22 tok/s | 55.06% |
| 125--150K | 45 | 19,087 | 14.06 tok/s | 70.39% |
| 150--156K | 3 | 4,940 | 14.72 tok/s | 63.73% |

Decode fell by approximately 35% between the first and the 125K--150K buckets.
The high 70.39% acceptance in that deep bucket did not restore early-session
speed. At this depth, target attention and verification cost dominate enough
that acceptance alone is not a useful throughput predictor.

Consecutive tool turns usually retained approximately 96--100% longest-common
prefix similarity. One apparent 18.8K-token "cache miss" was instead genuinely
new repository/tool output appended to a fully retained prefix. Prefix caching
worked; the dominant cost was processing and generating an unusually large
agent trajectory.

## Agent observations

### What worked

- Q5 completed a long-horizon coding workflow with real GitHub state changes.
- Tool selection, command construction and dependency/advisory matching were
  generally competent.
- The agent recovered from a closed-PR mistake and corrected an incomplete MCP
  branch before opening the final pull request.
- All four final changes were isolated, reviewable, signed and CI-green.
- Stable prompt ordering preserved the llama.cpp prefix cache across most tool
  loops.

### What cost time

- Seventy-two thousand generated tokens for four dependency fixes is excessive.
- The agent repeatedly reasoned about and polled CI instead of yielding until a
  meaningful state change.
- It created a custom Git Data API push helper to work around client-host
  restrictions. That workaround was task-environment specific, not an
  inference requirement.
- High reasoning encouraged careful recovery but was not A/B tested against
  medium. It may have increased trajectory length substantially.
- Keeping one session to 155K preserved task state but reduced decode from
  roughly 21--22 tok/s to roughly 14 tok/s.

## Practical conclusions

1. Qwen3.8-27B Q5 is viable for useful local coding-agent work on this Strix
   Halo deployment. It produced reviewed and merged changes, not merely chat.
2. The OpenCode harness was materially more productive than the observed
   OpenClaw workload, but this is not a controlled client comparison.
3. Prefix caching cannot compensate for indefinite context growth. For a batch
   of independent fixes, end or compact the session around 75K--100K tokens and
   start a fresh task phase when continuity is no longer valuable.
4. Agent success per hour is the useful metric. Raw short-prompt tok/s would
   have missed the trajectory bloat, CI polling and deep-context slowdown.
5. A future controlled run should repeat the same pinned task with Q4 and with
   medium reasoning before attributing quality or speed differences to Q5.

## Reproduction record

For a comparable run, record:

- OpenCode version and full model/provider variant configuration
- Base repository commit and exact alert set
- Start/end wall timestamps
- Pull-request URLs and terminal CI states
- Server model alias, runtime commit and all context/KV/DFlash settings
- Per-turn prompt, generation and acceptance metrics from llama.cpp logs
- Context depth at each completed call
- Manual interventions, retries, polling loops and superseded branches

Do not publish credentials, private repository contents, host addresses or raw
tool output. Public pull-request outcomes and sanitized timing totals are
sufficient for verification.
