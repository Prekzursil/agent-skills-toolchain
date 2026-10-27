---
name: binary-ninja
description: Use when Binary Ninja UI workflows, intermediate-language reasoning, or Binary Ninja Python API automation are needed for reverse engineering tasks.
---

# Binary Ninja

## Overview

Use Binary Ninja when you need a modern RE UI plus a powerful Python API and IL stack. It is especially useful for automation, plugin development, and cross-checking decompiler output through HLIL, MLIL, and LLIL.

## Quick Workflow

1. Confirm Binary Ninja is installed; if it is missing, stop and report the host-app block.
2. Open the target, let analysis settle, and note which IL layer answers the current question best.
3. Prefer small API scripts or plugin helpers for repeatable transformations and naming work.
4. Record the exact IL level, function, and address range behind every conclusion.
5. Use `binary-ninja-mcp` only when the request is specifically about client integration.

## Common Mistakes

- Quoting decompiler output without checking the IL layer that produced it.
- Assuming Binary Ninja automation can proceed when the host app is not installed.
- Mixing plugin-development tasks with one-off analysis notes.

## Reference Map

Read `references/upstream.md` for install reminders and Binary Ninja API entry points.
