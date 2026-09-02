"""Load a work-unit's actual target text and catalog line number."""
from __future__ import annotations

import json
from pathlib import Path

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def catalog_path(repo: Path) -> Path:
    return repo / CATALOG_REL


def load_units(repo: Path) -> dict[str, dict]:
    data = json.loads(catalog_path(repo).read_text(encoding="utf-8"))
    return {u["id"]: u for u in data["work_units"]}


def unit_target_line(repo: Path, unit_id: str) -> int:
    in_unit = False
    for i, line in enumerate(catalog_path(repo).read_text(encoding="utf-8").splitlines(), 1):
        if f'"id": "{unit_id}"' in line:
            in_unit = True
            continue
        if in_unit and '"id":' in line and unit_id not in line:
            break
        if in_unit and '"question_or_target"' in line:
            return i
    raise KeyError(f"question_or_target line not found for {unit_id}")


def unit_view(repo: Path, unit_id: str) -> dict:
    units = load_units(repo)
    if unit_id not in units:
        raise KeyError(f"catalog missing unit {unit_id}")
    u = units[unit_id]
    target = str(u.get("question_or_target") or "")
    if not target:
        raise ValueError(f"{unit_id} has empty question_or_target")
    line = unit_target_line(repo, unit_id)
    return {
        "id": unit_id,
        "title": str(u.get("title") or ""),
        "target": target,
        "anchor": f"{CATALOG_REL}:{line}",
        "line": line,
    }
