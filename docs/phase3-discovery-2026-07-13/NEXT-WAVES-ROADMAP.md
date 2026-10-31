---
title: NEXT-WAVES-ROADMAP
type: note
permalink: dqverify-repo-20261013/docs/phase3-discovery-2026-07-13/next-waves-roadmap
---

# Next-Waves Roadmap — post Wave-0 (2026-07-13)

Wave-0 (harness config SSOT: CAS-lite deploy + enforcement live + push) is **DONE**
(`RECONCILE-LOG.md`, `AUDIT-DESIGN-CONVERGED.md`). This plans the remaining waves. Owner-approved
sequencing: fold-PR + MCP-promote-prep **now**; the heavy Axis-C ultracode Workflow + Wave-1
continuation run **after the restart** (fresh context).

## Wave 1 — Config-reconcile + deploy-hardening (the Wave-0 known-open)
Small, mechanical, high-value — fixes what the SSOT drift-detector already flags.
1. **hooks.codex drift** — `install.py --check` flags `hooks.codex` (removed events) vs
   `build_hooks("codex")`. Reconcile: decide whether the live codex hooks or the generated set is
   canonical, then align. (`hooks.claude` is already OK.)
2. **Deploy smell — `BACKUPS_DIR` location**: pre-deploy live-backup lands in
   `<repo>/ci/harness/backups/` (gitignored) not the live tree. Point `BACKUPS_DIR` at the live
   target's own `backups/` so last-known-good travels with live. +test.
3. **Deploy smell — `source_commit=null`**: receipt records null when deployed from a non-git
   archive. Add a `source_commit` param to `deploy()` (runner passes `git rev-parse HEAD`) so the
   receipt is auditable. +test.
4. **agent-mail `:8812` DOWN** — supervisor task dead. Restart + verify self-healing
   (`Start-ScheduledTask MCPAgentMailSupervisor`; confirm `/api/health`), and investigate why the
   always-on supervisor died.
5. **MCP launch-read `.mcp.json` (D0.5)** — restructure so MCP config is a launch-read file
   (sidesteps the `~/.claude.json` clobber-race). One-time `promote-mcp-userscope.ps1
   -PruneExtraUserServers` at a Claude-closed restart for the current cleanup.

## Wave 2 — Axis-C: unified cross-vendor workflow (the post-restart ultracode Workflow)
Design-gate → build. The e2e ultracode Workflow the owner wants — SOTA + harness best-practices.
Folds: **task-9 codex-invoke** (scoped Codex exec primitive) + **Axis-B** orchestration engine
(48KB ULTRACODE queue) + **wfmon** improvements (views / filters / command-native + CLEAR
ultracode-native-vs-ours distinction) + native `/workflows`+ultracode parity + **Codex↔Claude
mingling in workflows** + fold the other `✳ DIAGNOSE_AND_OPTIMIZE` session. See the basic-memory
checkpoint (`harness-ssot-wave-0-shipped-axis-c-...`) + `AXIS-B-PRESERVE-INDEX.md`.
Run as: read → design → grill/review → build (reconcile existing work; do NOT re-swarm discovery).

## Wave 3 — Config-SSOT completion (from AUDIT-DESIGN-CONVERGED §4-§5)
- SessionStart drift-audit anchor (not the maybe-never-fired `ConfigChange`).
- 13 MCP drift-ins: promote/prune per the audit; fix codacy/deepsource at the plugin-bridge layer.
- Doc-librarian sweep (scattered `.md` reconcile) + stale-branch triage (salvage-first).
- Promote the 2 enforcement gates SHADOW→ADVISE after burn-in.

## Standing actions
- **Fold PR (D0.2)**: `chore/enshrine-runtime-config` → mainline. Stacked on `feat/codex-fleet-github-wave2` (see PR).
- MCP user-scope promote — Claude-closed (do at the restart).