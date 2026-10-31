---
name: reverse-engineering-toolkit
description: Use when selecting or sequencing reverse-engineering tools for Windows native analysis, dump triage, live debugging, binary diffing, signature generation, import repair, or MCP disassembler workflows. Choose from WinDbg Preview, x64dbg, Cheat Engine, IDA Pro MCP, Ghidra MCP, Binary Ninja MCP, HexStrike AI, Frida, BinDiff/BinExport, ret-sync. NOT for triaging a binary (use re-triage-preflight).
---

# Reverse Engineering Toolkit

## Overview

Use this skill to choose the smallest toolchain that fits the task, then hand off to the most specific tool skill or MCP skill instead of improvising. Prefer evidence-preserving workflows: dump or debugger first, then disassembler cleanup, then diffing or signature generation.

## Autonomous Tool Launch (no manual GUI)

When RE work needs IDA, Ghidra, or HexStrike and the MCP server / tool is not already up, bring it up yourself headlessly. Do NOT ask the user to hand-launch or navigate a GUI, and do NOT stall waiting for a backend — drive the launcher directly:

```
python C:\Users\Prekzursil\.local\opt\re-harness\re_launch.py <tool> [binary] [--status] [--teardown]
```

`<tool>` is `ida`, `ghidra`, or `hexstrike`. `[binary]` is optional (omitting it uses the configured default binary). The launcher is idempotent (probes first; reports `SUCCESS:<tool> already-up` if the server is already listening), cold-starts the server detached on a dedicated port, and health-polls it to ready before returning a terminal `SUCCESS:<tool>` / `FAILED:<tool>` marker.

Workflow:
1. Launch (or just probe): `re_launch.py <tool> [binary]` — use `--status` to only check the port + harness-owned registry row.
2. Drive the live server through its MCP surface: `mcp__ida-pro-mcp__*`, `mcp__ghidra-mcp__*`, or the HexStrike tools (route via ToolSearch if the schemas are not loaded). Use the per-tool MCP skills (`$ida-pro-mcp`, `$ghidra-mcp`, `$hexstrike-ai-mcp`, `$binary-ninja-mcp`) only when the MCP server itself needs install, repair, or registration — not to launch one for analysis.
3. When finished: `re_launch.py <tool> --teardown`. Teardown is registry-gated — it kills ONLY a server the harness itself spawned whose registered PID still owns its registered port.

Safety and gotchas (load-bearing):
- NEVER hand-launch a GUI for analysis, and NEVER kill the live GUI IDA on port 13337 (the only working 61-tool interactive surface). Headless IDA runs on a different port (8745); teardown can never target the GUI because it is not in the harness registry.
- IDA headless needs `IDADIR=C:\Program Files\IDA Professional 9.3` (the launcher exports it). Fresh-binary analysis blocks for minutes, so the harness runs it detached behind a hang-timeout poll; opening an existing `.i64` or loose IDB is instant (copy a GUI-locked IDB to a scratch dir before opening headless).
- Ghidra headless serves on 8089 and its MCP route is `/list_methods`, NOT `/methods` (`/methods` returns 404).
- HexStrike serves its Flask server on 8888.
- Binary Ninja is DEFERRED: the Personal license forbids headless, so there is no `bn` launch path — use the BN GUI/MCP only.

Full reference and safety design: `C:\Users\Prekzursil\.local\opt\re-harness\README.md`; see also `references/tool-selection.md`.

## Routing Matrix

- Crash dump, exception context, thread state, or module load questions: use `$windbg-preview` first; use `$windbg-command-cookbook` when you need concrete WinDbg commands.
- Live Windows process stepping, breakpoints, or fast attach loops: use `$x64dbg`; use `$cheat-engine-workflow` when you need value scans, pointer checks, or AOB validation; use `$cheat-engine-x64dbg-ida-handoff` when you already know the workflow must move through all three tools.
- Static analysis after live or dump evidence exists: use IDA Pro, Binary Ninja, or Ghidra. Use `$ida-decompiler-cleanup`, `$binary-ninja-diff-signatures`, or `$ghidra-automation-recipes` when the bottleneck is inside the chosen static-analysis surface. Use the matching MCP skill only when the MCP server itself needs setup or repair (`$ida-pro-mcp`, `$binary-ninja-mcp`, `$ghidra-mcp`).
- Debugger to disassembler synchronization: use `$ret-sync`.
- Binary-to-binary or version-to-version comparisons: use `$binexport` to export both sides, then `$bindiff` to compare.
- Signature generation for hooks or stable identifiers: use `$dump-to-signature-workflow` first, then `$binja-sigmaker` or a Cheat Engine AOB workflow.
- Bad indirect call typing in IDA: use `$apply-callee-type-ex`.
- Windows PE structure or import weirdness in Binary Ninja: use `$peutils`.
- External Python automation over Ghidra: use `$ghidra-bridge`.
- Symbolic exploration or path search: use the existing `$angr` skill only after the simpler debugger/disassembler path is exhausted.
- Memory-forensics-specific extraction from artifacts: use the existing `$volatility-3` skill only when WinDbg is not the right first tool.

## MCP Guidance

Only MCP servers need Codex, Claude Code, or Gemini registration. Do not invent client config for debugger plugins or host-only extensions. For MCP lifecycle work, route to the dedicated MCP skills already in the toolchain: `$hexstrike-ai-mcp`, `$frida-mcp`, `$ida-pro-mcp`, `$ghidra-mcp`, `$binary-ninja-mcp`, `$repomix`, and `$mcp-graphql`.

## Common Mistakes

- Starting with Volatility or angr before a normal Windows dump or debugger pass.
- Treating debugger notes as final findings without copying addresses, bytes, and module bases into static analysis notes.
- Comparing binaries before exporting clean BinExport artifacts from both sides.
- Adding Codex, Claude, or Gemini config for tools that are not MCP servers.

## Reference Map

Read `references/tool-selection.md` for the local install state, upstream pointers, and a one-screen matrix of when each tool should be first in line.
