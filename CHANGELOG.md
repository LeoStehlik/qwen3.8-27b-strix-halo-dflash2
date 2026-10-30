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
- Configured two continuously batched slots with unified Q8 KV and a 491,520
  token total pool, preserving 245,760 tokens per slot.
- Increased the host-RAM prompt cache from its 8 GiB default to 24 GiB after
  observing repeated eviction of approximately 6 GiB OpenClaw snapshots.

## 2026-10-30 — Local deployment

- Deployed UD-Q4_K_XL and UD-Q5_K_XL behind one on-demand router.
- Added Q4_K_M DFlash2 speculative decoding and matching F16 vision projector.
- Configured one 245,760-token slot with Q8_0 target K/V cache.
- Enabled a persistent localhost-only systemd user service.
- Validated Q4 to Q5 to Q4 routing, text, tools and basic vision.
