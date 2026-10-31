---
name: windbg-command-cookbook
description: Use when you need concrete WinDbg Preview command sequences for crash
  dumps, exception context, thread triage, stack inspection, module inventory, or
  address extraction before moving to static analysis.
permalink: dqverify-repo-20261013/skills/windbg-command-cookbook/skill
---

# WinDbg Command Cookbook

## Overview

Use this skill when the user needs practical WinDbg command flow, not just tool selection. The goal is to move from a dump file to stable exception, thread, stack, and module evidence that can be reused elsewhere.

## Cookbook Flow

1. Open the dump with `$windbg-preview`.
2. Start with the exception and the currently interesting thread before branching into deep memory inspection.
3. Capture the stack and module list before trying to interpret game-specific structures.
4. Export interesting module-relative addresses into your notes so they can be checked in IDA, Binary Ninja, or Ghidra.
5. Only then move to `$dump-to-signature-workflow` or `$swfoc-runtime-address-hunting`.

## Common Mistakes

- Running deep commands before understanding the crash or active thread.
- Copying raw absolute addresses without module-relative context.
- Treating the cookbook as exhaustive instead of using it to get to the next useful artifact.

## Reference Map

Read `references/commands.md` for the concrete WinDbg commands and the intended purpose of each one.