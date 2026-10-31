---
name: reverse-engineering-toolkit
description: Use when selecting or sequencing reverse-engineering tools for Windows native analysis, dump triage, live debugging, binary diffing, signature generation, import repair, or MCP-backed disassembler workflows. Especially useful for choosing between WinDbg Preview, x64dbg, Cheat Engine, IDA Pro MCP, Ghidra MCP, Binary Ninja MCP, HexStrike AI, Frida, BinDiff/BinExport, ret-sync, and related helpers.
---

# Reverse Engineering Toolkit

## Overview

Use this skill to choose the smallest toolchain that fits the task, then hand off to the most specific tool skill or MCP skill instead of improvising. Prefer evidence-preserving workflows: dump or debugger first, then disassembler cleanup, then diffing or signature generation.

## Autonomous Tool Launch (no manual GUI)

When RE work needs IDA, Ghidra, or HexStrike and the MCP server / tool is not already up, bring it up yourself headlessly. Do NOT ask the user to hand-launch or navigate a GUI, and do NOT stall waiting for a backend — drive the launcher directly:

```
python C:\Users\agentuser\.local\opt\re-harness\re_launch.py <tool> [binary] [--status] [--teardown]
```

`<tool>` is `ida`, `ghidra`, or `hexstrike`. `[binary]` is optional (omitting it uses the configured default binary). The launcher is idempotent (probes first; reports `SUCCESS:<tool> already-up` if the server is already listening), cold-starts the server detached on a dedicated port, and health-polls it to ready before returning a terminal `SUCCESS:<tool>` / `FAILED:<tool>` marker.

Workflow:
1. Launch (or just probe): `re_launch.py <tool> [binary]` — use `--status` to only check the port + harness-owned registry row.
2. Drive the live server through its MCP surface: `mcp__ida-pro-mcp__*`, `mcp__ghidra-mcp__*`, or the HexStrike tools (route via ToolSearch if the schemas are not loaded). Use the per-tool MCP skills (`$ida-pro-mcp`, `$ghidra-mcp`, `$hexstrike-ai-mcp`, `$binary-ninja-mcp`) only when the MCP server itself needs install, repair, or registration — not to launch one for analysis.

### Routing Matrix
### MCP Guidance
### Common Mistakes
### Reference Map
