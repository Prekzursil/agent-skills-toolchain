---
name: bindiff
description: Use when comparing two related binaries or database exports to identify
  changed functions, patch deltas, or version-to-version differences in native reverse-engineering
  workflows.
permalink: dqverify-repo-20261013/skills/bindiff/skill
---

# BinDiff

## Overview

Use BinDiff after both sides are exported cleanly. BinDiff is the comparison engine; it is not the exporter. Always produce BinExport artifacts from both binaries first.

## Quick Workflow

1. Export both analysis databases with `$binexport`.
2. Confirm you are comparing like-for-like builds (same architecture, similar loader assumptions, clean imports if possible).
3. Run `bindiff` on the two exports.
4. Review the changed and unmatched functions first; capture stable function identities and offsets.
5. Feed the highest-value deltas back into signature work, decompiler cleanup, or gameplay/runtime investigation.

## Common Mistakes

- Running BinDiff before producing clean exports from both sides.
- Comparing mismatched loader states or heavily broken imports without noting the distortion.
- Treating every unmatched function as meaningful without checking export quality first.

## Reference Map

Read `references/upstream.md` for the local install location and the companion BinExport workflow.