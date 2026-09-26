---
title: Reframe autonomous test-hardening harness + idea-engine plan (2026-06-22)
type: note
permalink: main/projects/reframe/reframe-autonomous-test-hardening-harness-idea-engine-plan-2026-06-22
tags:
- reframe
- testing
- harness
- deep-research
- coverage
- roadmap
---

# Reframe autonomous test-hardening + idea-engine (2026-06-22)

User asked: is there a toolchain to drive/fully-test the app to ~100% guarantee (functional + edges + UI/UX) on ANY computer + generate feature ideas? Deep-research (wf_c4ba8bdd, firecrawl/exa) + synthesis done. User chose: BUILD the full autonomous harness + idea roadmap.

## HONEST CEILING (stated to user): "100% on ANY computer" is UNACHIEVABLE by testing — coverage% only proves code ran; env space (OS/arch/GPU-driver/codec/locale/AV/offline) is combinatorially infinite; the GPU/WSL2 reframe path can't run on GPU-less CI. Achievable = HIGH CONFIDENCE on a tested matrix + bundled runtime (done) + graceful degradation + field telemetry. Materially stronger than any coverage number; NOT a guarantee.

## TOOLCHAIN (existing > online; tooluniverse=pharma-irrelevant; frida/cheatengine=RE-not-test). KEY: MCPs = authoring accelerants; the durable guarantee lives in repo specs + CI YAML.
- ⭐ OS MATRIX on the PACKAGED app (GH Actions windows/macos/macos-13/ubuntu + electron-playwright-helpers) — biggest lever; e2e.yml was Ubuntu-only.
- Property/fuzz: Hypothesis (Py sidecar) + fast-check (TS renderer, fc.commands) — where "all edges" come from.
- Mutation: mutmut (Py) + Stryker (TS) — the honest "are my 100% tests any good" (coverage!=correctness).
- Visual+a11y: Playwright screenshot-diff (no-cloud) + axe + Lighthouse; BrowserStack/Percy (renderer only, needs account).
- Telemetry: Sentry (real-world tail; needs DSN). AI exploratory: QA Wolf (Electron) / Skyvern/QA.tech (renderer-DOM only) — optional paid.

## REFRAME ALREADY HAS (~70%): pytest 100% branch + vitest 100% + Playwright _electron E2E (preview, Ubuntu xvfb) + nightly e2e.yml (real-ffmpeg+tiny-whisper smoke) + gates (ruff/basedpyright/opengrep/osv). GAPS: no OS matrix, no visual, no a11y, no property/fuzz, no mutation, no telemetry, GPU/WSL2 untested in CI.

## BUILD PLAN (branch feat/test-hardening, bounded waves to avoid rate-limit):
- Wave 1 (wf_6a7de1f1, IN FLIGHT): WU-A OS matrix on packaged build + electron-playwright-helpers (assert app.isPackaged) + nasty-input E2E fixtures (zero-len/audio-only/no-speech/broken-codec/weird-aspect/malformed-SRT-VTT/unicode-RTL/huge-timeline); WU-B Hypothesis + fast-check property/fuzz maintaining 100%.
- Wave 2 (queued): mutation (mutmut+Stryker, non-blocking nightly; pair .coverage-thresholds with a mutation-score target) + visual (Playwright screenshot-diff) + a11y (axe) + Lighthouse perf.
- Wave 3 (queued): IDEA-ENGINE — route exploratory crawls + property counterexamples + mutation-survivors + a11y/visual findings (+ Sentry clusters once wired) into ONE evidence-backed feature/improvement roadmap (-> metaswarm /create-issue -> design-gate).

## ACCOUNT-GATED (flagged to user): Sentry DSN, BrowserStack/Percy key, paid AI exploratory testers.

## momentstudio: Python backend 100% (CI green). Angular frontend BASELINE ~40% (113 files) = HUGE grind; PAUSED to focus API capacity on the Reframe harness (running both big grinds rate-limits). Resume Angular low-concurrency after. PR #600 still open (jsts lane red until Angular 100%).