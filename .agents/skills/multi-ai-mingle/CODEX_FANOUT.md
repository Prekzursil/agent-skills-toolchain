# Codex fan-out: fragility + safe pattern

> **Additive companion to `multi-ai-mingle/SKILL.md`** (clearly-marked new section,
> authored 2026-07-17). Deploy: copy into the live skill dir
> `~/.agents/skills/multi-ai-mingle/CODEX_FANOUT.md` (and the `~/.claude/skills/`
> mirror if synced), and add a one-line pointer under SKILL.md "Files in this skill".
> The fan-out rail (Claude drives N parallel Codex threads) is powerful but
> fragile in specific, repeatable ways. These are ledger-proven from real
> multi-Codex sweeps — treat them as hard operating limits, not tips.

## The safe pattern (do this)

Fan out **one fresh clone per Codex agent**, each on its **own branch**, launched
**detached** (`nohup … &` / a background job), so agents never share a working
tree and cannot stomp each other's files:

1. `git clone` (or `git worktree add` off a **freshly-pushed** main) into a
   per-agent dir; check out a per-agent branch (`codex/wu-<n>`).
2. Launch each Codex thread detached against its own clone. Capture its pid/log.
3. A **background `git ls-remote` push-watcher is the real deliverable signal** —
   poll the remote for the agent's branch/commit landing; that is what "done"
   means, NOT the agent's own "I finished" claim (self-report is gameable).
4. The **orchestrator verifies before merge — never self-cert.** The agent that
   wrote the code does not get to certify it; an independent re-check (tests +
   diff review) gates the merge.

## Fragility limits (respect these)

- **Concurrency RAM cap = 3.** Each Codex thread carries a full MCP fleet + a
  clone; past ~3 concurrent the box OOMs. Ledger: a 9-wide fan-out **OOM'd 9
  agents** at once. Cap the pool at 3 and queue the rest.
- **Shared app-server cascade — killing ONE kills ALL.** Every Codex session on
  this machine shares one backend app-server process tree; `taskkill /T` on one
  session's tree **terminates every Codex session**. To stop a single agent, do
  it from that agent's own terminal / thread, never a tree-kill. (Claude sessions
  are independent; Codex sessions are not.)
- **Shared `auth.json` → stagger launches.** All Codex threads read one
  `auth.json`; launching them simultaneously races the token refresh and throws
  **"refresh token already used"**, killing late starters. **Stagger** launches a
  few seconds apart so the first refresh settles before the next reads it.
- **ALWAYS `git push` origin/main after each merge.** Fresh clones clone
  **whatever main currently is on the remote**. If you merge a work-unit locally
  but do not push, the next agent's fresh clone gets a **STALE main missing the
  dependency** the previous unit added, and its build/tests fail for a reason that
  has nothing to do with its task. Push after every merge, before spawning the
  next clone.

## When an agent is stuck (two-strikes)

- On the **second** failed attempt on the same work-unit (two strikes), STOP
  re-running it. The usual root cause of a Codex unit that keeps dying is
  **context exhaustion** — the unit is too big and the thread hits ctx-100% and
  collapses. **Split the ctx-100%-dying unit into smaller sub-units** and fan
  those out, rather than retrying the whole unit a third time. Escalate to the
  orchestrator for re-decomposition if a split still fails.

## One-line checklist

fresh-clone-per-agent → own branch · detached launch · **cap 3** · stagger for
shared auth.json · **push main after every merge** · ls-remote push-watcher =
done-signal · orchestrator verifies (never self-cert) · two-strikes → split, not
retry · single-agent stop from its own terminal (tree-kill cascades to all).
