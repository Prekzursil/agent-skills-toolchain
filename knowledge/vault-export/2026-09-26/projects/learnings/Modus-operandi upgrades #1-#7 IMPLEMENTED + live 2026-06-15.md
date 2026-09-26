---
title: 'Modus-operandi upgrades #1-#7 IMPLEMENTED + live 2026-06-15'
type: decision
permalink: main/projects/learnings/modus-operandi-upgrades-1-7-implemented-live-2026-06-15
tags:
- hooks
- mcp
- modus-operandi
- security
- implemented
---

# Modus-operandi research-scan upgrades #1–#7 implemented (live) — 2026-06-15

**[milestone] 7 of 8 research-scan candidates are now WIRED.** All hooks are fail-open (exit 0 on any error), non-nagging, and tested. Live in `~/.claude/` + vendored 1:1 into `agent-skills-toolchain/agent-self/config/` (commit `12102d8` on `feat/optimal-agentic-workspace`, not pushed).

**Live hooks (`~/.claude/hooks/`, registered in `settings.json`):**
- **#1 test-tamper-guard/guard.py** — PreToolUse(Bash). On `git commit`, warns if staged TEST files weakened (asserts removed, skip/xfail/.only added, `assert True` stub, test file deleted); logs event-ledger failure. Warn-mode.
- **#5 claim-guard/{ledger-write.py,claim-check.py}** — PostToolUse(Bash) NDJSON command ledger at `%TEMP%\claude-claim-ledger\`; Stop hook warns on success-claims ("tests pass"/"fixed"/"build green") with no supporting ok=true command. `CLAIM_GUARD_MODE=warn`(default)|`off`.
- **#6 memory-guard/scan.py** — PostToolUse(`.*`). Scans untrusted content-tool output (firecrawl/exa/scrapegraph/tavily/claude-in-chrome/WebFetch/…) for injection (override/role-spoof/exfil/hidden-unicode/base64); allowlists RE/security tools (ghidra/ida/frida/semgrep/sonar/…). ASI06.

**Config changes:**
- **#2** `~/.mcp.json` `semgrep` repointed: dead `semgrep-mcp.exe` (0.9.0, only `deprecation_notice`) → `npx -y mcp-server-semgrep` (wraps working semgrep CLI 1.165). **Requires a CC restart to load.** Real tools: scan_directory/list_rules/create_rule/analyze_results/etc.
- **#3** `agent-skills-toolchain/scripts/claude-autonomous.ps1` — launch wrapper `claude --fallback-model claude-sonnet-4-6` for unattended runs (ralph-loop replays in-session, so fallback only settable at launch). `--safe-mode` = harness-vs-model bisector.
- **#4** server-side context editing (`compact_20260112`) — INERT today (no SDK/API runs; CLI auto-compacts). Ready snippet in `docs/modus-operandi-upgrades-2026-06-15.md`. Reject bundled Memory tool (basic-memory canonical).
- **#7** `tools/ese-gate/ese_gate.py` — standalone execution-equivalence entropy escalation gate for the codex council (built+tested; council wiring is the user's to apply).

**Activation:** hooks + the semgrep MCP take effect on next CC restart. **#8 deferred** — see [[micro-vm-os-sandbox-for-autonomous-loops-deferred-do-not-re-suggest-2026-06-15]] (do NOT re-suggest). Full doc: `agent-skills-toolchain/docs/modus-operandi-upgrades-2026-06-15.md`.