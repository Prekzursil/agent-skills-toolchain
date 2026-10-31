---
title: tool-selection
type: note
permalink: dqverify-repo-20261013/skills/reverse-engineering-toolkit/references/tool-selection
---

# Reverse Engineering Toolkit Reference

## Local commands and installs

- `windbg-preview` -> local shim that launches WinDbg Preview (`WinDbgX.exe`)
- `x64dbg` -> local shim for the winget-installed x64dbg package
- `r2` / `radare2` -> Chocolatey install
- `vol` -> Chocolatey install for Volatility 3
- `angr-python` -> dedicated virtualenv Python with `angr` installed
- `ida64`, `ghidraRun`, `binaryninja` -> local host-app shims

## Tool-first matrix

- `.dmp` / crash triage -> WinDbg Preview
- Live process stepping / API trace anchors -> x64dbg
- Runtime memory edits / value discovery -> Cheat Engine
- Static analysis / decompiler cleanup -> IDA Pro, Binary Ninja, or Ghidra
- Diffing two builds -> BinExport, then BinDiff
- Signature generation -> binja_sigmaker or Cheat Engine AOB scan workflow
- Import / PE cleanup in Binary Ninja -> peutils
- Python automation over Ghidra -> ghidra_bridge

## Existing MCP skills in the toolchain

- `hexstrike-ai-mcp`
- `frida-mcp`
- `ida-pro-mcp`
- `ghidra-mcp`
- `binary-ninja-mcp`
- `repomix`
- `mcp-graphql`

Use those skills when the MCP server itself needs to be installed, repaired, or registered for Codex, Claude Code, or Gemini CLI.

## Autonomous headless launch (re_launch.py)

The agent brings up the IDA / Ghidra / HexStrike MCP servers itself — no manual GUI launch. Entry point:

```
python C:\Users\Prekzursil\.local\opt\re-harness\re_launch.py <tool> [binary] [--status] [--teardown]
```

`<tool>` is `ida`, `ghidra`, or `hexstrike`. Omitting `[binary]` uses `defaults.default_binary` from the harness `config.yaml`. The launcher is idempotent, cold-starts the server detached on a dedicated port, health-polls to ready, and emits a terminal `SUCCESS:<tool>` / `FAILED:<tool>` marker.

| Tool | Port | Mode | Notes |
|---|---|---|---|
| ida | 8745 | true headless (`ida_pro_mcp.idalib_server`) | needs `IDADIR=C:\Program Files\IDA Professional 9.3`; fresh-binary analysis blocks minutes (run detached); a GUI-locked IDB must be copied to scratch before opening headless. Distinct from the live GUI IDA on 13337. |
| ghidra | 8089 | true headless (bundled `GhidraMCPHeadlessServer`) | MCP route is `/list_methods`, NOT `/methods` (`/methods` 404s). |
| hexstrike | 8888 | Flask server | upstream HexStrike AI runtime launcher. |
| binary ninja | — | DEFERRED | Personal license forbids headless; GUI/MCP only, no `bn` launch path. |

Safety guarantee: teardown is registry-gated (`state/registry.json` records `spawned_by_harness`), so it kills only servers the harness spawned whose registered PID still owns the registered port. The live GUI IDA on 13337 is never in the registry and can never be a teardown target. Drive the running server through `mcp__ida-pro-mcp__*` / `mcp__ghidra-mcp__*` / the HexStrike tools; `--teardown` when done.

Full reference: `C:\Users\Prekzursil\.local\opt\re-harness\README.md`.