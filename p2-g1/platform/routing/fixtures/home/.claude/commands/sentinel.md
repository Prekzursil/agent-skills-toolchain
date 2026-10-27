# /sentinel — Intent/Drift Sentinel

Dispatch the `intent-drift-sentinel` agent on the current task to run two gates:

- **ASK-GATE**: surface 1-3 EVPI-gated clarifying questions if the task is underspecified (skipped if prompt starts with `*`).
- **DRIFT-GATE**: read the event-ledger goal + recent turns and report whether current work has drifted from the recorded goal.

Returns a compact structured verdict. Does not modify any files or block execution.

## Usage

```
/sentinel
/sentinel * check only drift, skip clarifying questions
```

Prefix `*` bypasses the ASK-GATE (drift check only).

## When to use

- Before starting any task that feels ambiguous or underspecified.
- Mid-task, when you suspect the work has wandered from the original goal.
- After a compaction/resume, as a lightweight sanity check before continuing.
- Anytime you want an isolated second opinion on intent without risking prompt injection in the main context.
