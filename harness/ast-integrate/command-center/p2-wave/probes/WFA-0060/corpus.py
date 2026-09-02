#!/usr/bin/env python3
"""Load the WFA-0060 incidence corpus and optional WFA-0059 matrix."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIXTURE = HERE / "fixtures" / "incidence-matrix.json"
UPSTREAM_MATRIX = REPO / "command-center/wfa/WFA-0059-mechanism-extraction.json"


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def load_upstream_matrix() -> dict[str, Any]:
    rel = "command-center/wfa/WFA-0059-mechanism-extraction.json"
    if not UPSTREAM_MATRIX.is_file() or UPSTREAM_MATRIX.stat().st_size <= 0:
        return {
            "merged_mechanism_count": 0,
            "note": (
                "WFA-0059 extraction matrix is absent on this worktree. "
                "Ranking is over the WFA-0060 control corpus (planted echo "
                "cluster plus independent and single-source controls). This "
                "is not a ranking of the 284 candidates and 108 blueprints."
            ),
            "path": rel,
            "present": False,
        }
    try:
        doc = json.loads(UPSTREAM_MATRIX.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {
            "merged_mechanism_count": 0,
            "note": f"WFA-0059 present but unparseable: {type(exc).__name__}",
            "path": rel,
            "present": False,
        }
    extra: list[dict] = []
    if isinstance(doc, dict):
        for key in ("records", "mechanisms", "incidence"):
            val = doc.get(key)
            if isinstance(val, list):
                extra = [x for x in val if isinstance(x, dict) and x.get("incidences")]
                break
    return {
        "merged_mechanism_count": len(extra),
        "note": (
            f"merged {len(extra)} mechanism rows from WFA-0059"
            if extra
            else "WFA-0059 parsed but no incidence rows were merged"
        ),
        "path": rel,
        "present": True,
        "records": extra,
    }


def mechanisms() -> tuple[list[dict], dict[str, Any]]:
    fixture = load_fixture()
    rows = list(fixture.get("mechanisms") or [])
    upstream = load_upstream_matrix()
    seen = {str(m.get("mechanism_id")) for m in rows}
    for extra in upstream.get("records") or []:
        mid = str(extra.get("mechanism_id") or extra.get("id") or "")
        if mid and mid not in seen:
            rows.append(extra)
            seen.add(mid)
    return rows, upstream
