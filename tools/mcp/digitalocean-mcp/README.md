---
title: README
type: note
permalink: dqverify-repo-20261013/tools/mcp/digitalocean-mcp/readme
---

# DigitalOcean MCP

`tools/mcp/digitalocean-mcp/` is the repo-owned Windows-first wrapper for the archived upstream `digitalocean/digitalocean-mcp` package.

## Provenance
- **Curated upstream**: `digitalocean/digitalocean-mcp` (archived upstream selected by user request)
- **Repo-owned wrapper**: local Codex / Claude / Gemini registration, env-only token wiring, and validation helpers

## Why this exists
The archived DigitalOcean MCP package is a straightforward stdio MCP server launched with:

```text
npx @digitalocean/mcp --services apps
```

This repo keeps a thin wrapper so the workstation can install, validate, and document the DigitalOcean App Platform surface without hardcoding secrets.

## Local install shape
- server name: `digitalocean`
- command: `npx`
- args: `["@digitalocean/mcp", "--services", "apps"]`
- required token source: `DIGITALOCEAN_API_TOKEN`
- Codex entry: `mcp_servers.digitalocean` in the canonical `config.toml`
- Claude entry: user-scoped `claude mcp` registration for `digitalocean`
- Gemini entry: `"digitalocean"` in `C:/Users/Prekzursil/.gemini/settings.json`

## Operator flow
1. Export `DIGITALOCEAN_API_TOKEN` in the local environment
2. Run `scripts/install-digitalocean-mcp.ps1`
3. Run `scripts/validate-digitalocean-mcp.ps1`
4. Confirm the three client registrations exist
5. If the token is present, confirm the client health checks connect; otherwise record the setup as env-gated

## Stop rules
- Keep the archived upstream selection explicit; do not silently swap to `digitalocean-labs/mcp-digitalocean`.
- Never write a raw DigitalOcean token into repo files, validation notes, or user config snapshots.
- Keep the default service set minimal (`apps`) unless the user explicitly asks for a broader DigitalOcean surface.
- If the token is absent, report the integration as configured but env-gated instead of pretending it is fully live.