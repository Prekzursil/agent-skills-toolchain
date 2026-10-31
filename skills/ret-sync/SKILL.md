---
name: ret-sync
description: Use when synchronizing a live debugger with IDA Pro, Binary Ninja, or
  compatible disassemblers so stepping and addresses stay aligned during native reverse-engineering.
permalink: dqverify-repo-20261013/skills/ret-sync/skill
---

# ret-sync

## Overview

Use ret-sync after the debugger path is already narrowed down. It is not the first step; it is the bridge that keeps a live debugger and a static-analysis surface aligned once you know which module or function family matters.

## Quick Workflow

1. Open the target in your debugger first (usually `$x64dbg` in this environment).
2. Open the corresponding binary in IDA Pro or Binary Ninja.
3. Start ret-sync on the static side, then connect from the debugger side.
4. Verify that a simple step or breakpoint navigation updates both views before doing deeper analysis.
5. Keep plain notes of module base, rebasing assumptions, and sync status so you can recover quickly after a restart.

## Common Mistakes

- Trying to set up synchronization before the debugger path is stable.
- Assuming Ghidra support is ready without checking the local version-specific extension story.
- Forgetting to verify that both sides agree on the active module base.

## Reference Map

Read `references/upstream.md` for the local plugin staging paths and the current Ghidra caveat.