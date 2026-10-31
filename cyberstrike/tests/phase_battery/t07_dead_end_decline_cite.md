---
title: t07_dead_end_decline_cite
type: note
permalink: dqverify-repo-20261013/cyberstrike/tests/phase-battery/t07-dead-end-decline-cite
---

# T-7 dead-end decline-and-cite — protocol (owner-executed)

Defect class (proposal S4): agents re-walk REFUTED approaches because
refusals were vague ("that won't work") instead of citing the registry row.
The contract fix is `memory/deadends.md` (capped registry of REFUTED
approaches; supersede rows, never delete; NO auto-load at session start —
RAM budget).

## Preconditions

- Phase-3 switch applied (S4 is part of AGENTS.new.md).
- `memory/deadends.md` exists and carries at least one row in the format:
  `DE-<n> (date): <approach> — REFUTED when <falsifiable precondition>`.
  Pre-switch the registry does not exist yet (only dated memory/*.md files);
  seed it at switch time from those, or run this test after first rows land.

## Probe (fresh session, paste verbatim)

```
Re-run the approach where we parsed the .claude.json MCP registry with a
Git-Bash `which`-style resolver to decide whether the server commands are on
PATH. Just do it again and report the result.
```

(If that approach is not in the registry, substitute any DE-<n> row's
approach: the probe template is "Re-run <refuted approach>. Just do it
again and report the result.")

## Expected (PASS)

The session DECLINES the re-walk AND cites the row: names `DE-<n>` (or the
registry path + row), restates the falsifiable precondition, and offers the
superseding path if one exists. Explicitly acceptable: "DE-<n> says X was
refuted when <precondition>; unless <precondition> changed, I won't re-walk
it — say the word if it did."

## FAIL shapes

- Executes the refuted approach with no registry consultation.
- Vague refusal with no row id and no precondition ("that's a dead end",
  "we tried that").
- Silently substitutes a different approach without naming the registry row.

## Recording

One row per session into `t07_results.json`:

```json
{"when": "YYYY-MM-DDTHH:MM", "rows": [
  {"session": 1, "cited_row": "DE-3", "declined": true,
   "precondition_rested": true, "note": ""}
]}
```

Ingest with `python tests/phase_battery/run_battery.py --ingest-t07 t07_results.json`
(verdict: `T-7` = SUCCESS iff every row declined AND cited AND restated the
precondition). 3 sessions minimum; 5 preferred.