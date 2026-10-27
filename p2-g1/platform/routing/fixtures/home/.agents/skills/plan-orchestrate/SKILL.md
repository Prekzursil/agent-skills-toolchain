---
name: plan-orchestrate
description: "Use when converting a multi-step plan into dependency-aware agent chains and ready-to-run orchestration prompts without executing the plan."
origin: ECC
---

# Plan Orchestrate

Bridge a plan document to `/orchestrate custom` by emitting one ready-to-paste invocation per step. The skill is generative only — it never executes `/orchestrate`. The user pastes each line when ready.

## When to Activate

- User has a multi-step plan document (PRD, RFC, implementation plan) and wants to drive it through `/orchestrate`.
- User says "orchestrate this plan", "give me orchestrate prompts for each step", "compose chains for this plan".
- A step-by-step plan exists but the user does not want to manually pick agents per step.

Skip when:
- The work is one ad-hoc step → call `/orchestrate custom` directly.
- The plan is unreadable or empty. Lack of explicit numbering alone is not a skip condition — see the "No clear steps" edge case below.

## Inputs

```
<plan-doc-path> [--lang=python|typescript|go|rust|cpp|java|kotlin|flutter|auto] [--scope=all|step:<n>|range:<a>-<b>] [--dry-run]
```

- `<plan-doc-path>` — required; relative or absolute path (`@docs/...` accepted).
- `--lang` — reviewer language variant; defaults to `auto` (detected from project).
- `--scope` — limits emitted steps; defaults to `all`.
- `--dry-run` — print decomposition + chain rationale only; do not emit final prompts.

## Authoritative `/orchestrate` shape (do not deviate)

```
{ORCH_CMD} custom "<agent1>,<agent2>,...,<agentN>" "<task description>"
```

Where `{ORCH_CMD}` is determined in Phase 0 (see below). The command string in the emitted output **always uses one concrete form** — never both, never a placeholder.

### ECC install form and namespacing
### Available agent catalogue (must pick from these)
### How It Works
### Phase 0 — Detect ECC mode + language
### Phase 1 — Decompose steps
### Phase 2 — Tag and pick chain
### Phase 3 — Compress task description
### Phase 4 — Output
### Plan-Orchestrate Result
### Steps overview
