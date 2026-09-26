---
title: PrimariRo state + atlas build plan (checkpoint 2026-07-18)
type: report
permalink: main/projects/primariro/primari-ro-state-atlas-build-plan-checkpoint-2026-07-18
tags:
- primariro
- checkpoint
- plan
- state
- atlas
- fleet
---

Operational state + plan snapshot (companion to the [[PrimariRo → general RO public-office atlas — converged design + legal gates (2026-07-18)]] design note).

## PrimariRo state
- [state] 10-column requirement + hotnews UX (contacts geospatial.org CC0 + MoF; 2020 = 3,186 real terms; 2016 added; suppression removed → confidence BADGES; SearchAutocomplete/MayorDetail/LocalityDrilldown/FilterChips/Export) LANDED as **PR #1** (feat/complete-10-column-requirement). CI green; pytest bumped 8.4.2→9.0.3 (clears Dependabot #7). AWAITING owner decision: preview screenshots vs merge-on-green (merge deploys live to Pages). #primariro
- [state] Data is REAL/provenance-backed; AUR correctly absent in 2016/2020 (won 0 mayoralties then). Verified: provenance/dual-source/output-allowlist gates + render-guard self-test + 60 pipeline + 92 data-bound unit tests green. #verified

## Atlas build plan (phased; "everything e2e" via internal ordering)
- [plan] P0 additive schema migration (Jurisdiction/Mandate/Institution/Popolo) — BLOCKING, must regen mayor dataset BYTE-IDENTICAL + BEC-30 green. #plan
- [plan] Then parallel worktree tiers: national executives (President/Gov/prefects/CJ-pres) · Parliament (cdep/senat current legislature) · councils-composition + party registry + councillor-name framework. #plan
- [plan] Integrate → atlas/build branch + "who represents me" flagship scaffolding + private-tier guards (gitignore+pre-commit+CI leak-check) + coverage dashboard. #plan
- [plan] ITERATION after eval: full-history-to-1990 backfill + all-councillor names + all-parties-to-local-branch (the multi-pass data effort). #plan
- [plan] Owner chose: direct Codex fan-out (no metaswarm gates), everything e2e, THEN I evaluate vs build-spec §5 (completion + per-tier/party coverage % + each gate; active fabrication hunt; coverage-theater = FAIL). #plan

## Event tracker / workflow IDs (this session)
- [ref] Grill DIVERGE workflow: **wf_81bcbbaa-5b9** (5 lenses → 33-decision queue). #workflow
- [ref] Atlas BUILD fan-out: **w6ifbkyd7 / wf_d7c2f1f3-acd** (running; P0→tiers→integrate). #workflow
- [ref] Deliverables (session scratchpad): primariro-atlas-grill-log.md, primariro-atlas-decision-queue.md, primariro-atlas-build-spec.md. #ref

## Fleet state (this session, adjacent)
- [state] momentstudio: 0 code-scanning alerts, CodeQL warning fixed (default-setup disabled), #616 closed (premature per QZP charter), #617→#649 MERGED (backend cyclic-import salvage), #625→#650 DRAFT reconciled base (owner repoints their other session), #624 superseded. #momentstudio
- [state] agent-skills-toolchain: ci-hygiene stub-reword **PR #95** (mergeable, docs-only). Local `harness/upgrade-2026-07-17` branch is STALE (11 ahead/22 behind, overlaps merged #66/#67/#91) — NOT PR'd. Working tree has 7 uncommitted incl. 2 git-crypt `accounts.json` (FLAGGED to owner, untouched). #toolchain
- [todo] Open loops (task #20/#21): land PrimariRo #1 (owner decision), momentstudio #650 (owner's other session), ast #95; evaluate atlas build on completion. #todo

relations:
- part_of [[PrimariRo → general RO public-office atlas — converged design + legal gates (2026-07-18)]]


## Chain update 2026-07-19 — P2 fresh-restart (resume)

- **P0 ✅, P1 ✅** (integrity gate-hardening + OKLCH tokens) merged into `atlas/build` @ `b060e2e`, independently gate-verified (semantic-provenance crown-jewel seed test passes; 291 pytest green).
- **P2 v1 (`wf_ed574363-705`) INTERRUPTED** by process-exit ~03:32 mid-run (5 started / 2 result). Forensics (journal + branches + agent finals): private-guards impl+val cached BUT its adversarial reviewer was mid-flight reporting *"PROBE 2 confirms a real hole"* ⇒ impl `a637eae` was BLOCK-bound; backfill impl still ingesting councillors (uncommitted → discarded by the `--force` worktree prune); contacts impl never committed (branch=base). Two impls never returned ⇒ not cached ⇒ resume would re-run them AND collide on pre-existing branches.
- **Decision: CLEAN RESTART over resume** (fan-out-contract §10). Resume would save only ~2 agents and replay a BLOCK-bound WU. Pruned all leftover worktrees (kept primary + `PrimariRo-atlas-build`), deleted the 3 partial branches (contacts=base `b060e2e`, private-guards `a637eae`, backfill `e71d3ce`) for uncontested `git worktree add -b`.
- **P2 v2 RELAUNCHED FRESH** = `wf_dff345bd-5fc` (task `wsj5l3bi2`), same frozen script, background. WUs: contacts §0.2 Tier-1 MoF (`listaentitatipublice` via data.gov.ro) cross-source + lineage-independence; private-guards CHERRY-PICK from stale `atlas/private` (never merge the fork — it deletes tiers); backfill ingesters + bounded slice. metaswarm 4-phase per WU, sourcing-law enforced + `sourcing_violation` reviewer veto.
- **Independent gate harness ready** at `scratchpad/p2-gate.sh`: re-runs the 10 CI gates in a dedicated `PrimariRo-gate-*` worktree + orchestrator-only checks (mayor golden byte-identity vs `atlas/build`, Confirmed-cell quote-at-source spot-check, CAPTCHA/headless-evasion sourcing grep). Run per SHIP branch BEFORE merging into `atlas/build`.
- **Next after P2 lands**: gate each SHIP branch → merge SHIP-only into `atlas/build` → **P3** Design-C redesign (Design-Review-Gate first; figma reference-only, repo-native DTCG/OKLCH tokens canon) → **P4** deploy-preview (PR + Pages preview + robots-noindex + beta banner until owner approves live).
- **Hard lines held**: NEVER bypass CAPTCHA/bot-detection (legitimate channels only; gated ⇒ honestly absent/Unverified); NEVER fabricate (derived capped Probable, never Confirmed); institutional-only public contacts; HARD-OUT all private tiers; mayor golden byte-identical; Reframe issue #285 not mine to close.