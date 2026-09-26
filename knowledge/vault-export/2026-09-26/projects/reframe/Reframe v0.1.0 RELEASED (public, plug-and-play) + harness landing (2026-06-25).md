---
title: Reframe v0.1.0 RELEASED (public, plug-and-play) + harness landing (2026-06-25)
type: note
permalink: main/projects/reframe/reframe-v0.1.0-released-public-plug-and-play-harness-landing-2026-06-25
tags:
- reframe
- release
- v0.1.0
- shipped
- plug-and-play
---

# Reframe v0.1.0 RELEASED (2026-06-25)

Continues [[reframe-autonomous-test-hardening-harness-idea-engine-plan-2026-06-22]] + [[reframe-redesign-shipped-to-main-installer-rebuilt-spend-cap-in-flight-2026-06-21]].

## ✅ RELEASE SHIPPED: GitHub Release **v0.1.0 "Reframe v0.1.0 — AI Media Studio"** (Latest, not draft) on Prekzursil/Reframe (repo is PUBLIC → release is publicly downloadable; user explicitly authorized "release made, plug and play").
- Assets (plug-and-play downloads): media-studio-0.1.0-win-x64.exe (196MB NSIS installer) + media-studio-0.1.0-win-x64.zip (262MB portable). dl=0 so far.
- Docs merged (PR #234): plug-and-play README + v0.1.0 CHANGELOG on main.
- ONE-FOLDER confirmed: everything under github/Reframe (app/ sidecar/ docs/ build/ installers[gitignored] electron-builder.yml); no stray tracked binaries. External user runtime data %APPDATA%/media-studio (~11MB) left alone (not repo clutter).
- Product in the release = Hub + 5 AI features (Director/Repurpose/Editing-refine/UX-QoL/Intelligence) + tabbed UI redesign (Library/Create/Director/Repurpose/Settings incl. Providers&Keys + spend-cap) + 8 audit-bug fixes. GUI-verified.

## HONEST CAVEATS (in release notes): bundled Python (no prereqs) BUT first-run downloads several GB of models/deps; GPU features (chatterbox TTS, accelerated reframe) need NVIDIA; "plug-and-play" = install+auto-setup, not offline-instant. "100% on any computer" is NOT claimed (impossible by testing).

## TEST HARNESS landing (wf_44e39d2e): Wave-1 (OS-matrix packaged E2E + nasty-input fixtures + Hypothesis[sidecar]/fast-check[renderer] property/fuzz) verified locally (sidecar 4075/100%, renderer 100%/11204, pre-commit clean). CI was RED on a real gap: conftest imports hypothesis but CI `pip install -e sidecar[dev] --no-deps` SKIPS the [dev] extra (that's why pytest/pytest-cov are explicitly re-listed). FIX (1da2b7b): added `hypothesis` to the explicit pip-install line in quality.yml. PR #233 merging on green; then Wave-2 (mutation mutmut+Stryker nightly + Playwright visual-diff + axe a11y). LESSON: `--no-deps` in CI means EVERY test dep must be in the explicit install list, not just pyproject [dev]; verify with the EXACT CI env, not local /tmp/msv which had hypothesis.

## FLEET: 12/13. momentstudio LAST — Python backend 100%; Angular frontend grinding to 100% (wf_444b136f, ~40%→ baseline, 113 files) -> then PR #600 -> 13/13. Big multi-pass grind.

## REMAINING: land Wave-1/2 harness; momentstudio Angular -> 13/13; backlog ideas #2 social-publish + #3 yt-dlp-ingest (net-new, user go-ahead); Wave-3 idea-engine roadmap (from property counterexamples + mutation survivors + a11y findings); optional Sentry DSN/BrowserStack for the account-gated layers.