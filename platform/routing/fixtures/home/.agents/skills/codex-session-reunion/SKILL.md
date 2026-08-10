---
name: codex-session-reunion
description: Use when Codex sessions or rollout JSONL files are spread across Windows, WSL, backups, or VS Code mirrors and need to be inventoried, deduped, and promoted into one canonical store safely.
---

# Codex Session Reunion

## Overview

Reunite split session histories without blindly overwriting the current store. Inventory every reachable root, compare duplicates, score completeness, and only then promote the best non-corrupt copy into the canonical tree.

## Reference Map

- Read [references/canonicalization-rules.md](references/canonicalization-rules.md) for ranking, stop rules, and archive policy.
- Read [references/promotion-workflow.md](references/promotion-workflow.md) for the evidence-first promotion sequence.
- Run [scripts/session_inventory.py](scripts/session_inventory.py) to build a read-only inventory before any copy or move.

## Required Discovery

1. Enumerate all candidate roots, including Windows, WSL, backup, and `.codex-vscode*` stores.
2. Decide which root should remain the canonical destination.
3. Group duplicate files by rollout filename before comparing size, parse health, and line count.
4. Prove a file is corrupt before discarding it.

## Promotion Workflow

1. Inventory every root and save the report.
2. Group duplicates and rank them.
3. Archive any replaced target copy instead of deleting it.
4. Promote only when the winning copy is parseable and more complete than the current target.
5. Recount the canonical tree after promotion.

## Stop Rules

- Do not merge stores while an active writer is still pointed at a mirror.
- Do not replace a current target with a shorter or unparseable copy.
- Do not trust mtimes alone.
- Stop if two copies differ semantically and neither clearly dominates.

### Output Contract
### Common Mistakes
