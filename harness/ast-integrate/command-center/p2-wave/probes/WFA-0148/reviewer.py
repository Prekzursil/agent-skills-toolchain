#!/usr/bin/env python3
"""Independent recount + plant replay (no Counter import from registry)."""
from __future__ import annotations

from typing import Any

from classifier import UNUSED_DECLARED, VOCABULARY, classify
from plants import plant_for


def recount_array_manual(candidates: list[Any]) -> dict[str, int]:
    hist = {k: 0 for k in VOCABULARY}
    for row in candidates:
        if not isinstance(row, dict):
            continue
        label = str(row.get("classification") or "")
        if label in hist:
            hist[label] = hist[label] + 1
    return hist


def replay_plants() -> list[dict[str, Any]]:
    rows = []
    for value in UNUSED_DECLARED:
        rec = plant_for(value)
        emitted = str(classify(rec)["classification"])
        rows.append(
            {
                "value": value,
                "emitted": emitted,
                "reachable": emitted == value,
                "reachable": emitted == value,
            }
        )
    return rows
