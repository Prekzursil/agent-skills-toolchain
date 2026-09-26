---
title: 'Friction-mining items #1/#2/#4/#7 IMPLEMENTED 2026-06-15'
type: milestone
permalink: main/projects/learnings/friction-mining-items-1-2-4-7-implemented-2026-06-15
tags:
- friction-mining
- hooks
- implemented
- longrun
- claim-guard
- tool-preflight
- ci-lint
---

# Friction-mining adopted items #1/#2/#4/#7 — implemented + committed 2026-06-15

The session-friction-mining scan (mined the user's own 78GB of Claude+Codex transcripts) → grilled → built the 4 chosen items. All on `feat/optimal-agentic-workspace` in agent-skills-toolchain, vendored to the agent-self snapshot, NOT pushed. (#3/#5/#6/#8 archived — see [[archived-improvement-candidates-recorded-not-pursued-do-not-re-suggest-2026-06-15]].)

- **#1 longrun heartbeat** (`ab3a149`) — `scripts/longrun.ps1`+`.sh`: wrap any >60s op, stream `HEARTBEAT <id>: <elapsed>s | <last line>` via run_in_background/Monitor, end with `SUCCESS:<id>`/`FAILED:<id>` (+ hang-timeout→exit124). Addresses the #1 pain (constant "are you stuck/still running?" polling). **AGENTS.md §4a rule added (live + snapshot).** Bug I caught + fixed: added `[CmdletBinding(PositionalBinding=$false)]` so wrapped-command args can't leak into longrun's int params.
- **#2 claim-guard ci_gates** (`130ff66`) — `~/.claude/hooks/claim-guard/claim-check.py`: new STRICT claim category — "gates green / ready to merge" requires a real `gh pr checks`/`gh run view` in the Bash ledger (a green LOCAL build is NOT evidence). Warn-mode. Addresses the dominant correction ("you're not checking the gates, they're red"). HEAD-SHA + no-op checks live in #7.
- **#4 tool-preflight** (`5ae529f`) — `~/.claude/hooks/tool-preflight/preflight.py`: SessionStart existence-check (no spawn, <2s) of stdio-MCP interpreters + project CLIs → one digest of dead/missing + fix line. Registered live + snapshot. **Already flagged a real gap: `shellcheck` not on PATH.**
- **#7 ci-silent-pass-lint** (`d7f1291`) — `skills/ci-silent-pass-lint/`: deterministic `.github/workflows` linter for 11 silent-pass shapes (exit1 on HIGH) + `gate_findings_at_head.md` (the shared HEAD-SHA finding-count primitive #2 references; exact codacy/codecov/deepsource/qlty MCP tool names).

**Bugs caught by VERIFYING (not relaying) subagent output:** longrun PositionalBinding; mutmut is WSL-only (→cosmic-ray, #2-prior); npm key is `min-release-age` not `minimum-release-age`; mcp-scan renamed to snyk-agent-scan; F401s in mem-bench/ci-lint. Also `edit-validate` self-hardened twice (workflow top-level-return + %TEMP% scratch skip).

**Open:** `shellcheck` not on PATH (offer to install); `async-validate/` live orphan still locked by the other session (delete when free); Node migrated to 24 LTS (v24.16.0).