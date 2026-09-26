---
title: Reframe AI-program grill COMPLETE + preview fixed + plan gating (2026-06-17)
type: note
permalink: main/projects/reframe/reframe-ai-program-grill-complete-preview-fixed-plan-gating-2026-06-17
tags:
- reframe
- ai-program
- provider-hub
- director
- grill
- preview
- plan
- decision
---

# Reframe AI-program — post-grill state (2026-06-17)

Continues [[reframe-session-2026-06-16-phase8-done-zero-drive-provider-hub-director-planned]]. Branch `feat/phase8-moment-finding` (origin). Session in ultracode mode (xhigh + workflow orchestration).

## DONE this stretch
- **Reframe → zero CONFIRMED:** issues 0, PRs 0 (merged #209 deps + #210 issue-retirement + #211 torch-modernize). Dependabot: 12 alerts dismissed honestly (8 inaccurate lockfile + 4 no-patch tolerable-risk) + last 4 cleared by #211 (torch 2.10/cu128/py3.14 dedicated-interpreter for the isolated chatterbox env). Renderer + sidecar 100%.
- **Extensive grill COMPLETE** (~29 decisions): `docs/plans/ai-program/GRILL-DECISION-LOG.md` + `CONVERGED-PROGRAM.md`. Provider research → `docs/plans/provider-hub/CATALOG-SEED.md`. All committed (7c608ff).
- **Preview fix (G1) DONE** (commit 86d0ec4, renderer+sidecar 100%, GO review): root cause = dev data-root divergence (main.ts resolveDataRoot dev-branch ignored marker/exe-dir + propagateDataRootEnv was packaged-only → empty library → 404 → dead `<video>` → no subtitles, since subtitles are DOWNSTREAM of playback). Fixed dev to honor marker/exe-dir + always-propagate to sidecar; + caption-persist lock, playerEpoch key-churn "shake" removal, proxyPath stat-validation, `<video>` onError. **USER MUST runtime-confirm** (relaunch fresh → video plays + subtitle shows; if still fails = H2 Electron-39 streaming regression, needs version bisect). NOTE: dev still needs MEDIA_STUDIO_CONFIG_DIR (set at User scope=D:\Reframe\data) inherited, OR a data-dir.txt marker (exeDir in dev = node_modules, fragile).

## LOCKED program (the bet)
LOCAL-FIRST WEDGE (cloud opt-in accelerator, local backstop, gimmicks off critical path). Hub-first → scoped Director second. Critical path: G1 preview-fix(DONE) → merge phase8→main → ProviderPool(multi-PROVIDER rotation, same-provider=failover, "N keys≠N×quota" honored; local backstop=embedded llama.cpp + auto-detect Ollama/LM Studio) + AI-Job envelope + AI-call cache + pre-flight budget + tested graceful-degradation → Hub UI (static multi-provider catalog w/ per-task tiers + privacy/train-on-input axis; data-driven dual-unit usage bars + "superpowered", a11y; presets + per-function customize; user-brings-key redacted/never-logged/RPC-key-free; per-data-type consent; vision offload CloudVlmBackend on smolvlm2 seam) → Director v1 (conversational agent + typed tool-call plan, hard-validate-reject; toolbox T-stitch/T-scroll/T-ocr-list/T-transcript-edit/T-qa/T-silence; proof=BC-list scroll+extract then Q&A; planner via eval harness) → demand-driven (batch queue/repurpose, templates, multi-platform, semantic index, auto-recommender). ALSO IN (surface-only, code exists): filler/silence removal, speaker diarization. DROP gaze+avatars; gen-broll/music=phase-2 non-goal. Deepfake consent/provenance DEFERRED (user's call). Director canonical reference = the real Claude+Descript "Battle Cats list" chat (scroll-smooth=panorama-stitch+regen NOT speed-ramp; list-extract=OCR→text+poster).

## Director NEW feature (separate, later)
"Director" = prompt-driven AI video editing, `docs/plans/prompt-driven-editing/FEATURE.md`. Sequenced after Provider Hub.

## IN FLIGHT
- **PLAN** (`docs/plans/ai-program/PLAN.md`): drafted → Plan-Gate-1 = CHANGES (all 3 reviewers, no BLOCK; "no re-architecture, seams real"). Folding P0+P1 now (`wf_d64d099c`): real coverage gate (NOT .coverage-thresholds.json which DOESN'T EXIST in this repo — use pytest --cov-fail-under=100 + vitest thresholds:100; renderer is VITEST not jest); WU-vision pool→CloudVlmBackend channel + vlm_reranker wiring into phase8_select (NOT passed today) + frame-consent seam; WU-usage-ui coverage contradiction; WU-keys raw(get_raw) vs redacted + scrub_error_body key-source (move ProviderError into provider class); clock seam; target-job-size + first-run chooser; superpowered kept in MVP per PH1 (overrides DESIGN §12). Then re-gate.

## NEXT after plan PASS
Ask user EXECUTION METHOD (metaswarm orchestrated / subagent-driven / parallel) per CLAUDE.md rule. First real build step = WU-merge (phase8→main). Then build MVP WUs.

## Reusable gotchas reaffirmed
- Don't run repo-READING workflow concurrently with repo-MUTATING one on the shared tree (design-gate-1 false "files missing" from a concurrent branch checkout). Serialize repo workflows.
- This repo has NO .coverage-thresholds.json and NO CLAUDE-referenced jest — coverage SoT = quality.yml + app/vitest.config.ts. The metaswarm CLAUDE.md instruction is generic-template, not repo-accurate.
- Workflow output JSON: parse via `node -e` reading the .output file; grep on escaped JSON fails.