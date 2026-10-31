---
name: swfoc-runtime-address-hunting
description: Use when hunting SWFOC-specific runtime addresses, function anchors,
  structures, or memory regions in the SWFOC editor or swfoc_memory workspaces, especially
  when correlating dump evidence, debugger traces, and static analysis.
permalink: dqverify-repo-20261013/skills/swfoc-runtime-address-hunting/skill
---

# SWFOC Runtime Address Hunting

## Overview

Use this skill for SWFOC-specific native address work. The point is not just to find an address once; it is to identify a reproducible anchor that can be checked against dumps, debugger traces, and static analysis.

## Workflow

1. Start from the strongest existing evidence source you already have: the dump bundle, a debugger breakpoint, or a Cheat Engine value discovery.
2. Confirm the target module and capture module-relative offsets immediately.
3. Cross-check the same region in IDA Pro, Binary Ninja, or Ghidra before treating it as stable.
4. When the finding matters across builds, route it through `$dump-to-signature-workflow`.
5. Keep all SWFOC-specific notes tied to the real workspace artifacts, not to memory-only assumptions.

## Common Mistakes

- Hunting addresses from scratch without first reading the existing SWFOC dump bundle.
- Keeping absolute addresses without module-base context.
- Mixing trainer/editor source assumptions with runtime-native evidence without proving the bridge.

## Reference Map

Read `references/hunting-notes.md` for the exact local workspaces and the prebuilt artifact bundle to consult first.