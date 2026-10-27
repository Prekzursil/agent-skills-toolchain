---
name: claude-devfleet
description: Orchestrate multi-agent coding tasks via Claude DevFleet — plan projects, dispatch parallel agents in isolated worktrees, monitor progress, and read structured reports.
origin: community
---

# Claude DevFleet Multi-Agent Orchestration

## When to Use

Use this skill when you need to dispatch multiple Claude Code agents to work on coding tasks in parallel. Each agent runs in an isolated git worktree with full tooling.

Requires a running Claude DevFleet instance connected via MCP:
```bash
claude mcp add devfleet --transport http http://localhost:18801/mcp
```

## How It Works

```
User → "Build a REST API with auth and tests"
  ↓
plan_project(prompt) → project_id + mission DAG
  ↓
Show plan to user → get approval
  ↓
dispatch_mission(M1) → Agent 1 spawns in worktree
  ↓
M1 completes → auto-merge → auto-dispatch M2 (depends_on M1)
  ↓
M2 completes → auto-merge
  ↓
get_report(M2) → files_changed, what_done, errors, next_steps
  ↓
Report back to user
```

### Tools

| Tool | Purpose |
|------|---------|
| `plan_project(prompt)` | AI breaks a description into a project with chained missions |
| `create_project(name, path?, description?)` | Create a project manually, returns `project_id` |
| `create_mission(project_id, title, prompt, depends_on?, auto_dispatch?)` | Add a mission. `depends_on` is a list of mission ID strings (e.g., `["abc-123"]`). Set `auto_dispatch=true` to auto-start when deps are met. |
| `dispatch_mission(mission_id, model?, max_turns?)` | Start an agent on a mission |
| `cancel_mission(mission_id)` | Stop a running agent |
| `wait_for_mission(mission_id, timeout_seconds?)` | Block until a mission completes (see note below) |
| `get_mission_status(mission_id)` | Check mission progress without blocking |

### Workflow: Plan → Dispatch → Monitor → Report
### Concurrency
### Examples
### Full auto: plan and launch
### Manual: step-by-step control
### Sequential with review
### Guidelines
