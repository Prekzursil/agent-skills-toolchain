# MEL — Minimum Equipment List for the shared agent harness

> Wave D item 1 (2026-08-27), airworthiness trio part 1/3 (CONSOLIDATED-GEM-DECISIONS TOP-GEM #1).
> Aviation MEL logic applied to the harness: for each piece of equipment, may the harness
> **dispatch (keep working) with it inoperative**, under what **compensating procedure**, and on
> what **rectification clock** before continued dispatch is no longer allowed.
> Read this when a liveness check (mcp-liveness, watchdogs, sync failures) reports an item down —
> instead of improvising, apply the row. Dispatch categories:
> **GO** (proceed, note it) · **GO-WITH-COMPENSATION** (proceed only via the listed procedure) ·
> **NO-GO** (stop the affected work class until rectified).
> This file is a registry, not an enforcement mechanism; enforcement stays gated on Wave B evidence.

| # | Equipment | Inoperative dispatch | Compensating procedure while inoperative | Rectification clock |
|---|---|---|---|---|
| 1 | basic-memory MCP (127.0.0.1:8765) | GO-WITH-COMPENSATION | Do not silently skip memory writes: spool durable decisions to the active project folder / `memory-spool` hook and replay after recovery. Probe = `GET /mcp` → HTTP 406 is HEALTHY. Restart: `Start-ScheduledTask BasicMemory-HTTP-MCP`; watchdog self-heals in ≤ ~5 min. | Same session (watchdog); if still down after 2 supervised restart cycles → NO-GO for memory-dependent work, tell the owner |
| 2 | mcp_agent_mail (127.0.0.1:8812) | GO | Solo work unaffected. Multi-agent coordination degrades to file-based handoff (execution logs + agent transcripts). Restart: `Start-ScheduledTask MCPAgentMailSupervisor` (~27s recovery). | 1 day; coordination-heavy tasks wait for recovery |
| 3 | codex mcp-server (fan-out rail) | GO | Do the work in-session instead of fanning out; queue independent Codex work units in the execution log for later dispatch. Verify with `claude mcp get codex` → Connected. | 1 day |
| 4 | Claude dispatch hooks (`_dispatch/manifest.json` events) | GO-WITH-COMPENSATION | Hooks are advisory/inject; their loss removes instruments, not correctness. Compensate by running `verification-before-completion` manually before any completion claim. A manifest that fails to PARSE is a guard-file tamper signal → check `guard-tamper.log` first. | 3 days |
| 5 | Cursor hooks (`~\.cursor\hooks.json`, observe mode) | GO | Observe-only today — loss costs evidence, not safety. Log the outage in the execution log so the flip-decision week isn't counted against missing data. | 7 days (re-arm before the failClosed flip decision) |
| 6 | Codex execpolicy (`.codex\rules\default.rules`) | NO-GO for Codex-delegated shell work | The git-write ban and destructive-command rules are the only enforced Codex guardrail. If the file is missing/corrupt (tamper signal — check `guard-tamper.log`), restore from `.agents\backups\` before delegating anything to Codex. | Immediate |
| 7 | GuardTamperTracer + GuardTracerRound scheduled tasks | GO-WITH-COMPENSATION | Run `guard-tamper-check.ps1` / `guard-tracer-round.ps1` manually at session start until the tasks are re-registered. | 3 days |
| 8 | Statusline quota fields (`5h:`/`wk:` segments) | GO-WITH-COMPENSATION | Budget pacing falls back to judgment (weekly-quota principle in `~\AGENTS.md`); say the numbers are unavailable rather than guessing them. | 3 days |
| 9 | sync_shared_state.ps1 failing | NO-GO for skill/rule/MCP edits | Do not edit `.agents\skills`, rules files, or `agents.json` while sync is red — edits would strand undeployed. Diagnose with `agents status` / `agents doctor`. Read-only work continues. | Immediate for control-plane edits; other work GO |

## Tracer rounds (trio part 2/3)

A guard that never fires is indistinguishable from a broken one. `\.agents\scripts\guard-tracer-round.ps1`
(scheduled daily, DRY-RUN, no daemon) fires synthetic contraband through the observe-mode Cursor shell
guard and verifies the would-deny verdict; a guard that does not trip writes a **MEL-DEFERRAL** line to
`.agents\logs\guard-tamper.log` → apply row 5/6 above. File-integrity tampering on the guard files is
covered by the sibling `guard-tamper-check.ps1` (hash drift).

## Observational method (trio part 3/3)

Plans gain monitored metrics + pre-committed trigger-action responses — see the
"Observational Method" section appended to `writing-plans/SKILL.md` (2026-08-27). The pre-committed
response table is the point: decide BEFORE the metric moves what its movement forces you to do.
