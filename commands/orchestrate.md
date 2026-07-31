---
description: Sequential and tmux/worktree orchestration guidance for multi-agent workflows.
---

# Orchestrate Command

Sequential agent workflow for complex tasks.

## Usage

`/orchestrate [workflow-type] [task-description]`

## Workflow Types

### feature
Full feature implementation workflow:
```
planner -> tdd-guide -> code-reviewer -> security-reviewer
```

### bugfix
Bug investigation and fix workflow:
```
planner -> tdd-guide -> code-reviewer
```

### refactor
Safe refactoring workflow:
```
architect -> code-reviewer -> tdd-guide
```

### security
Security-focused review:
```
security-reviewer -> code-reviewer -> architect
```

## Execution Pattern

For each agent in the workflow:

1. **Invoke agent** with context from previous agent
2. **Collect output** as structured handoff document
3. **Pass to next agent** in chain
4. **Aggregate results** into the final report using the severity reconciliation
   rules below — "aggregate" is NOT "take the last reviewer's answer"

## Severity Reconciliation (MANDATORY — order-independent)

Two reviewers can rate the SAME defect differently. `code-reviewer` lists
"Exposed secrets in logs" under **Security (CRITICAL)**; `security-reviewer`'s
pattern table rates "Logging passwords/secrets" **MEDIUM**. Without a rule, a
change that logs an access token resolves to CRITICAL under `/orchestrate
security` and MEDIUM under `/orchestrate feature` — the same evidence, a
different disposition, decided purely by chain order. These rules remove that
degree of freedom. They are deterministic: apply them and every chain order
yields the same terminal recommendation.

**R1 — Highest severity wins.** For each distinct finding (same file, same
issue), the reconciled severity is the MAXIMUM any reviewer assigned on
`CRITICAL > HIGH > MEDIUM > LOW`. A later reviewer NEVER downgrades an earlier
one; "Final approval" in the chain descriptions means *last to run*, not
*authoritative*.

**R2 — Position confers no authority.** Reviewer order (sequential or parallel)
must not change the reconciled severity of any finding. If reordering the chain
would change the recommendation, R1 was not applied.

**R3 — Deterministic terminal mapping.** Derive the single required
recommendation from the reconciled set, never from prose:

| Highest reconciled severity present | RECOMMENDATION |
|---|---|
| CRITICAL | `BLOCKED` |
| HIGH | `NEEDS WORK` |
| MEDIUM or LOW only | `NEEDS WORK` if any reviewer withheld approval, else `SHIP` |
| No findings | `SHIP` |

**R4 — Disagreements are reported, not silently resolved.** When reviewers gave
different severities for one finding, the final report must list the finding
once at its reconciled severity and name each reviewer's original rating, so the
downgrade attempt stays visible.

**R5 — A missing or unparseable reviewer result is not an approval.** Treat it
as `NEEDS WORK` and say which reviewer did not report. Absence of a finding is
not evidence of absence.

Scope note: reconciliation is the ORCHESTRATOR's job. The
`hooks/subagent-lifecycle` Stop hook validates one subagent's output shape
against its own contract and is correctly blind to its siblings — it is not a
cross-reviewer arbiter and must not be extended into one.

## Handoff Document Format

Between agents, create handoff document:

```markdown
## HANDOFF: [previous-agent] -> [next-agent]

### Context
[Summary of what was done]

### Findings
[Key discoveries or decisions]

### Files Modified
[List of files touched]

### Open Questions
[Unresolved items for next agent]

### Recommendations
[Suggested next steps]
```

## Example: Feature Workflow

```
/orchestrate feature "Add user authentication"
```

Executes:

1. **Planner Agent**
   - Analyzes requirements
   - Creates implementation plan
   - Identifies dependencies
   - Output: `HANDOFF: planner -> tdd-guide`

2. **TDD Guide Agent**
   - Reads planner handoff
   - Writes tests first
   - Implements to pass tests
   - Output: `HANDOFF: tdd-guide -> code-reviewer`

