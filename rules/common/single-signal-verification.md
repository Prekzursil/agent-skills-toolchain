# Single-Signal Verification (two independent signals before a load-bearing claim)

**A single tool's silence or single reading is NOT evidence.** Before asserting that something
is *absent*, *broken*, *stuck*, or *done* — especially when the next action is disruptive (a
restart, a kill, a "re-fix", a rollback) — corroborate with a SECOND, mechanically-independent
probe. If the two disagree, the first was likely a measurement artifact, not ground truth.

This is the most expensive recurring failure mode. SIX live instances in ONE session
(2026-07-18), every one a wrong conclusion from a single unverified signal:

| Wrong claim | Single signal (the artifact) | Independent signal that corrected it |
|---|---|---|
| "ctx 100% — restart the run" | cumulative `total_token_usage` as the ctx numerator | **last-turn** `last_token_usage / window` (the real occupancy) |
| "agents are stuck / 0 KB" | a stale cached file-size snapshot | CPU-delta over 20 s **AND** byte-growth of the err logs (86-142 KB, climbing) |
| "`mon` is not on PATH" | `which mon` in **Git-Bash** (ignores `.cmd` shims) | `Get-Command mon` in **PowerShell** → resolves `mon.cmd` |
| "the board always dies" | a `-match` regex with `\c` (a .NET control-char escape → never matched) | fix the regex → four surviving boards were there all along |
| "codex agents are fire-and-forget" | turn-count alone (3 turns ⇒ didn't wait) | **wall-clock delta** (a 3-turn peer blocked 20m35s) **AND** the literal `--background` token in the command string — both one grep away |
| "the Remove-Item guard was a true positive" | the blocked command's **payload** (a doc body quoting `Remove-Item`) | the `tool_use` **input verb** — both fires were `Set-Content` writing markdown, 2/2 false positives |
| "the FB/WhatsApp MCP has no auth" (2026-07-19) | `fb_account_list` / `wa_account_list` → `accounts: []` (the *alternate-profile store*) | `whoami` → live `{uid, name}` **AND** `wa_search_messages` → real messages with `is_from_me` — the session WAS authenticated; `[]` meant "no alternate profiles", a different field |
| "the PR is BLOCKED = its checks are missing" (2026-07-19) | `mergeStateStatus: BLOCKED` read as "not yet run" | the `quality` run's `conclusion=failure` — the checks had **run and failed**; BLOCKED ≠ pending. Fixing one gate then revealed the next (jobs stop at the FIRST failing step) |
| "the MCP disable took effect" (2026-07-19) | `disabledMcpServers` present at **root** of `~/.claude.json` | the **process table** (320 live MCP procs, disabled servers spawning 10 min post-restore) **AND** the pre-restore backup (key lived per-*project*, not root) — root-scope was inert |

## The rule

1. **Absence/failure needs corroboration; success needs corroboration.** "Nothing there",
   "it crashed", "it's done" — each is a claim, not an observation, until a second independent
   probe agrees.
2. **The two signals must be mechanically independent** — a different shell, a different data
   field, a different measurement (process CPU vs file mtime vs byte-count), not the same query
   re-run. Re-running the same probe is not a second signal.
3. **Verify the detector before trusting the absence.** A "0 results / not found / 0 alive"
   reading is often a broken matcher, wrong shell, wrong path, or stale cache — check that the
   detector *can* find a known-present item before concluding nothing is present.
4. **Terminal-state discipline (AGENTS.md §4):** `DONE` only on receipt **AND** postcondition;
   `FAILED`/`STALLED` only on an AND-gate of ≥2 signals — never single-signal, never CPU-alone,
   never mtime-alone.
5. **A subagent's finding is a single signal too.** N subagents asserting the same thing is
   still one lens if they read the same stale input — verify load-bearing subagent claims
   against the real config/code before acting (this rule caught a "ground truth" that three
   design agents carried forward from a stale premise).

## When it bites hardest
Long autonomous loops, fan-out monitoring, RE offset work, "is it done yet" polling, and any
moment the *fix* is disruptive (restart / kill / force-push / rollback). The cost of a second
probe is seconds; the cost of acting on a false signal is a wasted restart, a killed sibling,
or a wrong "done". Pairs with `fresh-context-verify` (re-derive a load-bearing value in a clean
context) and the two-strikes pivot (AGENTS.md §4b).

**Auditors are not exempt.** In this same session an audit agent reproduced the exact failure it
was documenting — reading a blocked command's *content* instead of its *verb* — and shipped the
opposite of a sibling audit's correct verdict. Two same-level reports that disagree are a
resolve-from-raw-source trigger, never a pick-one trigger.
