---
title: pipeline
type: note
permalink: dqverify-repo-20261013/skills/dump-to-signature-workflow/references/pipeline
---

# Dump to Signature Pipeline

## Recommended chain

1. Dump/debugger evidence from `$windbg-preview`, `$x64dbg`, or `$cheat-engine-workflow`
2. Normalize to module + relative offset + byte window
3. Verify in a static tool (IDA Pro, Binary Ninja, or Ghidra)
4. Export comparison data with `$binexport` when version drift matters
5. Compare with `$bindiff` when needed
6. Generate the final pattern with `$binja-sigmaker` or a Cheat Engine AOB scan

## Local tools already staged

- BinDiff installed under `C:\Program Files\BinDiff\bin\bindiff.exe`
- BinExport staged for IDA Pro, Binary Ninja, and Ghidra
- binja_sigmaker staged in Binary Ninja plugins

## Provenance requirement

Every final signature should keep:
- source binary/build
- module name
- relative offset or function anchor
- byte window / masking assumptions