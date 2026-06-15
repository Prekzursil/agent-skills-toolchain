# Cross-Tool Behavior Contract

**Applies to:** Claude Code · Codex CLI · Antigravity (agy)  
**Version:** 2026-06-11 · Workspace Design v1 (Behavior-Enforcement Matrix)  
**Authority:** This file is the single behavioral contract shared across all three tools.  
Provider-specific addenda live in each tool's own config; conflicts resolve in favor of this file.

---

## 1. Front-load clarification (pre-execution only)

Before starting any long-horizon or ambiguous task:

- Restate your understanding of the goal in one sentence.
- When material ambiguity remains, ask 1-3 targeted questions rather than proceeding on assumptions.
- Timing: first 1-2 actions only. **Never ask mid-task** — mid-execution clarification amplifies prompt-injection risk 15-16x (ASPI research finding).
- **Bypass:** a prompt prefixed with `*` signals the user has already scoped it — skip clarifying questions entirely.
- Gate questions by EVPI: only ask when the answer would materially change your approach. Do not rubber-stamp obvious tasks with pro-forma questions (93% of unchecked clarifications are rubber-stamps).

## 2. Keep the whole goal in view (anti-tunnel-vision)

- Every N turns, re-read the original goal and check whether your current action still serves it.
- If you detect drift (current action no longer serves the stated goal), surface it explicitly before continuing.
- **Goal re-injection is owned by the PreToolUse hook** (injects verbatim from the event ledger). If it fires, treat the injected goal as authoritative.
- Do not fixate on one detail and silently abandon the broader objective.

## 3. Record decisions and failures to the event ledger

- Record durable findings (decisions, failures, milestones) via `note.py`:
  ```
  python ~/.claude/hooks/event-ledger/note.py --kind decision "text"
  python ~/.claude/hooks/event-ledger/note.py --kind failure "text" --preconditions "version/env/error-sig"
  python ~/.claude/hooks/event-ledger/note.py --kind milestone "text" --supersedes 3,5
  ```
- Failure entries must carry falsifiable preconditions. A milestone that contradicts a failure should --supersedes it so the dead-end is retired, not re-walked.
- The Stop hook writes objective turn data automatically. Use note.py only for the *why* (decisions, rationale, failures) that hooks cannot see.
- The SessionStart hook replays the ledger on resume/compact/clear — trust that replay as ground truth, not any in-context summary.

## 4. Prefer terminal-state tool outputs

- Format tool results as `SUCCESS:<id>` or `FAILED:<id> reason` rather than open-ended prose.
- This is the primary defense against repetitive-action loops (reduces repeat invocations ~7x before any detector fires).
- Anti-degeneration fingerprint = `(tool, args_hash, output_hash)` — never input-hash alone (polling tools like `server_health` have identical args by design and would false-positive on an input-only hash).

## 4a. Wrap long operations with `longrun` (>60s)

- Any op expected to run >60s (test suites, coverage, `lizard`/`semgrep` over a tree, CI/`--watch`, long Codex generations, multi-agent dispatch, self-written `Start-Sleep` polls) MUST run via `longrun` launched with `run_in_background`/`Monitor` — never a blocking foreground call. Helper: `C:/Users/Prekzursil/source/agent-skills-toolchain/scripts/longrun.ps1` (Windows) / `longrun.sh` (bash).
  - `pwsh -File <…>/longrun.ps1 -Id <id> -HeartbeatSec 15 -HangTimeoutSec <120|180|300> -Cmd <exe> <args…>` — options are named-only; the wrapped command + its args follow `-Cmd`. Bash: `longrun.sh -i <id> -h 15 -t 180 -- <exe> <args…>`.
  - Streams `HEARTBEAT <id>: <elapsed>s | <last line>` and ends with the §4 `SUCCESS:<id>`/`FAILED:<id>` marker — that marker IS the output-hash the anti-degen fingerprint needs for long calls.
- Stop-and-report: on a status request, re-read the printed log path (`-Tail 30`) + diff changed files; do NOT re-run the command to "check" it.
- Codex mirror: wrap long Codex CLI generations the same way (`codex-cli-runtime` + `codex-result-handling`).

## 5. Structured subagent handoffs (no raw-output prefix)

- Never pass a subagent's raw output as the prefix context for the next agent.
- Always: structured summary (bullet points, typed sections) with the original goal re-anchored at the top.
- Rationale: subagent drift is inherited down the chain. Re-anchoring cuts compounding divergence.

## 6. Block only dangerous; inject for everything else

- **Exit 2 (block):** irreversible or dangerous operations only — destructive git ops, secrets in code, force-push to main without explicit approval.
- **Exit 0 + additionalContext (inject):** all other guidance — routing, reminders, goal injection.
- Never block on ambiguity; inject a clarifying route instead.
- All hook code must be wrapped in try/except; any hook error must exit 0 (fail-open). A crashing hook is worse than a silent one.

## 7. Honesty and anti-sycophancy

- Before surfacing a conclusion to the user, run an internal generator-critic pass: would a fresh-context reviewer with no prior conversation agree?
- Do not adjust your assessment based on user tone, repeated asking, or apparent disappointment.
- Sycophancy is in model weights; external-signal checks are the only reliable counter.

## 8. Memory and continuity

- The canonical memory store is `basic-memory` (semantic, D: vault). Pull proactively after compaction or when user references prior work.
- The event ledger (`~/.claude/event-ledger/`) is the objective ground truth for turn history. It is NOT a replacement for basic-memory — they serve different roles (objective vs. semantic).
- CLAUDE.md stays under 300 lines. Do not accumulate prose; write durable facts to basic-memory instead.

## 9. Security non-negotiables (all tools)

- Never hardcode secrets. Use environment variables; validate presence at startup.
- Never `--no-verify` on commits without explicit user instruction.
- Never `git push --force` to main/master without explicit user approval.
- Validate all user inputs at system boundaries. Sanitize before HTML output.

---

*Backup of previous ECC AGENTS.md: `~/.claude/AGENTS.md.bak-ecc-2026-06-11`*
