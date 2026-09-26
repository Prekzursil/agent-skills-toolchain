---
title: Reframe intelligence WU-A1 DONE (text-consent seam)
type: note
permalink: main/projects/reframe/reframe-intelligence-wu-a1-done-text-consent-seam
tags:
- reframe
- intelligence
- milestone
- consent
- privacy
---

# Reframe intelligence WU-A1 — DONE (2026-06-20)

Branch `feat/intelligence-design`, commit `e69ffc0` (pushed, on top of 7495c99 WU-C4).

## What (G-A5, privacy-critical text-consent seam — text analog of frame gate)
- `consent.py`: new `require_text_consent(settings, provider)` — raises typed `ConsentError(provider, DATA_TYPE_TEXT)` unless `text_consent_granted`; returns None when granted. Mirrors `require_frame_consent` exactly.
- `handlers.py`: new `_text_consented_settings(settings)` PURE per-entry filter of `settings["providers"]` via `consent.text_consent_granted`, provider-id resolution `provider`/`id`/`"cloud"` fallback; returns NEW dict (original never mutated); returns settings unchanged when providers absent/not-list. Mirrors `_frame_consented_vision_settings` (handlers.py:617). So a 429 embedder-pool failover can NEVER rotate transcript text onto a non-consented provider.
- Tests: extended `test_consent.py` (4 new), new `test_handlers_consent.py` (8) — 26 pass.

## Scope note (PLAN §WU-A1 / DESIGN §4 G-A5)
Seam INTRODUCED here, consumed ONLY by `index` routes (WU-A5). Wiring into existing text functions (translation/select/subtitles) is an explicit FOLLOW-UP, out of this bundle.

## Gates
- Sidecar full coverage 100% line+branch (3119 tests, 159s); consent.py + handlers.py both 100%.
- ruff check + format clean (no changes); basedpyright 0/0/0 on changed files.
- Renderer untouched (sidecar-only WU) → RENDERER_COV N/A.

## Next
WU-A1 unblocks the cloud index routes (A5 uses `_text_consented_settings` at index.build + index.search egress, AC c/c2). WU-A2/A3/A4 are parallelisable.
