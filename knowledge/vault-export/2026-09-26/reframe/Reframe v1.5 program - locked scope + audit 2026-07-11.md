---
title: Reframe v1.5 program - locked scope + audit 2026-07-11
type: note
permalink: main/reframe/reframe-v1.5-program-locked-scope-audit-2026-07-11
tags:
- reframe
- v1.5
- roadmap
- program
- design
- audit
- ongoing
---

# Reframe v1.5 program — locked scope + audit 2026-07-11

⭐ CURRENT ongoing work. A 15-agent audit + competitor redo + live visual audit produced a v1.5 roadmap; owner grilled the forks → maximal scope. Multi-week program, executed checkpointed wave-by-wave.

## Audit verdict
Reframe is mature/secure/well-tested → v1.5 ceiling is **features + trust, not firefighting**. 3 real risks (P0): (1) **unsigned auto-updater** from a manual single-machine pipeline w/ empty build-hash pins (silent-RCE path); (2) **mock-sandwich test gate** — NO merge-blocking test crosses the RPC boundary or runs a model (exactly what bit v1.4); (3) **leaky crash seam** — sidecar crash spins the job UI forever, "Cancel" on reframe is a no-op. Keystone refactor: **schema-first generated RPC contract** retires ~7 drift findings (123-method hand-mirror, stale CONTRACTS.md, key-injection allowlist, untyped-settings silent-no-op). Design: **evolve, don't replace** — Dark-Editorial/Signal-Amber already in the 2026 pro-tool school (Linear/Raycast/DaVinci); refine tokens + glass layer + Cmd-K.

## Owner decisions (FINAL scope)
1. **Commercialize + keep-options-open, BUILD-BUT-DON'T-WIRE**: do ALL NC→permissive model swaps NOW (ViNet-S CC-BY-NC-SA → UNISAL Apache-2.0; NLLB/Seamless → MADLAD); build commercialization scaffolding but keep it dormant (no live paywall).
2. **ALL FOUR flagship features**: active-speaker + multi-speaker layouts · transcript-native editing · local auto-B-roll · fully-local lip-sync dub.
3. **Keystone-refactor-first** then features (schema-first RPC contract + typed Settings first, god-module splits interleaved).
4. **FULL pro-shell redesign**: three-zone shell + best-in-class timeline + full IA rebuild + Figma prototypes.

## Live visual-audit findings (drove the redesign; NOT fully in the code-audit)
- **16+ top-level editor tabs** → collapse to ~5 phases (Transcribe→Edit→Reframe→Caption→Export). Biggest IA lever.
- **Nav/brand/top-bar INCONSISTENT across screens** ("Make Shorts/Edit"+"AI MODEL/WHERE JOBS RUN"+"REFRAME" vs "Create/Repurpose"+"QUALITY"+"REFRAME — MEDIA STUDIO"). Unify.
- **Library foregrounds plumbing** (model-readiness list) over the user's videos → content-first grid.
- The bugged `research:competitors` agent MISSED the #1 feature to steal: **active-speaker detection** (redone separately → added as a flagship).
- Redesign prototype (2-screen navigable): artifact a28af8d0-4886-4a96-8373-1ed0beb1658f.

## Waves + progress
- **Wave 0 (de-risk, in flight):** schema-first RPC POC · crash→job-event (**Reframe PR #280 OPEN**, 100% cov) · real-cancel+tree-kill (agent running) · osv-gate torch · one e2e in gate. All via clone-to-temp isolation.
- Wave 1 trust: signed CI release + Electron 39→43 + licensing swaps + dormant commercialization.
- Wave 2 design: Figma + IA restructure + token evolution + WCAG-A timeline fix.
- Wave 3: the 4 flagships (TDD each).
- Wave 4: close-the-loop (reframe preview + orphaned ReframeOverridePanel, viral captions, GPU encode, recovery tray, onboarding, platform delivery).

## Open (deferred) decisions
macOS/Apple-Silicon (Windows-x64 for v1.5 unless reprioritized); signing route (Azure Trusted Signing vs detached-sig); flagship ordering within Wave 3.

Continues [[project_reframe_v1_4_1_shipped_2026-07-09]]; uses [[reference_reframe_quality_gate_codeql_2026-07-11]].
