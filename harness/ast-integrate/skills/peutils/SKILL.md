---
name: peutils
description: Use when inspecting or repairing PE-focused details in Binary Ninja, especially around Windows executable structure, imports, sections, and analysis convenience helpers.
---

# peutils

## Overview

Use peutils when Binary Ninja needs help with Windows PE structure details: imports, sections, addresses, or convenience helpers that make PE triage faster.

## Quick Workflow

1. Open the executable in Binary Ninja.
2. Use peutils when the question is specifically about PE structure or import-related analysis.
3. Stabilize imports and section understanding before exporting, diffing, or signature generation.
4. Capture any corrected addresses, names, or import insights in notes before switching tools.

## Common Mistakes

- Using peutils as a generic Binary Ninja replacement instead of a PE-focused helper.
- Comparing or exporting binaries before import and section understanding is stable enough.
- Forgetting that PE cleanup is often a prerequisite for better diffing results.

## Reference Map

Read `references/upstream.md` for the upstream repository and the local Binary Ninja plugin path.
