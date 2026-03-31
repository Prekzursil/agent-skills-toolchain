---
name: x64dbg
description: Use when live-debugging a Windows process, tracing code paths, setting breakpoints, or pairing a live debugger with ret-sync and a disassembler during native reverse-engineering work.
---

# x64dbg

## Overview

Use x64dbg for fast user-mode debugging on Windows before you commit to heavier static-analysis cleanup. It is the best first live debugger in this stack for breakpoints, stepping, register inspection, and quick attach loops.

## Quick Workflow

1. Launch `x64dbg` and open or attach to the target process.
2. Set one or two coarse breakpoints first (module entry, hot imports, obvious routines) instead of blanketing the process.
3. Capture module bases, interesting addresses, and short notes as soon as you confirm a path.
4. Add `$ret-sync` only when you already know which code region matters and want disassembler synchronization.
5. Hand decompiler cleanup or signature generation off to the static-analysis skill that matches the active disassembler.

## Common Mistakes

- Treating x64dbg traces as the final artifact instead of copying findings into static notes.
- Starting with too many breakpoints before understanding the module layout.
- Forgetting to capture module base deltas before comparing separate runs.

## Reference Map

Read `references/upstream.md` for local install notes, launch commands, and the expected companion tools in this environment.
