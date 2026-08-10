---
name: ralph-orchestrator-setup
description: Use when installing, updating, validating, or troubleshooting the local Ralph Orchestrator CLI, its MCP server registration, or the mirrored Ralph skills for Codex, Claude, and Gemini.
---

# Ralph Orchestrator Setup

## Overview

Use this skill to install and validate the local Ralph Orchestrator runtime that this repo vendors and wires into Codex, Claude, and Gemini.

## Use This Skill For

- Installing or updating the local `ralph` CLI
- Registering `ralph mcp serve` for Codex, Claude, or Gemini
- Installing the mirrored `ralph-hats`, `ralph-loop`, and `ralph-orchestrator-setup` skills into the three agent homes
- Diagnosing a broken local Ralph setup after a CLI, MCP, or skill drift

## Workflow

1. Read `tools/editor/ralph-orchestrator/README.md`.
2. Run `tools/editor/ralph-orchestrator/scripts/install-ralph-orchestrator.ps1`.
3. Run `tools/editor/ralph-orchestrator/scripts/validate-ralph-orchestrator.ps1`.
4. Confirm `ralph --version`, `ralph doctor`, and the three client MCP checks all succeed from a trusted workspace.
5. Confirm `ralph-hats`, `ralph-loop`, and `ralph-orchestrator-setup` are installed for Codex, Claude, and Gemini.

## Guardrails

- Treat the Ralph CLI, its MCP registration, and the mirrored skills as separate surfaces; do not mark the setup healthy if one surface is still broken.
- Keep the user-level MCP server workspace-agnostic by default. Use `--workspace-root` only for targeted validation or when the user explicitly wants a single locked workspace.
- If `ralph doctor` reports warnings or any client still shows a disconnected MCP entry, capture the exact blocked state instead of silently degrading the install.
- Do not edit the vendored upstream snapshot under `tools/editor/ralph-orchestrator/vendor/` unless the task is an intentional upstream refresh.

### Quick Reference
