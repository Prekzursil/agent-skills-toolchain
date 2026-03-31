---
name: reverse-engineering-toolkit
description: Use when selecting or sequencing reverse-engineering tools for Windows native analysis, dump triage, live debugging, binary diffing, signature generation, import repair, or MCP-backed disassembler workflows. Especially useful for choosing between WinDbg Preview, x64dbg, Cheat Engine, IDA Pro MCP, Ghidra MCP, Binary Ninja MCP, HexStrike AI, Frida, BinDiff/BinExport, ret-sync, and related helpers.
---

# Reverse Engineering Toolkit

## Overview

Use this skill to choose the smallest toolchain that fits the task, then hand off to the most specific tool skill or MCP skill instead of improvising. Prefer evidence-preserving workflows: dump or debugger first, then disassembler cleanup, then diffing or signature generation.

## Routing Matrix

- Crash dump, exception context, thread state, or module load questions: use `$windbg-preview` first.
- Live Windows process stepping, breakpoints, or fast attach loops: use `$x64dbg`; add Cheat Engine when you need memory inspection or trainer-style validation.
- Static analysis after live or dump evidence exists: use IDA Pro, Binary Ninja, or Ghidra. Use the matching MCP skill only when the MCP server itself needs setup or repair (`$ida-pro-mcp`, `$binary-ninja-mcp`, `$ghidra-mcp`).
- Debugger to disassembler synchronization: use `$ret-sync`.
- Binary-to-binary or version-to-version comparisons: use `$binexport` to export both sides, then `$bindiff` to compare.
- Signature generation for hooks or stable identifiers: use `$binja-sigmaker` or a Cheat Engine AOB workflow.
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
