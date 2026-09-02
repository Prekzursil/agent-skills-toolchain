# 2026-03-31 Ralph and workstation bundle validation

## Commands run

- `pwsh -File .\tools\editor\ralph-orchestrator\scripts\install-ralph-orchestrator.ps1`
- `pwsh -File .\tools\editor\ralph-orchestrator\scripts\validate-ralph-orchestrator.ps1`
- `pwsh -File .\tools\mcp\digitalocean-mcp\scripts\install-digitalocean-mcp.ps1`
- `pwsh -File .\tools\mcp\digitalocean-mcp\scripts\validate-digitalocean-mcp.ps1`
- `pwsh -File .\tools\mcp\workstation-codex-bundle\scripts\validate-workstation-bundle.ps1`

## Evidence

- Bundle validation passed with `workstation bundle validation passed`.
- The curated bundle config parsed successfully and contained both:
  - `ralph-orchestrator` -> WSL-backed `ralph mcp serve`
  - `digitalocean` -> `npx @digitalocean/mcp --services apps`
- The workstation bundle env snapshot still includes `CODECOV_BASE_URL`, `CODECOV_TOKEN`, `DEEPSOURCE_API_KEY`, and `CHROMATIC_PROJECT_TOKEN` and excludes retired `UNITY_MCP_REPO`.
- The Ralph validation lane confirmed `ralph 2.8.1`, a passing `ralph doctor`, and connected Codex/Claude registration.
- The DigitalOcean validation lane confirmed config registration for Codex/Claude/Gemini and classified the server as env-gated because `DIGITALOCEAN_API_TOKEN` is absent.

## Warnings / partials

- Ralph still reports environmental warnings for missing Claude auth and a dirty git worktree.
- Gemini MCP health checks are config-level only on this workstation because `gemini mcp list` times out.
- DigitalOcean live connectivity remains intentionally blocked until `DIGITALOCEAN_API_TOKEN` is provided in the user environment.
