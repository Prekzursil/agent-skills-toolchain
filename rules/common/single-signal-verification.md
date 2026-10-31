---
permalink: dqverify-repo-20261013/rules/common/single-signal-verification
---

# Single-Signal Verification (two independent signals before a load-bearing claim)

**A single tool's silence or single reading is NOT evidence.** Before asserting something is
*absent*, *broken*, *stuck*, or *done* — especially when the next action is disruptive (a
restart, a kill, a re-fix, a rollback) — corroborate with a SECOND, mechanically-independent
probe. If the two disagree, the first was likely a measurement artifact.

This is the most expensive recurring failure mode on this estate: **six** wrong conclusions in
one session (2026-07-18), **seven** more in another (2026-08-07/08), and in none of the latter
was the detector at fault — the correct answer was already on screen and simply unread.

**Full catalogue of ~20 measured misreads, each with the artifact and the probe that corrected
it:** `~/.agents/knowledge/rule-evidence/single-signal-verification-full.md`. Read it when you
want the precedent for a specific shape.

## The rule

1. **Both absence AND success need corroboration.** "Nothing there", "it crashed", "it's done"
   are claims, not observations, until a second independent probe agrees.
2. **The two signals must be mechanically independent** — a different shell, a different data
   field, a different measurement (process CPU vs file mtime vs byte-count). Re-running the same
   probe is not a second signal.
3. **Verify the detector before trusting an absence.** A "0 results / not found / 0 alive"
   reading is often a broken matcher, wrong shell, wrong path, or stale cache. Confirm the
   detector *can* find a known-present item first.
   - **3b. The both-states test.** Before a probe's silence counts as "fixed", run it against the
     known-BROKEN state and confirm it FIRES there. A probe silent in both states measures
     nothing. Applied to a test suite this is **mutation testing**: revert each real bug and
     require the suite to go red. A suite that stays green is not protecting that behaviour.
   - **3c. A control that cannot distinguish the two hypotheses is not a control.** It only
     proves the instrument ran — and it is more seductive than 3b because it PASSES and you
     record it as diligence. *Test:* state both hypotheses first, then ask what the control's
     PASS looks like under each. If identical, the control is inert. *Cheapest fix:* make the
     control a COUNT of the thing you are comparing and fail closed at zero. *Tell:* a
     suspiciously round, suspiciously equal number on both sides is usually a collection-level
     mistake, not genuine parity. **When your probe and someone else's disagree, suspect YOURS
     first.**
4. **Terminal-state discipline** (AGENTS §4): `DONE` only on receipt AND postcondition;
   `FAILED`/`STALLED` only on an AND-gate of ≥2 signals — never CPU-alone, never mtime-alone.
5. **A subagent's finding is a single signal too.** N subagents asserting the same thing is still
   one lens if they read the same stale input. Verify load-bearing subagent claims against the
   real config/code before acting.
6. **Declare the SOURCE probe, not just the verifier — an undeclared source is zero signals, not
   one.** Independence is a property of a *pair*; with only the verifier recorded there is no
   pair. State what measurement PRODUCED the claim and what mechanically different measurement
   CHECKED it. Any gate mechanizing this must treat a missing/empty source as a VIOLATION, never
   as "differs from the verifier, so independent".

## Read your own instrument

The dominant failure is **recall, not detection**. Before declaring a thing absent, broken, novel
or unbuilt: run recall (`basic-memory`), **read the gate output you just produced** instead of
skimming it, and `grep` the tree for the thing you are about to call missing. A green gate you
did not read is a signal you did not take. **When a claim and an instrument you are already
running disagree, the instrument wins.**

## Detector shapes that look like findings

| shape | wrong reading | why |
|---|---|---|
| `grep -c pat \|\| echo 0` | "all 7 hit" AND "empty intersection" in one run | `grep -c` prints `0` *and* exits 1, so `\|\| echo 0` also fires → `"0\n0"` |
| a process probe whose pattern is in its OWN command line | a dead session reported ACTIVE, twice | `Win32_Process` matched the probe. Tell: reported `CreationDate` == the probe's own run time |
| comparing two DIFFERENT files | "DRIFTED" | of course they differ — compare like with like |
| `pytest <standalone script>` | `INTERNALERROR> SystemExit: 0` read as a failing suite | the file calls `sys.exit()` at module level; run it via its own entry point |

**A self-contradicting output is a detector failure, not a finding.** If one run reports two
things that cannot both be true, fix the instrument before reading either number.

**Corollary — equality to a pinned SHA is a self-falsifying safety check.** It raised three false
alarms while a human legitimately committed. Use invariants that survive concurrent work: the
baseline commit remains an ANCESTOR of HEAD, every intervening commit is OWNER-authored, no
changed path carries a unit name from your program, and no agent wrote to that tree. (Author
identity is forgeable — corroborate with the changed-path surface.)

## When it bites hardest

Long autonomous loops, fan-out monitoring, RE offset work, "is it done yet" polling, and any
moment the *fix* is disruptive. A second probe costs seconds; acting on a false signal costs a
wasted restart, a killed sibling, or a wrong "done". **Auditors are not exempt** — an audit agent
once reproduced the exact failure it was documenting. Two same-level reports that disagree are a
resolve-from-raw-source trigger, never a pick-one trigger.

Pairs with `fresh-context-verify` and the two-strikes pivot (AGENTS §4b).