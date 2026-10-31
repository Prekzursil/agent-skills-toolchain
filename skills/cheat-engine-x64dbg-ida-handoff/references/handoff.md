---
title: handoff
type: note
permalink: dqverify-repo-20261013/skills/cheat-engine-x64dbg-ida-handoff/references/handoff
---

# Cheat Engine -> x64dbg -> IDA Handoff

## Preserve this at each step

### From Cheat Engine
- the observed value or structure field
- any pointer assumptions
- surrounding bytes or AOB candidate
- module name if known

### From x64dbg
- confirmed module base
- module-relative offset
- breakpoint location and reason it matters
- surrounding instructions / bytes

### Into IDA
- use the module-relative location, not just an absolute address
- confirm the same bytes or callsite statically
- clean only the function or callsite that matters

## Escalation

- use `$dump-to-signature-workflow` when the final output should be a durable pattern
- use `$ida-decompiler-cleanup` when the static view is the bottleneck