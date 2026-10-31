"""Local 96-entry blueprint registry with a computed flagship tier."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
REGISTRY_REL = "command-center/lib/flagship_e2e_contract/registry.json"


def load_registry(path: Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else REPO / REGISTRY_REL
    return json.loads(target.read_text(encoding="utf-8"))


def all_ids(doc: dict[str, Any]) -> list[str]:
    return [str(row.get("id")) for row in (doc.get("entries") or []) if isinstance(row, dict)]


def flagship_ids(doc: dict[str, Any]) -> list[str]:
    return [
        str(row.get("id"))
        for row in (doc.get("entries") or [])
        if isinstance(row, dict) and row.get("tier") == "flagship"
    ]


def compute_flagship_count(doc: dict[str, Any]) -> int:
    return len(flagship_ids(doc))


def plant_extra_flagship(doc: dict[str, Any]) -> dict[str, Any]:
    planted = copy.deepcopy(doc)
    entries = list(planted.get("entries") or [])
    entries.append({"id": "planted-extra-flagship", "tier": "flagship"})
    planted["entries"] = entries
    planted["library_size"] = len(entries)
    return planted


def plant_missing_flagship(doc: dict[str, Any]) -> dict[str, Any]:
    planted = copy.deepcopy(doc)
    entries = []
    demoted = False
    for row in planted.get("entries") or []:
        if not demoted and isinstance(row, dict) and row.get("tier") == "flagship":
            row = dict(row)
            row["tier"] = "supporting"
            demoted = True
        entries.append(row)
    planted["entries"] = entries
    planted["library_size"] = len(entries)
    return planted
