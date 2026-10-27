---
name: windbg-preview
description: Use when triaging Windows crash dumps, inspecting threads, exceptions, modules, memory, or debugger commands against dump files such as .dmp artifacts before deeper disassembler work.
---

# WinDbg Preview

## Overview

Use WinDbg Preview as the first tool for normal Windows dump triage. It is the fastest way to answer: what crashed, which thread matters, which modules were loaded, and what addresses are worth carrying into a disassembler.

## Quick Workflow

1. Launch `windbg-preview` and open the target dump.
2. Start with exception context, stack, active threads, and loaded modules before exploring raw memory.
3. Copy the exact module names, offsets, and thread IDs that look interesting.
4. Move those addresses into IDA Pro, Binary Ninja, or Ghidra only after the dump-side evidence is stable.
5. Use Volatility 3 only when you specifically need a memory-forensics workflow instead of a normal debugger-centric dump review.

## Common Mistakes

- Jumping to static analysis before confirming the exception and owning thread.
- Treating WinDbg as a decompiler replacement instead of a triage front-end.
- Using Volatility first for a normal Windows application dump.

## Reference Map

Read `references/upstream.md` for the local launch command and the SWFOC dump path already staged on this workstation.
