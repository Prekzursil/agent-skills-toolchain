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
| `output_tokens` | Output token count, when recorded |
| `cost_usd` | Precomputed cost in USD |
| `session_id` | Claude Code session identifier |
| `model` | Model used for the event |

Prefer `cost_usd` over hand-calculating pricing. Model prices and cache pricing
change over time, and the tracker should be the source of truth for how each row
was priced.

## Examples

### Quick Summary

```bash
sqlite3 ~/.claude-cost-tracker/usage.db "
  SELECT
    'Today: $' || ROUND(COALESCE(SUM(CASE WHEN date(timestamp) = date('now') THEN cost_usd END), 0), 4) ||
    ' | Total: $' || ROUND(COALESCE(SUM(cost_usd), 0), 4) ||
    ' | Calls: ' || COUNT(*) ||
    ' | Sessions: ' || COUNT(DISTINCT session_id)
  FROM usage;
"
```

### Cost By Project

```bash
sqlite3 -header -column ~/.claude-cost-tracker/usage.db "
  SELECT project, ROUND(SUM(cost_usd), 4) AS cost, COUNT(*) AS calls
  FROM usage
  GROUP BY project
  ORDER BY cost DESC;
"
```

### Cost By Tool

```bash
sqlite3 -header -column ~/.claude-cost-tracker/usage.db "
  SELECT tool_name, ROUND(SUM(cost_usd), 4) AS cost, COUNT(*) AS calls
  FROM usage
  GROUP BY tool_name
  ORDER BY cost DESC;
"
```

### Last Seven Days

```bash
sqlite3 -header -column ~/.claude-cost-tracker/usage.db "
  SELECT date(timestamp) AS date, ROUND(SUM(cost_usd), 4) AS cost, COUNT(*) AS calls
  FROM usage
  GROUP BY date(timestamp)
  ORDER BY date DESC
  LIMIT 7;
"
```

### Session Drilldown

```bash
sqlite3 -header -column ~/.claude-cost-tracker/usage.db "
  SELECT session_id,
    MIN(timestamp) AS started,
    MAX(timestamp) AS ended,
    ROUND(SUM(cost_usd), 4) AS cost,
    COUNT(*) AS calls
  FROM usage
  GROUP BY session_id
  ORDER BY started DESC
  LIMIT 10;
"
```

## Reporting Guidance

When presenting cost data, include:

1. Today's spend and yesterday comparison.
2. Total spend across the tracked database.
3. Top projects ranked by cost.
4. Top tools ranked by cost.
5. Session count and average cost per session when enough data exists.

For small amounts, format currency with four decimal places. For larger amounts,
two decimals are enough.

## Anti-Patterns

- Do not estimate costs from raw token counts when `cost_usd` is present.
- Do not assume the database exists without checking.
- Do not run unbounded `SELECT *` exports on large databases.
- Do not hard-code current model pricing in user-facing answers.
- Do not recommend installing unreviewed hooks or plugins that execute arbitrary
  code.

## OpenRouter generation ids (sidecar)

Claude SQLite rows in `~/.claude-cost-tracker/usage.db` do **not** include OpenRouter sidecar calls. Label the source when mixing numbers.

OpenRouter chat completions return a generation `id`. After the call, `GET https://openrouter.ai/api/v1/generation?id=<generation_id>` (same env credential, never log it) returns `total_cost`, token counts, model, and provider. Cost may lag a second or two; retry a few times on 404.

Probe (prints generation id + usage, never the secret):

```powershell
C:\Python314\python.exe C:\Users\Prekzursil\.agents\scripts\openrouter-complete.py --show-limits --prompt "Reply with the single word: pong"
```

Do not hard-code OpenRouter unit prices in answers; prefer the generation endpoint's `total_cost`. Per-key remaining cap is `GET /api/v1/key` → `limit_remaining` (see skill `openrouter-routing`).

Free-path Wave 0 smoke (2026-08-27): `liquid/lfm-2.5-2.6b:free` id `gen-1787793797-2WelxSMIM1z6ZjFYfWFv` and `openrouter/free` → `nvidia/nemotron-3.5-lightning:free` id `gen-1787793804-F2TQPdT2frdTAk6BC3FR` both settled at `total_cost=0` after an initial `GET /generation` 404 lag. Paid `deepseek/deepseek-v4-flash-0731` remains 402 until credits are added.

## Related

- `/cost-report` - Command-form report using the same database.
- `cost-aware-llm-pipeline` - Model-routing and budget-design patterns.
- `token-budget-advisor` - Context and token-budget planning.
- `strategic-compact` - Context compaction to reduce repeated token spend.
- `openrouter-routing` - T0/T1/T2 sidecar, spend-cap checklist, generation-id probe.
