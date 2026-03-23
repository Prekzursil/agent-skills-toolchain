---
name: promptbridge-codex-consult
description: Use when installing, probing, or debugging PromptBridge-backed Codex consultation in the Windows-only canonical CODEX_HOME setup.
---

# PromptBridge Codex Consult

## Setup Contract
- Canonical root = active Windows `CODEX_HOME`, default `%USERPROFILE%\.codex`.
- `.codex-vscode` is legacy migration input only.
- `codex_consult` is the managed MCP server.

## Verification Flow
1. Run `status` from the Codex bootstrap CLI.
2. Run `probe` and `self-test` from the same root.
3. Reload the IDE and start a fresh chat before claiming VS Code visibility.

## Fallback
If PromptBridge is unavailable, emit `fallback_to_lane_a = true` and continue with native Codex orchestration.
