#!/usr/bin/env python3
"""Catalog-cited corpus names. These are NOT live hashes.

Computed by regex over WORK-UNIT-CATALOG.json path strings that include
harness-restore-20260806 or platform-redesign-2026-07-19. Distinct from
R-A26's inherited 9/28 vs 17/28 live-scan counts, which this host cannot
recompute.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"

PATH_RE = re.compile(
    r"(harness-restore-20260806|platform-redesign-2026-07-19)"
    r"[/\\]([A-Za-z0-9._-]+\.(?:md|json|schema\.json))",
    re.I,
)


def catalog_cited_names() -> dict[str, Any]:
    text = CATALOG.read_text(encoding="utf-8")
    harness: set[str] = set()
    platform: set[str] = set()
    for tree, name in PATH_RE.findall(text):
        if "harness-restore" in tree:
            harness.add(name)
        else:
            platform.add(name)
    inherited = _r_a26_inherited(text)
    return {
        "source": "command-center/WORK-UNIT-CATALOG.json",
        "verdict": "NOT-CHECKED",
        "note": (
            "Basenames cited on catalog paths that name one of the two trees. "
            "Not a directory listing and not content hashes. Live membership "
            "on this host is empty until the trees are mounted."
        ),
        "harness_restore_cited": sorted(harness),
        "platform_redesign_cited": sorted(platform),
        "union_cited": sorted(harness | platform),
        "only_cited_in_harness": sorted(harness - platform),
        "only_cited_in_platform": sorted(platform - harness),
        "cited_in_both_paths": sorted(harness & platform),
        "counts": {
            "harness": len(harness),
            "platform": len(platform),
            "union": len(harness | platform),
        },
        "inherited_r_a26": inherited,
    }


def _r_a26_inherited(text: str) -> dict[str, Any]:
    """Pull R-A26's inherited live-scan claim without treating it as hashed."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {}
    unit = None
    for row in data.get("work_units") or []:
        if isinstance(row, dict) and row.get("id") == "R-A26":
            unit = row
            break
    if unit is None:
        return {"present": False}
    return {
        "present": True,
        "verdict": "NOT-CHECKED",
        "title": unit.get("title"),
        "evidence": unit.get("evidence"),
        "note": (
            "Inherited R-A26 live-scan (9/28 vs 17/28). This unit does not "
            "re-assert those counts as hashed fact on this host."
        ),
    }
