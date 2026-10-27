---
name: cheat-engine-x64dbg-ida-handoff
description: Use when moving runtime findings between Cheat Engine, x64dbg, and IDA Pro, especially for converting value scans or breakpoints into typed static analysis and durable module-relative anchors.
---

# Cheat Engine x64dbg IDA Handoff

## Overview

Use this skill when you already know the three tools belong in the same workflow. The goal is to preserve evidence while moving from quick runtime discovery to breakpoint-led understanding to durable static interpretation.

## Handoff Pattern

1. Start in `$cheat-engine-workflow` when you only have a live value, toggle, structure field, or AOB candidate.
2. Move to `$x64dbg` once you need control flow, breakpoints, or instruction-level confirmation.
3. Carry the result into IDA only after you can state the module, relative offset, and the bytes or callsite that matter.
4. Use `$ida-decompiler-cleanup` to make the relevant function understandable, not to clean the whole binary.
5. If the result must persist across builds, route it into `$dump-to-signature-workflow` or `$binary-ninja-diff-signatures` depending on the static surface you prefer.

## Common Mistakes

- Jumping straight from Cheat Engine to IDA without a debugger-confirmed control-flow explanation.
- Moving a runtime address into IDA without preserving module-relative context.
- Treating the handoff as done before the IDA function is understandable enough to support the next step.

## Reference Map

Read `references/handoff.md` for the exact evidence that should survive each tool transition.
