---
name: linear
description: Manage issues, projects & team workflows in Linear. Use when the user wants to read, create or updates tickets in Linear.
metadata:
  short-description: Manage Linear issues in Codex
---

# Linear

## Overview

This skill provides a structured workflow for managing issues, projects & team workflows in Linear. It ensures consistent integration with the Linear MCP server, which offers natural-language project management for issues, projects, documentation, and team collaboration.

## Prerequisites
- Linear MCP server must be connected and accessible via OAuth
- Confirm access to the relevant Linear workspace, teams, and projects

## Required Workflow

**Follow these steps in order. Do not skip steps.**

### Step 0: Set up Linear MCP (if not already configured)

If any MCP call fails because Linear MCP is not connected, pause and set it up:

1. Add the Linear MCP:
   - `codex mcp add linear --url https://mcp.linear.app/mcp`
2. Enable remote MCP client:
   - Set `[features] rmcp_client = true` in `config.toml` **or** run `codex --enable rmcp_client`
3. Log in with OAuth:
   - `codex mcp login linear`

After successful login, the user will have to restart codex. You should finish your answer and tell them so when they try again they can continue with Step 1.

**Windows/WSL note:** If you see connection errors on Windows, try configuring the Linear MCP to run via WSL:
```json
{"mcpServers": {"linear": {"command": "wsl", "args": ["npx", "-y", "mcp-remote", "https://mcp.linear.app/sse", "--transport", "sse-only"]}}}
```

### Step 1
Clarify the user's goal and scope (e.g., issue triage, sprint planning, documentation audit, workload balance). Confirm team/project, priority, labels, cycle, and due dates as needed.

### Step 2
### Step 3
### Step 4
### Available Tools
### Practical Workflows
### Tips for Maximum Productivity
### Troubleshooting
