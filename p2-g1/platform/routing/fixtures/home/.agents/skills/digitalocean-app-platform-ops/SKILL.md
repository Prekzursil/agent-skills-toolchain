---
name: digitalocean-app-platform-ops
description: Use when operating DigitalOcean App Platform through the archived DigitalOcean MCP server, especially for listing apps, deployments, logs, restarts, deletes, or spec validation.
---

# DigitalOcean App Platform Ops

## Overview

Use this skill to operate the archived `@digitalocean/mcp` App Platform surface once the MCP server is already installed and token-wired.

## Use This Skill For

- Listing App Platform apps and deployments
- Reading deployment state and logs
- Restarting apps or canceling deployments
- Validating an app spec before creation or update
- Reviewing whether an App Platform action is safe before execution

## Quick Reference

| Intent | MCP tool family |
| --- | --- |
| List or inspect apps | `list_apps`, `get_app` |
| Create or update an app | `create_app`, `update_app`, `validate_app_spec` |
| Deployments and rollbacks | `list_deployments`, `create_deployment`, `cancel_deployment`, rollback tools |
| Logs and metrics | log retrieval + bandwidth metrics |

## Workflow

1. Confirm the `digitalocean` MCP server is already configured. If not, switch to `$digitalocean-mcp-setup`.
2. Prefer read-only inspection first (`list_apps`, `get_app`, deployments, logs) before proposing a mutating action.
3. For create or update flows, validate the app spec before applying it.
4. For deletes, restarts, rollbacks, or cancelation, call out the destructive scope before executing.

## Guardrails

- This skill is for the archived App Platform MCP surface only; do not assume the broader resource coverage of the maintained successor repo.
- Keep the service set minimal and App Platform-focused unless the user explicitly expands scope.
- If the token is missing or the server is disconnected, stop and route back to `$digitalocean-mcp-setup`.
