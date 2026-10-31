# x64dbg Notes

## Upstream

- Package source used locally: `winget install --id x64dbg.x64dbg`
- Project site: https://x64dbg.com/

## Local launch

- Command: `x64dbg`
- Shim target: `%USERPROFILE%\.local\bin\x64dbg.cmd`

## Best companion tools

- `ret-sync` when you need live-debugger to disassembler synchronization
- Cheat Engine when you need value discovery or trainer-style state confirmation
- IDA Pro / Binary Ninja / Ghidra after the interesting code path is known
