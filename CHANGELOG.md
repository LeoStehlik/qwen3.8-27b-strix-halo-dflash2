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
- Documented Discord partial-preview streaming so readers can see generated
  text before a long agent turn completes.
- Added later 43K--50K-context live decode measurements ranging from 17.25 to
  24.38 tok/s, including a 2,668-token turn at 17.97 tok/s.
- Recorded the local persistent-slot candidate: a 35,074-token snapshot saved
  in 399.65 ms, restored in 327.73 ms and retained useful prefix reuse after a
  service restart.
- Corrected the DFlash2 roadmap after confirming that `p_split` and `p_min` are
  not useful tuning controls for the selector-lattice path.
- Recorded the Wave32 override, power/scheduling observations, draft-precision
  tests and the practical 30 tok/s target.
- Added a separate ROCm/vLLM investigation plan covering `gfx1151`, AMD
  MXFP4/MXFP6, DFlash2, tools, vision, prefix caching and rollback.
- Added a shared real-agent benchmark plan for OpenClaw, OpenCode and OpenWork.

## 2026-10-30 — Local deployment

- Deployed UD-Q4_K_XL and UD-Q5_K_XL behind one on-demand router.
- Added Q4_K_M DFlash2 speculative decoding and matching F16 vision projector.
- Configured one 245,760-token slot with Q8_0 target K/V cache.
- Enabled a persistent localhost-only systemd user service.
- Validated Q4 to Q5 to Q4 routing, text, tools and basic vision.
