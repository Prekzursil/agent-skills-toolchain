---
title: Unified Monitor Cockpit program + session learnings 2026-07-18
type: report
permalink: main/projects/harness/unified-monitor-cockpit-program-session-learnings-2026-07-18
tags:
- compaction-checkpoint
- monitor-cockpit
- harness
- self-reflect
- '2026-07-18'
---

# Unified Monitor Cockpit — program checkpoint + session learnings (2026-07-18)

**Session:** 30bd50d4-5a72-4c19-8fd5-85b6430c7b7d. **MASTER INDEX to every doc:**
`C:\Users\Prekzursil\.claude\monitor-harness-ultracode-2026-07-18\README-INDEX.md` (read this first).
Authoritative decision record: `unified-monitors/GRILL-DECISION-LOG.md`.

## The program
ONE unified interactive cockpit watching EVERY monitor (wfmon, agentmon, codexmon, compute-monitor,
mon-audit, cs, + salvaged taskwatch / supervision-registry / event-ledger / mcp-fleet / GitHub Actions):
each becomes a thin monitorcore `MonitorSource` adapter rendered by ONE shared presentation
(stdlib-SSE **web** + Textual **TUI**, built together) + a localhost **control daemon**.

## LOCKED (owner-steered; full detail in GRILL-DECISION-LOG.md)
- **Framing:** unified Claude+Codex · shared monitorcore core (extend in-place) · web+TUI together ·
  full control daemon (`control_kind` + owned-set PID firewall + Job-Object tree-kill) · session_id
  dedup · SQLite FTS5 tail-index · **≥2-signal corroboration processor stage** (the governing
  invariant) · **everything-in-one-wave** · central `~/.claude/workflows/` + `~/.claude/sessions/`
  named-index folders + auto-save hooks · **metaswarm-orchestrated + TDD + parallel worktrees** build.
- **wfmon = HYBRID:** salvage its journal.jsonl data layer, rebuild the presentation, retire the
  bespoke Textual app.
- **U1-U20 all locked.** Notable owner overrides: unify ALL 7 monitors identically (cs full,
  D:\agent-monitor UX absorbed); **REWRITE the PowerShell monitors in Python** with parity + 100%
  tests (not a SubprocessSource bridge); build the live Gantt NOW; build the alert rail NOW;
  RAM-adaptive bounded polling (my addition — back off concurrency under memory pressure).
- **X1-X18 all locked.** Guardrail rules first · Stop+SessionStart workflow-mirror (copy2, survives
  project GC) · sessions index (hardlink if atomic-replace check passes, else pointer JSON) · ONE
  cockpit auto-engage (widen matcher, retire 2 dedicated hooks) · machine-wide launch lock · focus via
  daemon POST + file-drop fallback · sessions board (4 feeds + locks) · agent-mail leases ·
  **default-WARN** conflict guard (hard-lock collapses fleets) · worktree mandate · **all 3
  codex-interchange lanes** (A canonical adapter + B mcp one-off + C detached fan-out) · full
  mcp-manager integration (McpFleetSource + control arm + pop-out).
- **X12 = C (full layered Codex edit-gating):** worktree belt + fan-out pre-lease wrapper +
  observe-and-reconcile with auto-revert/watchdog + track openai/codex#27833.
- **Added requirements:** E5 salvage revivals · **E6 one canonical cwd-independent config home**
  (user/managed scope + audit per-project overrides) · **E7 GitHubActionsSource** (runners self-hosted
  + cloud, workflow runs, cancel/rerun control).

## Blockers (do NOT assume solved)
- **B1** auto-engage focus needs a parent `--focus` flag + daemon focus endpoint that grep proved
  DO NOT EXIST → parent-side add, fast-follow.
- **B2 (CORRECTED):** Codex CLI *does* have a native hook system and its PreToolUse *does* fire on
  `apply_patch` — but **deny is NOT enforced** (empirically proven; openai/codex#27833, Windows). So
  Codex edits are observable, not preventable, via its own hook. Prevention = worktrees + pre-lease wrapper.
- **B3** `Agent(codex)` interchangeability — now **partly proven**: routing a Workflow work-unit via
  `opts.agentType: 'codex:codex-rescue'` spawned correctly this session.
- monitorcore lives on `origin/main` (tools/monitorcore + skills/workflow-monitor) but NOT on the
  checked-out `harness/upgrade-2026-07-17` → build from a clean `origin/main`. Live copy:
  `~/.agents/skills/workflow-monitor/monitorcore/`.

## Next step
Finish the mega-audit integration pass + the mcp-live-control verdict → CONSOLIDATE all queues into
ONE master implementation plan → plan-review gate (3 adversarial reviewers) → metaswarm TDD build in
parallel worktrees.

Relates to [[single-signal-verification-rule-2026-07-18]],
[[project_session_2026-07-11_reframe_v15_harness]], [[reference_mcp_nodrift_architecture_2026-07-04]].
