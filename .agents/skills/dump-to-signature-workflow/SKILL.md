---
name: dump-to-signature-workflow
description: Use when converting dump or debugger evidence into durable signatures, AOB patterns, or diffable artifacts, especially when findings must survive across builds or runtime sessions.
---

# Dump to Signature Workflow

## Overview

Use this skill after you already have a real address or code region from WinDbg, x64dbg, or Cheat Engine. The goal is to turn that fragile observation into something durable: a signature, a BinExport/BinDiff comparison anchor, or a module-relative pattern you can trust across builds.

## Workflow

1. Start from a confirmed address, code region, or function family from the dump/debugger side.
2. Normalize the evidence by recording module name, module base, relative offset, and surrounding bytes.
3. Open the matching binary in IDA Pro or Binary Ninja and verify the same region statically.
4. Export both sides with `$binexport` and compare with `$bindiff` if build drift matters.
5. Generate the final signature with `$binja-sigmaker` or a Cheat Engine AOB workflow, then annotate its provenance.

## Common Mistakes

- Skipping the module-relative normalization step and going straight from an absolute dump address to a signature.
- Generating a signature before checking whether the surrounding code changed in another build.
- Forgetting to write down which dump, build, or binary the signature came from.

## Reference Map

Read `references/pipeline.md` for the exact artifact chain and the local tool support already staged on this machine.
