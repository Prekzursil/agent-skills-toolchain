---
name: "source-command-devfleet"
description: "Orchestrate parallel Codex agents via Codex DevFleet — plan projects from natural language, dispatch agents in isolated worktrees, monitor progress, and read structured reports."
---

# source-command-devfleet

Use this skill when the user asks to run the migrated source command `devfleet`.

## Command Template

# DevFleet — Multi-Agent Orchestration

Orchestrate parallel Codex agents via Codex DevFleet. Each agent runs in an isolated git worktree with full tooling.

Requires the DevFleet MCP server: `Codex mcp add devfleet --transport http http://localhost:18801/mcp`

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

2. **Wait for user approval** before dispatching. Show the plan clearly.

3. **Dispatch the first mission** (the one with empty `depends_on`):

```
mcp__devfleet__dispatch_mission(mission_id="<first_mission_id>")
```

The remaining missions auto-dispatch as their dependencies complete (because `plan_project` creates them with `auto_dispatch=true`). When manually creating missions with `create_mission`, you must explicitly set `auto_dispatch=true` for this behavior.

### All Available Tools
### Guidelines
