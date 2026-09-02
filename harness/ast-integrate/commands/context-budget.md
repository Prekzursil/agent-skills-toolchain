---
description: Analyze context window usage across agents, skills, MCP servers, and rules to find optimization opportunities. Helps reduce token overhead and avoid performance warnings.
---

# Context Budget Optimizer

Analyze your Claude Code setup's context window consumption and produce actionable recommendations to reduce token overhead.

## Usage

```
/context-budget [--verbose]
```

- Default: summary with top recommendations
- `--verbose`: full breakdown per component

$ARGUMENTS

## What to Do

This command is self-contained — run the four phases below directly. There is no separate
`context-budget` skill to delegate to; an earlier revision of this file pointed at
`skills/context-budget/SKILL.md`, which has never existed in any skill root.

### Phase 0 — Resolve the context window FIRST

Resolve the window BEFORE computing any percentage — never assume one. Take the first that is
available: (a) a capacity the user supplied in `$ARGUMENTS`; (b) `autoCompactWindow` in the
active `settings.json`; (c) the active model's advertised window — a `[1m]` model suffix means
1,000,000 tokens, not 200,000. Only if all three are unavailable, fall back to 200,000 **and
state that fallback in the report**. A 200K denominator applied to a 1M session overstates
pressure 5x (100,000 tokens of overhead reads as 50.0% instead of 10.0%) and manufactures
removal recommendations.

### Phase 1 — Inventory

Enumerate what the session actually loads, per surface. Do not estimate a surface you did not
read; report it as `NOT-CHECKED` instead.

- **Skills** — every `SKILL.md` under the active skill roots. Only the frontmatter `name` and
  `description` are session-start tax; the body is read on demand. Charging whole bodies
  overstates the skill surface by orders of magnitude. `ci/check_skill_context_budget.py`
  is the in-repo reference implementation of this split and of the 8,000-char trigger ceiling.
- **Rules** — files with no `paths:` frontmatter load at turn 0; files WITH `paths:` load
  lazily on a matching touch. Charge only the always-on set as fixed cost.
- **MCP servers** — each connected server's tool schemas. Count tools and sum their
  name + description + input schema, not the server's whole capability list.
- **Agents / commands** — frontmatter `description` only, same as skills.

### Phase 2 — Classify

Split each inventoried item into **fixed** (paid every turn) and **on-demand** (paid only when
invoked). Report the two totals separately; a single blended number hides the only figure that
can be acted on.

### Phase 3 — Detect issues

Flag, with the measured number beside each: surfaces over their declared ceiling; duplicate or
near-duplicate descriptions; always-on rules that could be `paths:`-scoped; MCP servers whose
tools are never called; and any surface whose measurement failed (report the failure, never a
zero). A zero you did not measure is a false clean.

### Phase 4 — Report

Output a Context Budget Report: the resolved window and how it was resolved, fixed vs on-demand
totals with percentages, the per-surface table, then the ranked recommendations. With
`--verbose`, add the full per-component breakdown. State every unmeasured surface explicitly.
