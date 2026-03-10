# Agent Lanes Codex

`tools/mcp/agent-lanes-codex/` is the bounded MCP-side home for the Codex orchestration lane.

## Purpose

Expose structured Codex workflows through MCP with explicit profile names, explicit tool aliases, and bounded fallback behavior.

## Profiles

- `consult`
- `review`
- `curate`
- `brainstorm`
- `discuss`
- `coordinate`

## Explicit aliases

Preferred explicit aliases on this side include:
- `codex_local_consult`
- `codex_local_review`
- `codex_local_curate`
- `codex_orchestrator_consult`
- `codex_orchestrator_review`
- `codex_orchestrator_curate`

## Boundary

This lane is MCP-native first. It owns:
- profile resolution
- Codex multi-pass execution
- structured result shaping
- optional secondary ChatGPT web curation
- fallback to Codex synthesis if the web lane fails

It does not own browser automation directly.

## Safety notes

When the optional ChatGPT web curator is enabled, this lane should:
- verify readiness first
- inspect session state first
- reject wrong-vendor or blocked sessions
- fall back to Codex synthesis if the web lane fails

## Promotion rule

Keep this folder as the live bounded home for the MCP-side contract, docs, and packaging plan. Runtime code may live elsewhere until the project is promoted into a fully in-repo runnable package.
