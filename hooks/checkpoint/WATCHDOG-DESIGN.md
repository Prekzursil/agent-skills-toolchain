# Idle-agent watchdog — DESIGN ONLY (no runtime shipped this round)

Status: **DESIGN. Nothing in this directory implements it.** The lane brief says "design only
unless you can prove it safe", and the safety proof requires a precondition that does not exist
yet (see §6). Shipping a detector that cannot separate *hung* from *finished* would reproduce a
failure this estate has already paid for.

---

## 1. The premise that must not be repeated

> "Stall detection from file-mtimes alone is IMPOSSIBLE — don't ship it."
> — `rules/common/bash-hud-and-terminal-emit.md` §3

A stalled process and a long-completed one are **indistinguishable from mtimes**: both simply stop
updating their file. The measured cost: a statusline "subagent stall" segment flagged an
**11-hour-old finished** agent as a live stall. mtimes yield exactly one honest signal —
*N files written in the last ~T seconds = currently active*. Anything claiming "stuck / hung /
frozen" needs **orchestrator state** (which units are *expected* to be running) that a file
listing does not contain.

So the first design question is not "how do I detect a stall" but "where does the expected-set
come from". On this estate it already exists, and it is not the filesystem.

## 2. Signal inventory (measured, not assumed)

| # | Signal | Source | What it can prove | What it CANNOT prove |
|---|--------|--------|-------------------|----------------------|
| **S1** | Expected set | `~/.claude/bg-registry/<sid>.ndjson` | which units the orchestrator believes are RUNNING | that they are alive |
| **S2** | Write activity | byte-**growth** of `~/.claude/projects/<proj>/<sid>/subagents/agent-<id>.jsonl` across ΔT | ALIVE (growth > 0) | anything, when growth == 0 |
| **S3** | Process liveness | CPU-time **delta** for the registry record's `pid` across the same ΔT | ALIVE, or dead-pid | anything for an in-process Task subagent (no distinct pid) |
| **S4** | Artifact landing | `expected_artifact` exists and is non-empty | the unit **FINISHED** | that it finished *well* |

S1 is verified live, not inferred: `hooks/bg-registry/register.py` is wired at
`_dispatch/manifest.json` `PreToolUse.checks[0]` (matcher `Task`), `done_marker` at
`Stop.checks[0]`, `reconcile` at `SessionStart.checks[0]`; `~/.claude/bg-registry/` currently
holds live NDJSON including `lane6audit.ndjson` written **during this program**. Record shape
(`register.py:20-23`): `{id, kind, cmd, subagent_type?, name?, desc?, pid, expected_artifact,
declared_scope, started_ts, status, sync, session}`, with `done_marker.py` appending
`{id, status:"done", done_ts, reason}`.

**S2 is byte-GROWTH, never mtime.** Two samples separated by ΔT (default 60 s). This is the same
correction that resolved "agents are stuck / 0 KB" — a stale cached size snapshot said dead; CPU
delta over 20 s **and** err-log byte-growth (86–142 KB, climbing) said alive.

## 3. The verdict table (AND-gate, ≥2 mechanically independent signals)

`single-signal-verification` §4: `FAILED`/`STALLED` only on an AND-gate of ≥2 signals — never
single-signal, never CPU-alone, never mtime-alone.

| S1 running? | S2 growth | S4 artifact | S3 | **Typed verdict** | Meaning |
|---|---|---|---|---|---|
| yes | > 0 | – | – | `CLEAN` | working |
| yes | 0 for ≥ T_idle | **present** | – | `DEGRADED` | **DONE-NOT-RECORDED** — the unit finished and `done_marker` missed it. Registry drift, *not* a stall. |
| yes | 0 for ≥ T_idle | absent | pid dead | `FINDING` | **DIED** — process gone, no artifact. Unrecoverable work. |
| yes | 0 for ≥ T_idle | absent | pid alive, 0 CPU Δ | `FINDING` | **SUSPECT-IDLE** — the 388-minute shape. |
| yes | 0 for ≥ T_idle | absent | NOT-CHECKED (in-process subagent) | `FINDING` (lower confidence, stated) | suspect; S3 unavailable is disclosed, not silently treated as alive |
| yes | – | – | – | `NOT-CHECKED` | registry or transcript unreadable — surfaced, never folded into CLEAN |
| no | – | – | – | `CLEAN` | nothing expected to be running |

The **DONE-NOT-RECORDED** row is the whole point. It is the row an mtime detector cannot express,
and it is the row that produced the 11-hour false positive. A detector that lacks it is the mtime
detector with extra steps.

