# Changelog

## Unreleased

- Prepared the working deployment as a portable local Git repository.
- Licensed the repository's original scripts and documentation under MIT.
- Added pinned and checksummed runtime/model download scripts.
- Added a portable systemd user-service installer.
- Documented architecture, installation, security, benchmarks and roadmap.
- Made launchers independent of `/home/less`.
- Enabled preservation of Qwen reasoning across compatible tool histories.
- Retained DFlash2 width 4 after Q4 and Q5 width sweeps.
- Retained temperature 0.2 as the conservative agent/tool starting point.
- Added a streaming exact-request coalescer for concurrent retries.
- Tested one, two and four continuously batched slots with four simultaneous
  cold prompts. Retained one 245,760-token slot because it produced the first
  result and drained the queue sooner than either multi-slot configuration.
- Increased the host-RAM prompt cache from its 8 GiB default to 24 GiB after
  observing repeated eviction of approximately 6 GiB OpenClaw snapshots.
- Added a sanitized real OpenClaw trace: a 152,781-token cold prompt took
  9m32s, while ten prefix-cached tool turns had a 47.5-second median.

## 2026-10-30 — Local deployment

- Deployed UD-Q4_K_XL and UD-Q5_K_XL behind one on-demand router.
- Added Q4_K_M DFlash2 speculative decoding and matching F16 vision projector.
- Configured one 245,760-token slot with Q8_0 target K/V cache.
- Enabled a persistent localhost-only systemd user service.
- Validated Q4 to Q5 to Q4 routing, text, tools and basic vision.
