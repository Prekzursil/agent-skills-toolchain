---
title: patterns
type: note
permalink: dqverify-repo-20261013/skills/ida-decompiler-cleanup/references/patterns
---

# IDA Decompiler Cleanup Patterns

## Best local helpers

- `$apply-callee-type-ex` for bad indirect-call typing
- `$binexport` once the function understanding is stable enough to compare builds
- `$ret-sync` when live debugger context is needed while cleaning up the function

## Order of operations

1. Confirm the region with dump/debugger evidence if available
2. Fix the call typing that blocks interpretation
3. Rename only the variables and structures that remove actual ambiguity
4. Re-decompile and verify the logic changed in a meaningful way
5. Preserve the result in notes or follow-on export/signature work