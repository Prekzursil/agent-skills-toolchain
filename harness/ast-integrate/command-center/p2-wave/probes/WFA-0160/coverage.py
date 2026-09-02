"""Mechanical spec-set difference: enumerated source classes vs searched.

A class is searched only when the catalog sweep unit's output_path exists on
this worktree, is non-empty, and parses as JSON. Probe directories and
fixtures are not search evidence. Missing Windows restore files are absence,
not a silent pass.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from spec_classes import SPEC_SOURCE_CLASSES, by_sweep_unit

CATALOG_REL = "command-center/WORK-UNIT-CATALOG.json"


def load_catalog_units(repo: Path) -> dict[str, dict[str, Any]]:
    path = repo / CATALOG_REL
    doc = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, Any]] = {}
    for unit in doc.get("work_units") or []:
        if isinstance(unit, dict) and unit.get("id"):
            out[str(unit["id"])] = unit
    return out


def artifact_status(repo: Path, rel: str) -> dict[str, Any]:
    if not rel:
        return {
            "path": rel,
            "present": False,
            "bytes": 0,
            "parses": False,
            "searched": False,
            "reason": "no-output-path",
        }
    path = repo / rel.replace("\\", "/")
    present = path.is_file()
    size = int(path.stat().st_size) if present else 0
    parses = False
    if present and size > 0:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            parses = True
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            parses = False
    searched = present and size > 0 and parses
    reason = "searched" if searched else (
        "absent" if not present else ("empty" if size <= 0 else "unparseable")
    )
    return {
        "path": rel.replace("\\", "/"),
        "present": present,
        "bytes": size,
        "parses": parses,
        "searched": searched,
        "reason": reason,
    }


def class_coverage(repo: Path) -> dict[str, Any]:
    units = load_catalog_units(repo)
    sweep_map = by_sweep_unit()
    rows = []
    searched: list[str] = []
    never: list[str] = []
    for spec in SPEC_SOURCE_CLASSES:
        uid = spec["sweep_unit"]
        unit = units.get(uid) or {}
        out_rel = str(unit.get("output_path") or "").replace("\\", "/")
        st = artifact_status(repo, out_rel)
        row = {
            "source_class": spec["id"],
            "sweep_unit": uid,
            "spec_anchor": spec["spec_anchor"],
            "catalog_title_fragment": spec["catalog_title_fragment"],
            "catalog_unit_present": bool(unit),
            **st,
        }
        rows.append(row)
        if st["searched"]:
            searched.append(spec["id"])
        else:
            never.append(spec["id"])
    spec_ids = [s["id"] for s in SPEC_SOURCE_CLASSES]
    # Mechanical set difference, not an eyeball count.
    never_set = sorted(set(spec_ids) - set(searched))
    extra = sorted(set(searched) - set(spec_ids))
    return {
        "enumerated": spec_ids,
        "enumerated_n": len(spec_ids),
        "searched": searched,
        "searched_n": len(searched),
        "never_searched": never_set,
        "never_searched_n": len(never_set),
        "extra_non_enumerated": extra,
        "rows": rows,
        "sweep_units_in_spec": sorted(sweep_map),
        "catalog_rel": CATALOG_REL,
        "rule": (
            "searched := catalog output_path exists AND size>0 AND json.loads; "
            "never_searched := enumerated \\ searched"
        ),
    }
