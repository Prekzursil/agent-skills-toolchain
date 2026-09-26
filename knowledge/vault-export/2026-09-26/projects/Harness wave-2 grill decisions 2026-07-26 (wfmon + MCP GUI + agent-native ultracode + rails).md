---
title: Harness wave-2 grill decisions 2026-07-26 (wfmon + MCP GUI + agent-native ultracode
  + rails)
type: note
permalink: main/projects/harness-wave-2-grill-decisions-2026-07-26-wfmon-mcp-gui-agent-native-ultracode-rails
tags:
- compaction-checkpoint
- monitor-harness
- decisions
---

Owner-answered 15-question `grill-me-extensive` round that scopes **wave 2** of the harness program. Full log on disk: `C:/Users/Prekzursil/.claude/monitor-harness-ultracode-2026-07-18/GRILL-DECISIONS-2026-07-26.md` (authoritative). **Reframe is explicitly OUT of scope** ("exclude reframe only what i told you").

## Four lanes, all ADDITIVE, home = `agent-skills-toolchain` `tools/`
1. **wfmon** — ONE board with **switchable panes** unifying EVERY monitor type on the box (Codex threads · Claude subagents · Workflows · MCP health · any others) + monitor **Phase-2 WU9-WU13**.
2. **MCP GUI** — cockpit **pane** + **localhost web GUI** (stdlib http.server + static HTML/JS) + **CLI**. All four capability groups required: health matrix · live enable/disable/reconnect · add/remove/edit configs · curation + token/RAM budgeting w/ impact preview. Three surfaces because a TUI pane cannot serve config-editing + curation tables well (owner's own fallback rule fires).
3. **Ultracode agent-native** — shared **spec** + **adapters** + **BOTH Python and JS runtimes**, each 100% line+branch, plus a real **eval harness**.
4. **Cross-agent extensions** — adapters for **Codex CLI** · **Antigravity (agy)** (owner: "gemini became antigravity") · **Grok** (an API, not a CLI) · **generic any-CLI/API**.

## Hard constraints
- **ADDITIVE ONLY.** NOT authorized: T1-1 fold-8-hooks, T1-4 skill-vault reconcile/trim, T1-9 retire-43-dirs. Live hooks tree + skill curation untouched. New paths may be deployed; existing ones may not be edited.
- **Isolated worktrees off freshly-fetched `origin/main`; never touch the main checkout** (it sits on parked `fix/mcp-health-agentmail-fbmessenger` w/ 40 uncommitted incl. plaintext-token accounts.json).
- **Done = merged AND running live**: 100% coverage gate → **fresh independent critic PASS** → merge → additive deploy → E2E verify. Critic is non-negotiable (last wave it caught a CRITICAL escape-injection my own workflow Verify had passed).
- **Triage if runway ends:** all four lanes land a working gated deployed CORE; defer the tail (WU12/WU13, JS parity, web-GUI charts).
- **Unverified rails:** probe first; verified → executed adapter; unreachable → adapter built to documented interface but labelled UNVERIFIED inline w/ the settling experiment. Never claim a rail works unrun.

## Deliberate anchor overrides (recorded, not hidden)
- MASTER-QUEUE §7 bars a **"2nd orchestration runtime"** — G-3 ("2+1") **overrides it deliberately**. Mitigation: the spec is the single source of truth; adapters translate so dialects cannot diverge.
- §7 bars heavyweight TUI (Textual 927ms/41MB, breaks no-venv) — honoured: the web GUI is stdlib-only, zero resident RAM when closed. No Textual/PySide.

## Ground-truth corrections from the grill
- `origin/main` moved 4 commits past my `350f808` merge (#216-#219 → `9dcfe86`). Always branch from a fresh fetch.
- A scout's "concurrent session is editing the repo" alarm was a **FALSE POSITIVE** — my own check: branch/head/dirty-count unchanged; reflog showed an *aborted* rebase + no-op checkout (my own prior activity). Detector failure, not a rival session.
- **`/harness-audit` is NOT runnable** here (needs `scripts/harness-audit.js` in the target repo; absent). Use `agent-harness-construction` + `eval-harness` vault docs.
- **`ui-audit`/`ui-drive` are web-or-Electron ONLY** (Playwright/CDP) → they legitimately apply to the lane-2 localhost web GUI. No native-Windows UI driver (pywinauto/FlaUI/WinAppDriver/UIA) exists in the vault.
- `visual-review` exists only as `metaswarm:visual-review`, despite the project CLAUDE.md reference.
- Reframe (out of scope) is at `C:/Users/Prekzursil/Documents/GitHub/Reframe`, NOT `~/source` — noted so the failed lookup is not repeated.

## Externally blocked / may end UNVERIFIED honestly
WU10 (needs a real Codex budget-truncation marker to observe) · WU13 (tagged NEEDS-ANTHROPIC for full relay run-id fidelity).

Follows [[monitor-cockpit-flagship-phase-1-merged-escape-injection-lesson-2026-07-25]].