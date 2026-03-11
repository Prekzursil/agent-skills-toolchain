# 2026-03-11 process parentage audit

This is a no-Codex-kill audit of the current helper-process storm. The goal is to separate expected child MCP helpers from true orphan noise.

## Current headline counts
- `Code.exe`: about 96
- `codex.exe`: about 9
- `node.exe`: about 180 after the wider workstation load
- `uvx.exe`: about 51
- `msedge.exe`: about 54

## High-signal finding
The duplicate MCP helper storm is primarily caused by **multiple live `codex.exe app-server` parents**, not by one runaway orphaned helper. During the audit, the following active `codex.exe` parents owned many helper children:
- `4216`
- `42652`
- `56856`
- smaller additional parents for older sessions

## Concrete child examples
Observed child stdio helpers under active Codex parents included:
- `promptbridge_talk` node servers
- `docker-mcp`
- `excel-mcp-server`
- `scrapegraph-mcp`
- `markitdown-mcp`
- `@playwright/mcp`
- `chrome-devtools-mcp`
- `@codacy/codacy-mcp`
- `firecrawl-mcp`
- `tavily-mcp`
- `@wonderwhy-er/desktop-commander`

This means many duplicates are **session fan-out**, not proof that the helper itself is intrinsically broken.

## Immediate fixes applied in this pass
- Removed Serena from the canonical config and stopped the remaining live Serena helper tree.
- Disabled `postgres` in the canonical config because it was the largest current-noise source.
- Stopped the already-running duplicate helper containers for `ghcr.io/pgedge/postgres-mcp:latest`.
- Terraform was later removed from the curated bundle entirely rather than kept as a disabled noise source.

## Result after targeted cleanup
- `postgres-mcp` running containers: `0`
- MindsDB remains up as the only intended local MCP containerized service in this slice

## Operational conclusion
A completely clean helper list is not achievable without closing or reloading unused VS Code / Codex windows, because the active app-server fan-out is real. The safe approach is:
1. keep the canonical MCP set lean
2. disable the noisiest MCPs by default when they are not currently needed (`postgres`)
3. avoid kill-all cleanup against `codex.exe`
4. only recycle verified stale child helpers or helper containers
