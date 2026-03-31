---
name: apply-callee-type-ex
description: Use when IDA Pro decompiler output suffers from missing or bad indirect-call types and you need ApplyCalleeTypeEx to improve call prototypes and downstream analysis quality.
---

# ApplyCalleeTypeEx

## Overview

Use ApplyCalleeTypeEx in IDA Pro when callsites are technically reachable but badly typed, especially around indirect calls or decompiler output that is blocked by missing callee information.

## Quick Workflow

1. Open the affected function in IDA Pro and identify the callsite whose type information is wrong or missing.
2. Apply the plugin to the relevant call or function context.
3. Re-run or refresh the decompiler view and inspect whether argument types and return type improved.
4. Capture the recovered type information in notes or propagate it into reusable type definitions when the result is stable.
5. Repeat only on the highest-value sites; do not spray the plugin everywhere without checking the effect.

## Common Mistakes

- Running the plugin without first identifying the specific bad callsite.
- Assuming one improved callsite fixes the entire surrounding type graph automatically.
- Forgetting to refresh and verify the decompiler output after the change.

## Reference Map

Read `references/upstream.md` for the upstream plugin source and the local IDA plugin path.
