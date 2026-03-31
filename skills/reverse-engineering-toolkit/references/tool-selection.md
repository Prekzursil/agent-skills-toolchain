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
