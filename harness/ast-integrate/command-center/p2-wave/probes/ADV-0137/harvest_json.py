"""Harvest A: JSON object walk of work_units[].inputs."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from counting_rule import (
    UID,
    passages_from_inputs,
    sources_from_inputs,
)

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def load_catalog(repo: Path) -> dict:
    path = repo / CATALOG_REL
    return json.loads(path.read_text(encoding="utf-8"))


def harvest(repo: Path, catalog: dict | None = None) -> dict:
    doc = catalog if catalog is not None else load_catalog(repo)
    units = doc.get("work_units") or []
    unit_sources: dict[str, list[str]] = {}
    unit_passages: dict[str, list[str]] = {}
    deps: dict[str, list[str]] = {}
    hist: Counter[str] = Counter()
    prose_only: list[str] = []
    for u in units:
        if not isinstance(u, dict):
            continue
        uid = u.get("id")
        if not isinstance(uid, str) or not UID.match(uid):
            continue
        inputs = u.get("inputs") or []
        if not isinstance(inputs, list):
            inputs = []
        src = sources_from_inputs(inputs)
        pas = passages_from_inputs(inputs)
        unit_sources[uid] = sorted(src)
        unit_passages[uid] = sorted(pas)
        if not src:
            prose_only.append(uid)
        for s in src:
            hist[s] += 1
        dlist = u.get("dependencies") or []
        deps[uid] = [str(x) for x in dlist if isinstance(x, (str, int))]
    return {
        "n_units": len(unit_sources),
        "unit_sources": unit_sources,
        "unit_passages": unit_passages,
        "histogram": dict(hist),
        "prose_only": prose_only,
        "dependencies": deps,
        "family": "json-object-walk",
        "catalog_rel": CATALOG_REL,
    }
