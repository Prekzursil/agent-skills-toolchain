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

Run the **context-budget** skill (`skills/context-budget/SKILL.md`) with the following inputs:

1. Pass `--verbose` flag if present in `$ARGUMENTS`
2. Resolve the context window BEFORE computing any percentage — never assume one. Take the
   first that is available: (a) a capacity the user supplied in `$ARGUMENTS`; (b)
   `autoCompactWindow` in the active `settings.json`; (c) the active model's advertised
   window — a `[1m]` model suffix means 1,000,000 tokens, not 200,000. Only if all three
   are unavailable, fall back to 200,000 **and state that fallback in the report**. A 200K
   denominator applied to a 1M session overstates pressure 5x (100,000 tokens of overhead
   reads as 50.0% instead of 10.0%) and manufactures removal recommendations
3. Follow the skill's four phases: Inventory → Classify → Detect Issues → Report
4. Output the formatted Context Budget Report to the user

The skill handles all scanning logic, token estimation, issue detection, and report formatting.
