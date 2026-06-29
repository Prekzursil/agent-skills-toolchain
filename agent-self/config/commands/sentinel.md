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

## Steps

Invoke the `intent-drift-sentinel` agent with the current task description (and any `*` bypass prefix) as its input. Pass the current working directory so it can locate the correct ledger partition.

The sentinel will:
1. Assess whether clarifying questions are warranted (EVPI-gated).
2. Read `~/.claude/event-ledger/<slug>/state.json` and recent `events.jsonl` for the current project.
3. Optionally query basic-memory if the ledger goal field is empty.
4. Return a structured verdict (ASK-GATE + DRIFT-GATE + open failures).

The parent session should read the verdict and either answer the questions (if asked), realign to the stated goal, or continue if the verdict is ON-TRACK / CLEAR.
