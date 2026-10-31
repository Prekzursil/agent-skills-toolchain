---
name: ida-decompiler-cleanup
description: Use when Hex-Rays decompiler output in IDA Pro is noisy, poorly typed,
  or hard to reason about, especially for indirect-call typing, prototype cleanup,
  structure naming, variable cleanup, and preparing functions for durable analysis
  or signature work.
permalink: dqverify-repo-20261013/skills/ida-decompiler-cleanup/skill
---

# IDA Decompiler Cleanup

## Overview

Use this skill when IDA already has the right region but the decompiler output is too messy to trust. The goal is to improve readability and type quality just enough to support the next decision, not to cosmetically perfect the entire binary.

## Cleanup Workflow

1. Start with the smallest function or callsite that actually blocks progress.
2. Fix indirect or poorly typed calls first with `$apply-callee-type-ex` when appropriate.
3. Normalize obvious local variable names, argument meaning, and structure names only where they improve the current reasoning path.
4. Re-decompile and confirm the cleanup changed the control flow or data understanding in a useful way.
5. Export the improved understanding into notes, BinExport, or a signature workflow once the function is stable enough.

## Common Mistakes

- Spending time on global beautification instead of the function that currently matters.
- Renaming aggressively before the control flow is understood.
- Treating decompiler cleanup as complete evidence instead of cross-checking against bytes, stack usage, or debugger findings.

## Reference Map

Read `references/patterns.md` for the local plugin helpers and the recommended cleanup order.