"""Load the live >=96 foundry catalog for WFA-0136.

The Prompt-One 09-WORKFLOW-BLUEPRINT-LIBRARY.json (cited as 108 records,
floor 96) is not on this worktree. The live catalog that carries title,
question, mechanism, and not_a_duplicate_because here is the WFA work-unit
slice of WORK-UNIT-CATALOG.json.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FLOOR = 96
CITED_LIBRARY = "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
CITED_COUNT = 108

LIBRARY_CANDIDATES = (
    "09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/wfa/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
    "command-center/foundry/09-WORKFLOW-BLUEPRINT-LIBRARY.json",
)


def library_presence(repo: Path) -> dict[str, Any]:
    rows = []
    for rel in LIBRARY_CANDIDATES:
        path = repo / rel
        rows.append(
            {
                "path": rel.replace("\\", "/"),
                "present": path.is_file(),
                "bytes": path.stat().st_size if path.is_file() else 0,
            }
        )
    fixture = (
        repo
        / "command-center/p2-wave/probes/WFA-0019/fixtures/corpus"
        / "09-WORKFLOW-BLUEPRINT-LIBRARY.json"
    )
    n_fix = 0
    if fixture.is_file():
        try:
            doc = json.loads(fixture.read_text(encoding="utf-8"))
            bps = doc.get("blueprints") if isinstance(doc, dict) else None
            n_fix = len(bps) if isinstance(bps, list) else 0
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            n_fix = -1
    return {
        "cited_library": CITED_LIBRARY,
        "cited_count": CITED_COUNT,
        "floor": FLOOR,
        "candidates": rows,
        "any_present": any(r["present"] for r in rows),
        "wfa0019_fixture": {
            "path": fixture.relative_to(repo).as_posix(),
            "present": fixture.is_file(),
            "n_blueprints": n_fix,
            "used_as_corpus": False,
            "why": "one-record sweep fixture, not the 108-entry library",
        },
    }


def prose_of(entry: dict) -> str:
    return " ".join(
        [
            str(entry.get("title") or ""),
            str(entry.get("question_or_target") or ""),
            str(entry.get("mechanism") or ""),
        ]
    )


def load_entries(repo: Path) -> list[dict]:
    catalog = repo / "command-center" / "WORK-UNIT-CATALOG.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    out: list[dict] = []
    for unit in data.get("work_units") or []:
        if not isinstance(unit, dict):
            continue
        uid = str(unit.get("id") or "")
        if not uid.startswith("WFA-"):
            continue
        out.append(
            {
                "id": uid,
                "title": str(unit.get("title") or ""),
                "mechanism": str(unit.get("mechanism") or ""),
                "question_or_target": str(unit.get("question_or_target") or ""),
                "not_a_duplicate_because": str(unit.get("not_a_duplicate_because") or ""),
                "output_path": str(unit.get("output_path") or ""),
                "source": "command-center/WORK-UNIT-CATALOG.json",
            }
        )
    out.sort(key=lambda row: row["id"])
    return out
