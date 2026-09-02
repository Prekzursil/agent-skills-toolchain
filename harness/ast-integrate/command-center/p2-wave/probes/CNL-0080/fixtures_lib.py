#!/usr/bin/env python3
"""Load on-disk fixtures. Expected outcomes are NOT stored; probes recompute."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
NAMES = [
    "fire-unanimity",
    "fire-timer",
    "silent-contested",
    "silent-round-11",
    "both-at-ceiling",
    "instant-unanimity-round-1",
]


def load_all() -> list[dict]:
    rows = []
    for name in NAMES:
        path = FIX / f"{name}.json"
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["_fixture_file"] = path.name
        rows.append(doc)
    return rows


def by_id(fid: str) -> dict:
    for row in load_all():
        if row["id"] == fid:
            return row
    raise KeyError(fid)
