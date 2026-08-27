---
name: binary-ninja-diff-signatures
description: Use when working in Binary Ninja to compare versions, analyze changed functions, or generate stable signatures for runtime hooks, trainer features, or address portability across builds.
---

# Binary Ninja Diff and Signatures

## Overview

Use this skill when Binary Ninja is the main static surface for version drift and signature work. It combines Binary Ninja-side cleanup, BinExport/BinDiff comparisons, and `binja_sigmaker` generation into one workflow.

## Workflow

1. Open the relevant binary in Binary Ninja and stabilize imports or PE structure with `$peutils` if needed.
2. If build-to-build comparison matters, export both binaries with `$binexport` and review the changed functions with `$bindiff`.
3. Once the target function family is understood, generate a signature with `$binja-sigmaker`.
4. Record the module, function anchor, and build provenance immediately.
5. Feed the final artifact into the SWFOC runtime workflow only after validating the signature or diff result against a second build when possible.

## Common Mistakes

- Generating signatures before checking whether the function changed across builds.
- Ignoring PE/import problems that make the Binary Ninja view less stable than it should be.
- Treating BinDiff output as final truth without rechecking the bytes in Binary Ninja.

## Reference Map

Read `references/workflow.md` for the local plugin staging and the exact order to move from Binary Ninja cleanup to diffing to signature generation.
