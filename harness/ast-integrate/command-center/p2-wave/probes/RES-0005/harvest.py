#!/usr/bin/env python3
"""Locate 05-ECO shards if present; otherwise record the catalog harvest rail."""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parents[4]

SHARD_NAMES = (
    "05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
    "05-ECO-workflow-sources.md",
    "05-ECO-frontier-orchestration.md",
    "05-ECO-plugin-specs.md",
    "05-ECO-marketplace-teardown.md",
)

SEARCH_ROOTS = (
    Path.home() / ".claude" / "harness-restore-20260806",
    Path.home() / ".claude" / "platform-redesign-2026-07-19",
    Path("/root/.claude/harness-restore-20260806"),
    Path("/root/.claude/platform-redesign-2026-07-19"),
    REPO / "command-center" / "sources",
    REPO / "command-center" / "research" / "eco-shards",
)


def find_shards() -> dict[str, str]:
    found: dict[str, str] = {}
    for root in SEARCH_ROOTS:
        if not root.is_dir():
            continue
        for name in SHARD_NAMES:
            path = root / name
            if name in found:
                continue
            if path.is_file() and path.stat().st_size > 0:
                found[name] = str(path)
    return found


def harvest_rail() -> dict:
    found = find_shards()
    return {
        "shard_files_present": bool(found),
        "shards_found": found,
        "catalog_rail": "command-center/WORK-UNIT-CATALOG.json",
        "named_shard_citations": [
            "C:/Users/Prekzursil/.claude/harness-restore-20260806/05-ECOSYSTEM-AND-FRONTIER-RESEARCH.md",
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-workflow-sources.md",
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-plugin-specs.md",
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-marketplace-teardown.md",
            "C:/Users/Prekzursil/.claude/platform-redesign-2026-07-19/05-ECO-frontier-orchestration.md",
        ],
        "note": (
            "Original 05-ECO shard files are not on this Linux worktree. "
            "Pairs are harvested from catalog-cited 05-ECO disagreements; "
            "each pair names both source shards (or the index plus a content shard)."
        ),
    }
