---
title: 2026-03-31-local-validation
type: note
permalink: dqverify-repo-20261013/tools/mcp/digitalocean-mcp/validation/2026-03-31-local-validation
---

# 2026-03-31 DigitalOcean local validation

## Commands run

- `pwsh -File .\tools\mcp\digitalocean-mcp\scripts\install-digitalocean-mcp.ps1`
- `pwsh -File .\tools\mcp\digitalocean-mcp\scripts\validate-digitalocean-mcp.ps1`
- `pwsh -File .\tools\mcp\workstation-codex-bundle\scripts\validate-workstation-bundle.ps1`

## Evidence

- `npx @digitalocean/mcp --help` returned the archived App Platform server usage text successfully.
- `codex mcp get digitalocean` showed:
  - `enabled: true`
  - `command: npx`
  - `args: @digitalocean/mcp --services apps`
  - `env: DIGITALOCEAN_API_TOKEN=*****`
- `claude mcp get digitalocean` showed the server registered in user scope and attempted to connect with `npx @digitalocean/mcp --services apps`.
- Gemini registration was verified from `C:\Users\Prekzursil\.gemini\settings.json`; the validation probe for `gemini mcp list` timed out after 15 seconds on this workstation, so Gemini was verified at the config level rather than by a live CLI health check.
- `pwsh -File .\tools\mcp\workstation-codex-bundle\scripts\validate-workstation-bundle.ps1` passed with `workstation bundle validation passed` and confirmed the curated Codex snapshot includes both `digitalocean` and `ralph-orchestrator`.

## Warnings / partials

- `DIGITALOCEAN_API_TOKEN` was not present in the current session during validation.
- Because the token is absent, `claude mcp get digitalocean` reports `Status: ✗ Failed to connect`; this is expected and the integration should be treated as configured but env-gated.
- Gemini CLI health probing remains best-effort because `gemini mcp list` is currently non-responsive on this workstation.