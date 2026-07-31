# Cross-Vendor Dispatch (Claude → Codex, and any agent that shells to another agent runtime)

Ledger-proven 2026-07-18 (`wf_82c5b350-9ba`): 3 Codex-backed subagents produced **0 production
artifacts** against 16 files from 2 Claude peers. The failure was in the ADAPTER, not the vendor —
Codex's coding quality was never actually exercised. These rules close each observed hole.

## 1. A work-unit dispatch MUST be JOINED. Fire-and-forget is banned.

**Reconciliation with AGENTS.md §4a — read this first.** §4a requires any op expected to
run longer than 60s — *expressly including "long Codex generations" and "multi-agent
dispatch"* — to run under `longrun` with `run_in_background`/`Monitor`, never as a
blocking foreground call. A
cross-vendor work unit routinely exceeds 60s. Read as a ban on backgrounding, this rule would
leave a 300-second awaited dispatch with **no compliant launch mode** — foreground violating
§4a, background violating this rule. It is not such a ban. The two rules govern different axes:

| axis | owner | requirement |
|---|---|---|
| how the PROCESS is launched | AGENTS.md §4a | >60s ⇒ `longrun` + `run_in_background`, watched by `Monitor` |
| when the AGENT may return | this rule | only after the run reaches a terminal state AND §2 passes |

**Background the process, never the obligation.** Launching under `longrun` with
`run_in_background` and then blocking on `Monitor` until the run terminates is **COMPLIANT** and
is the required shape for anything over 60s. What is banned is *returning to the barrier while
the unit is still running*.

- NEVER release a fan-in barrier before the dispatched run has reached a terminal state. That
  bans `--background`, `&`, `nohup`, `spawn(detached)`, or `run_in_background` **without a join**
  — not the backgrounded launch itself.
- NEVER return a job id, a `"started in the background as task-…"` string, or a
  `"Check /codex:status"` receipt as a work-unit result. One agent's ENTIRE final answer was such
  a receipt; its job then COMPLETED on disk and the real finding was discarded unread.
- Prove the join is real. An unjoined background job's result is unreachable in practice: jobs
  written from a subagent carried `sessionId: null` while the status command filtered by session
  id, so `null === "<id>"` hid every one of them. *(That specific mechanism is historical — the
  `codex-companion.mjs` / `lib/job-control.mjs` companion is not present in this repo. The
  failure mode it demonstrates is not: any launch whose result you cannot address is a silent
  loss, so pin the run id and the `-o/--output-last-message` path at launch time.)*

## 2. Blocking on process exit is NOT proof of completion (AND-gate ≥2 signals)

Observed: a foreground call with `timeout: 1800000` returned after **6m59s** carrying only a
progress prefix, and the agent forwarded that raw stderr stream as its terminal result while its
own job record still read `status=running`. Before claiming SUCCESS require ALL of:

1. exit code 0, **AND**
2. the `-o/--output-last-message` file exists, is non-empty, and parses, **AND**
3. it validates against the caller's schema.

(1) without (2) is `SEVERED`, not `SUCCESS`. Never parse the `[codex] …` progress stream as a
result — that stream is what one agent mistook for its answer.

## 3. Prompt by FILE, never inline

- Windows `CreateProcess` caps the command line at **32,767 chars**. An inline prompt produced
  `payload_len=34472` → `os error 206` and killed both Codex runs that attempted real work.
- The Bash transport also truncates large heredocs: empirically 4,500 B OK / 13,650 B FAIL
  (exact threshold UNVERIFIED). One agent burned ~9 min and 4 tool errors rediscovering this.
- `codex exec` accepts stdin (`-`), and `codex-companion.mjs:643` already supports
  `--prompt-file`. **Both were undocumented in `codex-rescue.md` and the `codex-cli-runtime`
  skill** — that documentation gap is what cost the 9 minutes.

## 4. `--ignore-user-config` on every non-interactive Codex invocation

The active MCP inventory is what blows the arg limit. This is the #1 EXECUTION blocker and is
independent of the dispatch bug. It also dodges the typed `--output-schema` × active-MCP landmine
(codex issue #15451) already recorded in the `workflow-authoring` skill §9.

## 5. Model floor

Never `model: sonnet` on a dispatching agent. Dispatch judgement — background-vs-foreground,
timeout selection, prompt marshalling — is exactly what went wrong, and it violates the standing
opus-for-substantive-subagents preference. Note this CONFOUNDS any Claude-vs-Codex comparison run
on the old definition: it was sonnet-driver vs opus-driver, not GPT-5.x vs Opus.

## 6. Always a terminal state (AGENTS.md §4)

`SUCCESS:<wu-id>` + payload, or `FAILED:<wu-id> <reason>` + the diagnostic tail. **Never return
nothing** — `codex-rescue.md`'s "if the Bash call fails … return nothing" is an unrecoverable hole
in a fan-in barrier. Taxonomy: `severed-stream` · `codex-exit-<n>` · `win-arg-limit` (auto-retry
ONCE with `--ignore-user-config`) · `timeout-<n>s` · `schema-invalid`.

## 7. Timeouts

Any agent that shells to another agent runtime must set an EXPLICIT Bash `timeout` (30 min) and
run under `longrun` (AGENTS.md §4a). "Under `longrun`" means backgrounded-and-monitored per §4a;
§1's join requirement is what keeps that compliant, so there is no conflict to resolve here. The
silent 10-min default is what one agent rationalised `--background` to escape — the fix is the
explicit timeout plus the join, not an unmonitored detach.

**§1 and this section do NOT conflict — read §1 as banning ABANDONMENT, not backgrounding.**
`longrun` backgrounds its child by construction, so a literal reading of §1 would make §4a
unreachable and leave a >60s dispatch with no compliant path at all. The invariant is: you may
background ONLY under `longrun`, and you MUST then block on `Monitor` until the job reaches a
terminal state and you hold the `-o` payload. Returning a job id, a receipt, or anything before
that payload is the banned thing.

## 8. `codex:codex-rescue` is NOT a work-unit agent

By its own description it is a rescue forwarder for "when Claude Code is stuck". Use
`~/.claude/agents/codex.md` (synchronous adapter) for work units. Do not place any forwarder on a
critical path.
