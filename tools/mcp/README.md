# MCP Tools

`tools/mcp/` is the live home for MCP-native orchestration tooling and other bounded server-side projects.

## Current bounded projects

### `agent-lanes-codex`

- Codex-side orchestration lane with explicit profiles, aliases, and bounded fallback behavior.

### `codex-orchestrator`

Location:

```text
tools/mcp/codex-orchestrator
```

Purpose:

- expose multi-agent Codex planning/review tools through MCP
- keep one shared orchestration backend behind thin user-facing tools
- support named profiles plus per-call overrides

Primary tools:

- `codex_consult`
- `codex_brainstorm`
- `codex_review`
- `codex_discuss`
- `codex_coordinate`
- `codex_curate`

The shared result contract is stable across all six tools.

### `workstation-codex-bundle`

- curated Windows-first MCP bundle with explicit self-made vs curated provenance and validation notes

## Operator commands

From the repo root:

```powershell
npm run orchestration:status
npm run orchestration:probe
npm run orchestration:self-test
```
