---
name: binexport
description: Use when exporting IDA Pro, Binary Ninja, or Ghidra analysis into BinExport artifacts for BinDiff or portable cross-tool comparison workflows.
---

# BinExport

## Overview

Use BinExport whenever a comparison needs stable exported analysis data instead of raw UI state. The exporter belongs in the disassembler; the resulting artifact is what `$bindiff` should compare.

## Quick Workflow

1. Open the target binary in IDA Pro, Binary Ninja, or Ghidra.
2. Let auto-analysis settle enough that functions, imports, and code layout are usable.
3. Run the BinExport plugin or extension from that host tool.
4. Save the export artifact with a name that clearly identifies the build or variant.
5. Repeat for the comparison target, then hand both files to `$bindiff`.

## Common Mistakes

- Exporting before analysis or imports are stable.
- Reusing ambiguous output filenames and losing track of which build is which.
- Treating BinExport itself as the comparison tool.

## Reference Map

Read `references/upstream.md` for the local plugin staging paths across IDA Pro, Binary Ninja, and Ghidra.
