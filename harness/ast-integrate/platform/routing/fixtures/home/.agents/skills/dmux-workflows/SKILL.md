---
name: dmux-workflows
description: Multi-agent orchestration using dmux (tmux pane manager for AI agents). Patterns for parallel agent workflows across Claude Code, Codex, OpenCode, and other harnesses. Use when running multiple agent sessions in parallel or coordinating multi-agent development workflows.
origin: ECC
---

# dmux Workflows

Orchestrate parallel AI agent sessions using dmux, a tmux pane manager for agent harnesses.

## When to Activate

- Running multiple agent sessions in parallel
- Coordinating work across Claude Code, Codex, and other harnesses
- Complex tasks that benefit from divide-and-conquer parallelism
- User says "run in parallel", "split this work", "use dmux", or "multi-agent"

## What is dmux

dmux is a tmux-based orchestration tool that manages AI agent panes:
- Press `n` to create a new pane with a prompt
- Press `m` to merge pane output back to the main session
- Supports: Claude Code, Codex, OpenCode, Cline, Gemini, Qwen

**Install:** `npm install -g dmux` or see [github.com/standardagents/dmux](https://github.com/standardagents/dmux)

## Quick Start

```bash
# Start dmux session
dmux

# Create agent panes (press 'n' in dmux, then type prompt)
# Pane 1: "Implement the auth middleware in src/auth/"
# Pane 2: "Write tests for the user service"
# Pane 3: "Update API documentation"

# Each pane runs its own agent session
# Press 'm' to merge results back
```

## Workflow Patterns

### Pattern 1: Research + Implement

Split research and implementation into parallel tracks:

```
Pane 1 (Research): "Research best practices for rate limiting in Node.js.
  Check current libraries, compare approaches, and write findings to
  /tmp/rate-limit-research.md"

Pane 2 (Implement): "Implement rate limiting middleware for our Express API.
  Start with a basic token bucket, we'll refine after research completes."

### After Pane 1 completes, merge findings into Pane 2's context
