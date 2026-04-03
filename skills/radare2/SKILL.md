---
name: radare2
description: Use when command-line disassembly, debugging, hex editing, or scriptable low-level binary triage is needed without relying on a heavyweight GUI first.
---

# radare2

## Overview

Use radare2 when you need a scriptable command-line reversing environment. It is strongest when you want fast binary triage, disassembly, patching, debugging, and exact control over analysis steps.

## Quick Workflow

1. Open the target with `r2 -A <binary>` when you want initial analysis.
2. Use `aaa` only when deeper analysis is needed; avoid expensive analysis upfront if triage is enough.
3. Enumerate functions with `afl`, seek with `s`, inspect disassembly with `pdf`, and review strings/imports before patching.
4. Use debugger commands only after the static picture is stable.
5. Save command history or scripts for repeatable investigations.

## Common Mistakes

- Running every expensive analysis pass before understanding the target size and goal.
- Mixing triage and live-debug steps without capturing a stable baseline first.
- Treating r2 output as self-explanatory instead of annotating addresses, functions, and hypotheses.

## Reference Map

Read `references/upstream.md` for install guidance and high-signal starter commands.
