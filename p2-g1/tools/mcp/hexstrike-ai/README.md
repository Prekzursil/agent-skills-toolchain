# HexStrike AI

`tools/mcp/hexstrike-ai/` is the repo-owned Windows-first integration layer for the upstream `0x4m4/hexstrike-ai` project.

## Provenance
- **Curated upstream**: `0x4m4/hexstrike-ai` at commit `83337796dcfb8cfbf733bd24d0b2c7e4f0732790`
- **Repo-owned wrapper**: local install, localhost runtime bootstrap, Codex / Claude / Gemini registration, and validation helpers

## Why this exists
HexStrike ships as a two-part upstream runtime:
- `hexstrike_server.py` runs the local HTTP service
- `hexstrike_mcp.py --server http://127.0.0.1:8888` exposes the MCP-facing adapter

This repo does not take ownership of the upstream implementation. It keeps a thin, reproducible Windows-first layer so the workstation can install, start, validate, and document the HexStrike runtime consistently across Codex, Claude, and Gemini.

## Local install shape
- upstream checkout: `C:/Users/Prekzursil/.local/opt/hexstrike-ai`
- venv: `C:/Users/Prekzursil/.local/opt/hexstrike-ai/.venv`
- launcher: `C:/Users/Prekzursil/.local/opt/hexstrike-ai/hexstrike_mcp_launcher.py`
- server bind: `http://127.0.0.1:8888`
- Codex MCP entry: `mcp_servers."hexstrike-ai"` in the canonical `config.toml`
- Claude MCP entry: user-scoped `claude mcp` registration for `hexstrike-ai`
- Gemini MCP entry: `"hexstrike-ai"` in `C:/Users/Prekzursil/.gemini/settings.json`

## Operator flow
1. Run `scripts/install-hexstrike-ai.ps1`
2. Run `scripts/validate-hexstrike-ai.ps1`
3. Confirm `/health` responds on `127.0.0.1:8888`
4. Confirm the three client registrations point at the same launcher path
5. Use the MCP from a trusted local workstation only

## Stop rules
- Keep the HTTP service bound to `127.0.0.1` only; do not expose it remotely without a fresh design and auth review.
- Treat HexStrike as a high-trust local security-testing runtime. Do not silently widen access beyond the local workstation.
- If the upstream Python environment fails to resolve or the HTTP health endpoint never comes up, stop and fix the runtime before claiming the MCP registration is healthy.
- If upstream dependency resolution becomes Windows-incompatible, capture that explicitly in validation rather than pretending the install succeeded.
