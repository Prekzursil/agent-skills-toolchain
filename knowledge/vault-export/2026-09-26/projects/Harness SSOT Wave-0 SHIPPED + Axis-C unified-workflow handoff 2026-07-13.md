---
title: Harness SSOT Wave-0 SHIPPED + Axis-C unified-workflow handoff 2026-07-13
type: report
permalink: main/projects/harness-ssot-wave-0-shipped-axis-c-unified-workflow-handoff-2026-07-13
tags:
- harness
- ssot
- wave-0
- axis-c
- codex-invoke
- compaction-checkpoint
---

# Harness config-SSOT — Wave-0 SHIPPED + Axis-C handoff (2026-07-13)

**Repo (SoT):** `agent-skills-toolchain`. **Worktree:** `C:\Users\Prekzursil\source\ast-harness-reconcile`
(a worktree of that repo). **Branch:** `chore/enshrine-runtime-config` @ `19ccb88` — **PUSHED to origin**
(fresh branch, tracking set). Live harness: `~/.agents/harness` (canonical, edit-in-place, NOT git).

## What shipped (Wave-0 — audit-gate converged, owner-approved)
- **Audit-gate**: reconciled our 13-agent discovery + an **independent Codex control-plane audit**
  (8 artifacts, `Documents/Codex/2026-07-13/.../outputs/`) + prior queues + direct git/disk verification.
  Deliverable: `docs/phase3-discovery-2026-07-13/AUDIT-DESIGN-CONVERGED.md`.
- **Ground truth confirmed**: enforcement was **inert on live** (repo AHEAD of live, not a fork); Stop-loop
  fix live+backed-up; agent-mail `:8812` DOWN (supervisor task dead — quick-fix `Start-ScheduledTask
  MCPAgentMailSupervisor`); Codex wrongly claimed "no deploy receipt" (both exist).
- **CAS-lite deploy** built (`install.py deploy()`, commit `6fa8047`): LOCK → PLAN → BACKUP → STAGE →
  pre-write-CAS-abort-on-change → per-file `os.replace` → post-write-parity+restore → receipt.
  Right-sized (owner's exact spec; NO 11-state journal / compensation engine / bundle store). +7 tests,
  456 harness tests green. Deploy-plan adversarially reviewed (5 must-fixes closed) + code-traced.
- **DEPLOYED** clean `git archive HEAD` → live (held task-9 excluded). Enforcement now LIVE
  (`_canonical_config_edit_guard`/`_basic_memory_nudge`: 0 → 4 matches). Live imports clean; hot-swap safe.
- **CLAUDE.md** (worktree) AgentBridge section → RETIRED pointer.

## Owner decisions (CONFIRMED)
- Canonical repo = **fold `ast-harness-reconcile` → `agent-skills-toolchain`** (already a worktree of it;
  fold = merge branch to mainline via PR — link offered on push, owner's call).
- MCP = **launch-read `.mcp.json`** restructure (+ one-time closed prune, needs Claude fully closed).
- Architecture = **right-sized + CAS-lite** (reject Codex's fleet-grade RFC).
- Axis B = **preserve-by-reference** → EVOLVED: owner reframed it as the orchestration CORE of Axis-C.

## Known-open (NOT Wave-0 scope)
- `install.py --check`: `hooks.claude` OK; **`hooks.codex` config drift** (pre-existing; deploy touched
  only the harness TREE not `settings.json`) → Codex-parity/config-reconcile wave. Drift-detector WORKING.
- `BACKUPS_DIR` puts the live-backup in `<repo>/ci/harness/backups/` (gitignored) not the live tree — minor smell.
- `source_commit: null` in receipt (deployed from non-git archive) — cosmetic; SHA `6fa8047`.

## NEXT — Axis-C: unified cross-vendor workflow/orchestration/monitoring/mingling (FRESH SESSION)
Owner's vision (fold into ONE design): **task-9 `codex-invoke`** (scoped Codex exec primitive; HELD,
complete but self-reviewed only — files: `tools/codex/profiles/`, `skills/codex-invoke/`, `guides/
codex-invocation.md`+`codex-monitor-reconcile.md`, `modules.py` +56/−11 ~/.codex edit-guard, uncommitted)
+ **Axis B** = the 48KB `ULTRACODE-HARNESS-SOTA-DECISION-QUEUE` orchestration engine (`agent()/parallel()/
budget()`; ~0% overlap w/ SSOT — see `AXIS-B-PRESERVE-INDEX.md`) + **wfmon** improvements (views, filters,
command-native, CLEAR ultracode-native-Claude-workflows vs OURS distinction) + native `/workflows`+ultracode
PARITY + **Codex↔Claude MINGLING in workflows** (mixed-vendor agent teams, not codex-only/claude-only).
Also: read the OTHER Claude session that ran `✳ DIAGNOSE_AND_OPTIMIZE` and fold it in.
Through-line: one workflow system where any agent is Claude OR Codex (mingled), scoped per-call (task-9),
orchestrated by one engine (Axis B), monitored uniformly (wfmon), matching native `/workflows`.

Do Axis-C as a design-gate (read → design → grill/review), NOT a build-first. Discovery already exists —
reconcile, don't re-swarm.

Related: [[project_harness_session_scoping_fix_2026-07-11]] · [[project_codex_parity_config_2026-07-11]] ·
[[reference_mcp_nodrift_architecture_2026-07-04]] · [[feedback_peer_review]] · [[Gem-hunt program 2026-07-12]]
