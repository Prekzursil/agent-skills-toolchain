---
name: cost-tracking
description: Track and report Claude Code token usage, spending, and budgets from a local cost-tracking database. Use when the user asks about costs, spending, usage, tokens, budgets, or cost breakdowns by project, tool, session, or date.
origin: community
---

# Cost Tracking

Use this skill to analyze Claude Code cost and usage history from a local SQLite
database. It is intended for users who already have a cost-tracking hook or
plugin writing usage rows to `~/.claude-cost-tracker/usage.db`.

Source: salvaged from stale community PR #1304 by `MayurBhavsar`.

## When to Use

- The user asks "how much have I spent?", "what did this session cost?", or
  "what is my token usage?"
- The user mentions budgets, spending limits, overruns, or cost controls.
- The user wants a cost breakdown by project, tool, session, model, or date.
- The user wants to compare today against yesterday or inspect a recent trend.
- The user asks for a CSV export of recent usage records.

## How It Works

First verify prerequisites:

```bash
command -v sqlite3 >/dev/null && echo "sqlite3 available" || echo "sqlite3 missing"
test -f ~/.claude-cost-tracker/usage.db && echo "Database found" || echo "Database not found"
```

If the database is missing, do not fabricate usage data. Tell the user that cost
tracking is not configured and suggest installing or enabling a trusted local
cost-tracking hook/plugin.

The expected `usage` table usually contains one row per tool call or model
interaction. Column names vary by tracker, but the examples below assume:

| Column | Meaning |
| --- | --- |
| `timestamp` | ISO timestamp for the usage event |
| `project` | Project or repository name |
| `tool_name` | Tool or event name |
| `input_tokens` | Input token count, when recorded |

### Examples
### Quick Summary
### Cost By Project
### Cost By Tool
### Last Seven Days
### Session Drilldown
### Reporting Guidance
### Anti-Patterns
### Related