`T_idle` default **25 min** — from the measured orchestration lesson ("one hung agent deadlocks
the phase; detect: write-freeze >25min"), against an observed worst case of **388 min**. Env
`WATCHDOG_IDLE_SEC`.

## 4. Traps this design structurally avoids

* **Self-match.** A process probe whose pattern appears in its OWN command line reported a dead
  session ACTIVE, twice; the tell was `CreationDate == the probe's own run time`. This design
  resolves pids from the **registry record**, never by pattern-matching a command line, so the
  class cannot occur. If a pattern scan is ever added it MUST exclude self by pid and assert
  `CreationDate < probe start`.
* **A readable file is not a live feed** (monitorcore). S2 is a *delta between two reads*, never a
  single read; a file that exists and is readable contributes nothing on its own.
* **`grep -c pat || echo 0`** prints `0` **and** exits 1, so the `||` also fires and yields
  `"0\n0"`. Any counting in the implementation must be done in Python, not shell.
* **A self-contradicting output is a detector failure, not a finding.** If one pass reports both
  "N units running" and "no registry entries", the instrument is broken — stop and fix it before
  reading either number.

## 5. Where it runs (and where it must NOT)

**MUST NOT: the `Stop` event.** Measured 2026-08-08: nine Stop checks already total **63.7 s**
against a **35 s** `events.Stop.settings_timeout` host wall, and the four slowest are exactly the
four that report DISARMED. Adding a ΔT-sampling detector — which by construction must *wait* —
to that clock would make it worse and would itself be killed.

**Recommended surface**, in order:
1. **The `mon` / monitorcore cockpit** as a read-only widget. It is already the operator's live
   view, it is off the hook clock, and ΔT sampling is natural in a poller.
2. **A one-shot at `SessionStart`**, folded into the existing `bg-registry/reconcile` check that
   already reads this registry. Cheap (one pass, no ΔT — so it can only emit `DIED` /
   `DONE-NOT-RECORDED` / `NOT-CHECKED`, never `SUSPECT-IDLE`), and it must SAY that its
   `SUSPECT-IDLE` coverage is `NOT-CHECKED` rather than implying none was found.
3. Never a `PreToolUse` or `Stop` check.

## 6. Why there is NO auto-restart, and the precondition that would change that

An automatic restart is **rejected**, on three independent grounds:

1. **The DONE-NOT-RECORDED row would restart finished work.** That row exists precisely because
   the two states look identical from the outside for long stretches.
2. **A false restart of a file-mutating unit is a data-loss event.** Parallel agents share one
   filesystem and one git index; a duplicate writer on the same scope is the measured
   contamination mode (`git add -A` sweeping siblings). Two live writers on one lane scope is
   strictly worse than one silent one.
3. **No unit declares idempotency.** `register.py`'s record has `declared_scope` but no
   "safe to re-run" field, so a restarter would be guessing.

**Precondition for revisiting:** a per-unit `idempotent: true|false` declaration written at
registration time, plus a lease so a restart cannot overlap the original. Until that exists, the
correct behaviour is to **surface and let a human or the orchestrator decide** — the same
inject-never-block posture as every other advisory gate here (AGENTS.md §6).

## 7. Falsification plan (what would prove this design wrong)

Both-states, or it does not count. Before any implementation is trusted:

1. Construct a **KNOWN-HUNG** unit (a registered unit whose process sleeps forever with no writes
   and no artifact). The detector MUST emit `FINDING / SUSPECT-IDLE`.
2. Construct a **KNOWN-FINISHED-BUT-UNMARKED** unit (artifact landed, no `done` record, process
   exited). The detector MUST emit `DEGRADED / DONE-NOT-RECORDED` — **a different verdict**.
3. Construct a **KNOWN-BUSY** unit (writing continuously). MUST emit `CLEAN`.
4. Delete the registry. MUST emit `NOT-CHECKED`, never `CLEAN`.

If (1) and (2) return the same verdict, the design has failed and must not ship: separating those
two is the entire justification for building anything beyond the honest `ag:N` active count.

## 8. Honest limits of this design (UNVERIFIED, inline)

* ~~UNVERIFIED~~ **SETTLED 2026-08-08 — CONFIRMED.** S2 works. `probe_s2_growth.py` (shipped in
  this directory) took two size samples 25 s apart over all 53 `agent-*.jsonl` in the newest
  `subagents/` dir: **2 of 53 grew** (+20,860 B and +18,773 B); the other 51 were flat. The host
  does **not** buffer until completion, so byte-growth is a usable liveness signal for in-process
  Task subagents. The 2-of-53 split is also the probe's own control: a detector that reported
  0/53 or 53/53 would be broken, and this one discriminates. Re-run it after any CLI upgrade —
  this is exactly the kind of host behaviour that changes silently under you.
* **UNVERIFIED**: that a Task-dispatched subagent has no separately-addressable OS pid. The
  registry's CLI mode takes `--pid`, but hook mode does not appear to set a distinct one.
  *Settling experiment*: read a hook-mode record and check whether `pid` is the host's pid.
  If S3 is genuinely unavailable for the common case, say so in the widget rather than degrading
  quietly.
* **Not covered**: a unit that is alive, writing, and *productively wrong*. No liveness signal can
  see that; it is a review problem, not a watchdog problem.
