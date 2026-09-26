---
title: Deep-research batch (2nd scan) implemented + crash recovery 2026-06-15
type: milestone
permalink: main/projects/learnings/deep-research-batch-2nd-scan-implemented-crash-recovery-2026-06-15
tags:
- hooks
- deep-research
- crash-recovery
- async-validate
- implemented
---

# Deep-research 2nd scan implemented + survived a terminal crash — 2026-06-15

**[milestone] The 2nd modus-operandi scan (efficiency+memory focus, 8 items) is implemented and committed** (`5aa8076` on `feat/optimal-agentic-workspace` in agent-skills-toolchain; NOT pushed). All live in `~/.claude/` + mirrored into the `agent-self` snapshot. Distinct from the 1st-scan batch (`12102d8`).

**The 8 (all built by parallel subagents, individually verified):**
1. fork-cache `CLAUDE_CODE_FORK_SUBAGENT=1` (settings env) — ~90% input savings on fan-out.
2. `~/.claude/hooks/stopfailure-notify/` — StopFailure hook, notifies on API-error/rate-limit/billing turn-ends.
3. `~/.claude/hooks/cmd-rewrite/inject-nopager.py` — PreToolUse updatedInput, kills Git-Bash pager hangs.
4. `~/.claude/hooks/async-validate/validate.py` — PostToolUse asyncRewake per-file validator. **SEE WAKE-LOOP ISSUE BELOW.**
5. `agent-skills-toolchain/tools/memory-bench/` — basic-memory recall regression suite. **Baseline 81% (13/16)**; weak spots contradiction (50%) + multi-session-temporal (67%). Uses a SCRATCH vault, never D:\basic-memory.
6. `agent-skills-toolchain/skills/rubric-verifier/` — execution-free N-candidate patch selector (advisory).
7. `agent-skills-toolchain/tools/triage-router/` — code-health→model-tier cost router (metaswarm/Ralph dispatch).
8. `~/.claude/hooks/cmd-rewrite/compress-output.py` — PostToolUse updatedToolOutput, collapses noisy Bash output.

**⚠️ async-validate (#4) WAKE-LOOP — real design flaw.** A SEPARATE session running a remediation workflow hit a degenerate loop: async-validate (asyncRewake, PostToolUse:Edit) re-runs ruff on EVERY edit and woke the main session on each transient ruff-dirty WIP edit — thousands of wakes. That session correctly diagnosed it and added a **sentinel kill-switch** to validate.py (`<hookdir>/.disabled` exists → exit 0), created `.disabled` to pause it, verified (no-sentinel→exit2, sentinel→exit0). **`.disabled` is currently PRESENT (hook PAUSED across all sessions).** MUST `rm ~/.claude/hooks/async-validate/.disabled` to re-enable AFTER that workflow (wgn5oq2ei) finishes. **Permanent hardening still pending** (circuit-breaker/dedupe, or move to Stop-time, or drop #4) — the per-Edit asyncRewake design is loop-prone in autonomous/workflow sessions; research graded it A but missed this real-world failure.

**Crash recovery:** terminal crashed mid-integration (killed the #5 builder's in-process state, but its files — memory_bench.py + probes.jsonl + results.json — were on disk; #5 was essentially complete). On restart: all hooks intact + registered, semgrep restored (uv-tool 1.166), basic-memory + MCP servers reconnected. The batch was uncommitted at crash → committed `5aa8076` on resume.

**Other pending (from the update sweep):**
- **C:\Python314 decapitated** — my `winget upgrade Python.Python.3.14` (failed, needed elevation) removed python.exe from a 2.66 GB Python env (ML/data stack intact). User chose RESTORE: reinstall Python 3.14.6 → C:\Python314 (elevated installer; steps given). NOT done yet. Hooks unaffected (use AppData pythoncore python).
- Tool updates needing elevation (user runs): JDK 21.0.11, Python 3.14.6, Node 24 LTS migration, gh, `winget upgrade astral-sh.uv`. Landed: deno 2.8.3, npm 11.17.0, MCP cleanup (figma deleted, browserstack/tavily unpinned), enableAllProjectMcpServers=true (this project).

See [[modus-operandi-upgrades-1-7-implemented-live-2026-06-15]] and [[micro-vm-os-sandbox-for-autonomous-loops-deferred-do-not-re-suggest-2026-06-15]].