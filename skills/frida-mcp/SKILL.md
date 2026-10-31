---
name: frida-mcp
description: Use when installing or configuring frida-mcp as an MCP server for live
  Frida instrumentation in Codex, Claude Code, or Gemini CLI.
permalink: dqverify-repo-20261013/skills/frida-mcp/skill
---

# Frida MCP

## Overview

Use `frida-mcp` when an AI client needs direct access to Frida process, device, and scripting operations. Prefer a dedicated virtual environment under `~/.local/opt/frida-mcp` so the command path stays stable across client registrations.

## Quick Workflow

1. Confirm core Frida tooling works first (`frida-ps` or `frida --version`).
2. Install or update the MCP package with `tools/mcp/reverse-engineering-mcp-bundle/scripts/install_python_mcp.py`.
3. Register `manifests/frida-mcp.json` into Codex, Claude, and Gemini with the shared registration helper.
4. Verify the client can at least enumerate devices or processes before using it for deep instrumentation.
5. Switch to the plain `frida` skill when the work is about scripts, hooks, or runtime technique rather than MCP setup.

## Common Mistakes

- Installing `frida` or `frida-tools` and assuming the MCP layer is included.
- Forgetting to confirm transport context (local, USB, remote) before judging the MCP server.
- Treating package install as complete without registering the client entry.

## Reference Map

Read `references/upstream.md` for the upstream install snippet and the repo bundle commands.