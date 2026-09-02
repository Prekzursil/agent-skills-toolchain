"""Catalog load that refuses colliding ids instead of silently last-wins merging."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CatalogCollision(Exception):
    def __init__(self, collisions: list[dict[str, Any]]) -> None:
        self.collisions = collisions
        ids = ", ".join(sorted({str(c.get("id")) for c in collisions}))
        super().__init__(f"catalog collision at load: {ids}")


def _units(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw = data.get("work_units")
    if isinstance(raw, list):
        return [u for u in raw if isinstance(u, dict)]
    raw = data.get("items")
    if isinstance(raw, list):
        return [u for u in raw if isinstance(u, dict)]
    return []


def load_catalog_files(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Return id -> unit. Raise CatalogCollision if any id is owned twice."""
    owners: dict[str, tuple[str, dict[str, Any]]] = {}
    collisions: list[dict[str, Any]] = []
    for path in paths:
        rel = str(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError(f"catalog root is {type(data).__name__}, expected object")
        seen_in_file: set[str] = set()
        for unit in _units(data):
            uid = str(unit.get("id") or "")
            if not uid:
                continue
            if uid in seen_in_file:
                collisions.append(
                    {
                        "id": uid,
                        "catalogs": [rel, rel],
                        "meanings": [unit.get("title"), unit.get("title")],
                        "where": "intra-file",
                    }
                )
                continue
            seen_in_file.add(uid)
            if uid in owners:
                prev_path, prev_unit = owners[uid]
                collisions.append(
                    {
                        "id": uid,
                        "catalogs": [prev_path, rel],
                        "meanings": [prev_unit.get("title"), unit.get("title")],
                        "where": "cross-catalog",
                    }
                )
            else:
                owners[uid] = (rel, unit)
    if collisions:
        raise CatalogCollision(collisions)
    return {uid: unit for uid, (_p, unit) in owners.items()}


def silent_last_wins(paths: list[Path]) -> dict[str, dict[str, Any]]:
    """Negative control: dict last-wins, the silent merge this confirmation forbids."""
    merged: dict[str, dict[str, Any]] = {}
    for path in paths:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        for unit in _units(data):
            uid = str(unit.get("id") or "")
            if uid:
                merged[uid] = unit
    return merged


COLLIDING_ID = "CNF-0031-CONTENDED"


def run_collision_experiment(catalogs: dict[str, Path]) -> dict[str, Any]:
    colliding = [catalogs["a"], catalogs["b"]]
    disjoint = [catalogs["a"], catalogs["disjoint"]]
    collisions: list[dict[str, Any]] = []
    refused = False
    try:
        load_catalog_files(colliding)
    except CatalogCollision as exc:
        refused = True
        collisions = exc.collisions
    merged_ok = load_catalog_files(disjoint)
    silent = silent_last_wins(colliding)
    silent_one = COLLIDING_ID in silent
    return {
        "colliding_id": COLLIDING_ID,
        "collisions": collisions,
        "detected_at_load": refused,
        "disjoint_merge_count": len(merged_ok),
        "kept_both_would_be": 2,
        "refused": refused,
        "silent_merge_ids": sorted(silent),
        "silent_merge_total_ids": len(silent),
        "silent_merge_would_yield_one_unit": silent_one,
    }
