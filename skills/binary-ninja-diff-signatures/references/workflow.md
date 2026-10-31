---
title: workflow
type: note
permalink: dqverify-repo-20261013/skills/binary-ninja-diff-signatures/references/workflow
---

# Binary Ninja Diff and Signature Workflow

## Local helpers

- `$peutils` -> PE/import cleanup helper
- `$binexport` -> export comparison artifacts
- `$bindiff` -> compare exported builds
- `$binja-sigmaker` -> generate stable byte signatures

## Recommended sequence

1. Fix Binary Ninja-side structural confusion first
2. Export both sides if cross-build stability matters
3. Review changed/unmatched functions with BinDiff
4. Return to Binary Ninja for the concrete bytes and signature generation
5. Keep the final signature tied to the compared builds and module-relative context