3. **Code Reviewer Agent**
   - Reviews implementation
   - Checks for issues
   - Suggests improvements
   - Output: `HANDOFF: code-reviewer -> security-reviewer`

4. **Security Reviewer Agent**
   - Security audit
   - Vulnerability check
   - Final approval
   - Output: Final Report

## Final Report Format

```
ORCHESTRATION REPORT
====================
Workflow: feature
Task: Add user authentication
Agents: planner -> tdd-guide -> code-reviewer -> security-reviewer

SUMMARY
-------
[One paragraph summary]

AGENT OUTPUTS
-------------
Planner: [summary]
TDD Guide: [summary]
Code Reviewer: [summary]
Security Reviewer: [summary]

FILES CHANGED
-------------
[List all files modified]

TEST RESULTS
------------
[Test pass/fail summary]

SECURITY STATUS
---------------
[Security findings, each at its RECONCILED severity (R1).
 Where reviewers disagreed, name both original ratings (R4).]

RECOMMENDATION
--------------
[SHIP / NEEDS WORK / BLOCKED — derived from the R3 table, not from prose]
```

## Parallel Execution

For independent checks, run agents in parallel:

```markdown
### Parallel Phase
Run simultaneously:
- code-reviewer (quality)
- security-reviewer (security)
- architect (design)

### Merge Results
Combine outputs into a single report by applying the Severity Reconciliation
rules R1-R5. Parallel execution has no ordering at all, so an order-dependent
merge is not merely unstable here — it is undefined.
```

For external tmux-pane workers with separate git worktrees, use `node scripts/orchestrate-worktrees.js plan.json --execute`. The built-in orchestration pattern stays in-process; the helper is for long-running or cross-harness sessions.

When workers need to see dirty or untracked local files from the main checkout, add `seedPaths` to the plan file. ECC overlays only those selected paths into each worker worktree after `git worktree add`, which keeps the branch isolated while still exposing in-flight local scripts, plans, or docs.

```json
{
  "sessionName": "workflow-e2e",
  "seedPaths": [
    "scripts/orchestrate-worktrees.js",
    "scripts/lib/tmux-worktree-orchestrator.js",
    ".claude/plan/workflow-e2e-test.json"
  ],
  "workers": [
    { "name": "docs", "task": "Update orchestration docs." }
  ]
}
```

To export a control-plane snapshot for a live tmux/worktree session, run:

```bash
node scripts/orchestration-status.js .claude/plan/workflow-visual-proof.json
```

The snapshot includes session activity, tmux pane metadata, worker states, objectives, seeded overlays, and recent handoff summaries in JSON form.

## Operator Command-Center Handoff

When the workflow spans multiple sessions, worktrees, or tmux panes, append a control-plane block to the final handoff:

```markdown
CONTROL PLANE
-------------
Sessions:
- active session ID or alias
- branch + worktree path for each active worker
- tmux pane or detached session name when applicable

Diffs:
- git status summary
- git diff --stat for touched files
- merge/conflict risk notes

Approvals:
- pending user approvals
- blocked steps awaiting confirmation

Telemetry:
- last activity timestamp or idle signal
- estimated token or cost drift
- policy events raised by hooks or reviewers
```

This keeps planner, implementer, reviewer, and loop workers legible from the operator surface.

## Arguments

$ARGUMENTS:
- `feature <description>` - Full feature workflow
- `bugfix <description>` - Bug fix workflow
- `refactor <description>` - Refactoring workflow
- `security <description>` - Security review workflow
- `custom <agents> <description>` - Custom agent sequence

## Custom Workflow Example

```
/orchestrate custom "architect,tdd-guide,code-reviewer" "Redesign caching layer"
```

## Tips

1. **Start with planner** for complex features
2. **Always include code-reviewer** before merge
3. **Use security-reviewer** for auth/payment/PII
4. **Keep handoffs concise** - focus on what next agent needs
5. **Run verification** between agents if needed
