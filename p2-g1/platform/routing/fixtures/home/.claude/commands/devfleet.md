---
description: Orchestrate parallel Claude Code agents via Claude DevFleet — plan projects from natural language, dispatch agents in isolated worktrees, monitor progress, and read structured reports.
---

# DevFleet — Multi-Agent Orchestration

Orchestrate parallel Claude Code agents via Claude DevFleet. Each agent runs in an isolated git worktree with full tooling.

Requires the DevFleet MCP server: `claude mcp add devfleet --transport http http://localhost:18801/mcp`

## Flow

```
User describes project
  → plan_project(prompt) → mission DAG with dependencies
  → Show plan, get approval
  → dispatch_mission(M1) → Agent spawns in worktree
  → M1 completes → auto-merge → M2 auto-dispatches (depends_on M1)
  → M2 completes → auto-merge
  → get_report(M2) → files_changed, what_done, errors, next_steps
  → Report summary to user
```

## Workflow

1. **Plan the project** from the user's description:

```
mcp__devfleet__plan_project(prompt="<user's description>")
```

This returns a project with chained missions. Show the user:
- Project name and ID
- Each mission: title, type, dependencies
- The dependency DAG (which missions block which)
