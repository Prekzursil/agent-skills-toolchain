---
title: Reframe v1.3 program plan (grill converged)
type: report
permalink: main/projects/reframe/reframe-v1.3-program-plan-grill-converged
tags:
- reframe
- media-studio
- v1.3
- grill
- decision-log
- installer
- design-gate
---

# Reframe v1.3 "Complete & Coherent" — decision log (post Design-Gate-1)

Grill-me-extensive (expansion+red-team) converged 2026-07-04; Design Review Gate 1 = APPROVE_WITH_CHANGES
(5/5 roles, 0 blocks). Full plan v2: scratchpad/reframe-v1.3-program-plan-v2.md. App = media-studio
(Electron 39 app/ + React/TS + Python 3.12 sidecar over stdio JSON-RPC). Repo branch fix/reframe-hardening;
main=v1.2.0. Installed D:/Program Files/Reframe - Media Studio/; provisioned root D:/Reframe/data.

## Locked decisions
- G-1 Bigger vision (fix+complete+grow; multi-release).
- G-2/G-6 ONE big polished v1.3, NO interim release (user REAFFIRMED after gate pushback — they're the
  affected user + have data-dir.txt workaround). Vision features = Wave 2.
- G-3 Display name "Reframe" everywhere; internal name media-studio STAYS (appId/data-folder id).
- G-4 On-demand-first install (never bricks).
- G-5 Re-host ViNet-S saliency + TransNetV2 scene-cut, verify-before-load + pinned.
- G-7 Personal/free use → ViNet-S CC-BY-NC-SA non-commercial OK with attribution.

## Three errors (code-grounded)
1. unknown asset(s): _wire.py _COMPONENT_ASSETS/_READINESS_TIERS tier1 + recommender.py:82-95 list
   de-registered assets -> assets.ensure emits names rpc.py rejects. Fix: re-register + gate to manifest-known.
2. LLM 10061: llama :8088 (provider.py:54) only started by translation tier (translation.py:453-455);
   select/subtitles/local-backstop POST assuming up.
3. media code 4: raw non-Chromium source streamed before proxy; failures swallowed.
Plus missing bundled ffmpeg (sidecar.ts buildSidecarEnv -> resources/bin/ffmpeg.exe).

## Design-Gate-1 findings (12 MUST folded into v2)
Direction unanimously sound. 5 seams: (1) per-complaint ACCEPTANCE CRITERIA + clean-machine
install-and-use BLOCKING gate (the exact miss that caused this); (2) RECONCILE-don't-rebuild WS-D/E
(ProviderKeyRow/UsageBar/OpenRouterUsage/DirectorPanel explainer ALREADY EXIST; real gap = key
reveal/edit/validate; much "missing" was just unreachable behind the brick); (3) installer-profile <->
first-run contract (FIRST_RUN_COMPLETE core-only + point-of-use readiness); (4) DPAPI key chain
(sidecar reads cleartext keys from settings.json TODAY; needs safeStorage decrypt->raw key over stdio RPC
per-request, migration re-encrypt+SHRED plaintext, refuse-to-persist if unavailable, transient reveal RPC);
(5) integration seams (llama auto-start at LocalServerProvider boundary via injected ensure-callback +
readiness probe + LaneLock; data-root CONTENT-aware not location; weight verify-before-load +
license/provenance, re-hosting OFF critical path; latent bug DirectorPanel.tsx:226 plan?.videoId ?? trimmed
dispatches goal as videoId). SHOULD: reconcile animated-purple usage to single-accent ladder; confirm
release provenance (branch pkg 1.1.0 vs released 1.2.0); freeze scope (ROADMAP V2 out).

Gate bug: args passed stringified -> planPath/repoPath resolved 'undefined' so agents reviewed CODEBASE
(deeply) but NOT the plan doc -> A-F sequencing unreviewed -> readyForPlanning=FALSE. Re-gate v2 with fixed args.

## Sequencing A->F (A+B verified-unbricked checkpoint before C); re-host models = parallel infra track.
## Next: Design-Gate-2 (v2) -> formal plan .beads/plans/active-plan.md -> Plan Review Gate -> execution-method -> BUILD.
Relates media_studio_local_scope; quality>cost; TDD+100% coverage gate + adversarial review + no silent fallbacks.