# Ralph Orchestrator

`tools/editor/ralph-orchestrator/` is the repo-owned Windows-first integration layer for the upstream `mikeyobrien/ralph-orchestrator` framework.

## Provenance
- **Curated upstream snapshot**: `mikeyobrien/ralph-orchestrator` version `2.8.1`, commit `9673d910e88fbe8ed41787f9a433cdd697e7ec3f`
- **Repo-owned wrapper**: local install, MCP registration, cross-agent skill install, and validation helpers for Codex, Claude, and Gemini

## Why this exists
Ralph is a host-local orchestration framework with:
- a local CLI (`ralph`)
- a workspace-scoped MCP server (`ralph mcp serve`)
- a public skill package (`ralph-hats`, `ralph-loop`)

This repo vendors the upstream snapshot so the framework shape is inspectable and pinned, while the local wrapper keeps workstation install, MCP registration, and skill rollout deterministic.

## Local install shape
- vendored snapshot: `tools/editor/ralph-orchestrator/vendor/`
- default CLI install on this Windows workstation: WSL-backed prebuilt Linux binary unpacked under `~/.local/opt/ralph-orchestrator/` with `~/.local/bin/ralph` symlinked to the extracted binary
- the install helper also writes WSL-visible `claude` and `gemini` wrappers under `~/.local/bin/` so `ralph doctor` can see the Windows-hosted backends from inside WSL
- npm registry install remains available for non-Windows targets, but the current upstream npm package does not ship a Windows x64 artifact
- current Windows host execution path: `C:/Windows/System32/wsl.exe -e bash -lc 'export PATH="$HOME/.local/bin:$PATH"; /home/prekzursil/.local/bin/ralph mcp serve'`
- Codex MCP entry: `mcp_servers."ralph-orchestrator"` in the canonical `config.toml`
- Claude MCP entry: user-scoped `claude mcp` registration for `ralph-orchestrator`
- Gemini MCP entry: `"ralph-orchestrator"` in `C:/Users/Prekzursil/.gemini/settings.json`
- mirrored skills:
  - canonical repo-published copies under `.agents/skills/`
  - compatibility copies under `skills/`

## Operator flow
1. Run `scripts/install-ralph-orchestrator.ps1`
2. Run `scripts/validate-ralph-orchestrator.ps1`
3. Confirm `ralph --version` and `ralph doctor` succeed locally
4. Confirm the three MCP registrations point at `ralph mcp serve`
5. Confirm `ralph-hats`, `ralph-loop`, and `ralph-orchestrator-setup` are installed for Codex, Claude, and Gemini

## Stop rules
- Keep the global MCP registration workspace-agnostic; do not hardcode `--workspace-root` into the user-level server entry unless the user explicitly wants one-repo-only behavior.
- Treat the Ralph CLI, its MCP server, and the mirrored skills as separate verification surfaces. Do not claim the integration is healthy unless all three are checked.
- If `ralph doctor` or any client-specific MCP health check fails, report the exact blocked state instead of downgrading silently.
- Do not edit files inside `vendor/` unless you are intentionally refreshing the upstream snapshot.
