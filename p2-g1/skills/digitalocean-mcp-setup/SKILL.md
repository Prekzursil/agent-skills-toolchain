---
name: digitalocean-mcp-setup
description: Use when installing, validating, or troubleshooting the archived DigitalOcean MCP server for Codex, Claude, or Gemini, especially when App Platform tools or env-only token wiring need to be set up safely.
---

# DigitalOcean MCP Setup

## Overview

Use this skill to install and validate the archived `@digitalocean/mcp` server for the local Codex, Claude, and Gemini clients without hardcoding a DigitalOcean token into configs.

## Use This Skill For

- Adding the archived DigitalOcean MCP server to Codex, Claude, or Gemini
- Fixing a broken `digitalocean` MCP registration
- Checking whether `DIGITALOCEAN_API_TOKEN` is wired safely through the environment
- Verifying that the App Platform-only tool surface is configured before use

## Workflow

1. Read `tools/mcp/digitalocean-mcp/README.md`.
2. Run `tools/mcp/digitalocean-mcp/scripts/install-digitalocean-mcp.ps1`.
3. Run `tools/mcp/digitalocean-mcp/scripts/validate-digitalocean-mcp.ps1`.
4. Confirm the `digitalocean` server is visible in Codex, Claude, and Gemini.
5. If `DIGITALOCEAN_API_TOKEN` is missing, report the setup as env-gated instead of pretending it is fully live.

## Guardrails

- Treat the archived upstream repo as intentional user-directed input; do not silently migrate this workflow to the maintained successor.
- Keep `DIGITALOCEAN_API_TOKEN` out of repo files, config snapshots, and validation notes.
- Default to the minimal `apps` service set unless the user explicitly asks for more DigitalOcean services.
- If a client shows the server as disconnected and the token is absent, report that as an env-gated state rather than a broken install.
