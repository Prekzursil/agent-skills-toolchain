---
name: volatility-3
description: Use when a memory image must be analyzed to recover processes, modules,
  or unpacked binaries that only exist in RAM.
permalink: dqverify-repo-20261013/skills/volatility-3/skill
---

# Volatility 3

## Overview

Use Volatility 3 when the important artifact is in memory rather than on disk. It is the bridge between dynamic behavior and later static analysis, especially for unpacked or injected malware.

## Quick Workflow

1. Confirm the memory image source, operating system family, and acquisition context before running plugins.
2. Start with process and module inventory (`pslist`, `pstree`, DLL/module views) before dumping anything.
3. Dump only the process, region, or module that answers the current question.
4. Preserve hashes, offsets, process IDs, and command transcripts with every dump.
5. Hand recovered binaries to a static RE tool only after confirming the dump scope is correct.

## Common Mistakes

- Dumping large amounts of memory before identifying the process of interest.
- Losing the mapping between dump artifacts and the original PID or memory region.
- Treating a memory dump as clean without checking for multiple stages or injected modules.

## Reference Map

Read `references/upstream.md` for install notes and starter plugins.