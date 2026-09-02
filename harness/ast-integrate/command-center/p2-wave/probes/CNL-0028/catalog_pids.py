"""Independent P-id extraction from the work-unit catalog (not from protocols.json)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FAMILY_UNITS = tuple(f"CNL-{n:04d}" for n in range(38, 47))
PID_RE = re.compile(r"\bP(\d{2})\b")


def catalog_protocol_ids() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    found: list[str] = []
    per_unit: dict[str, list[str]] = {}
    for unit in data.get("work_units") or []:
        uid = str(unit.get("id") or "")
        if uid not in FAMILY_UNITS:
            continue
        question = str(unit.get("question_or_target") or "")
        ids = [f"P{m}" for m in PID_RE.findall(question)]
        per_unit[uid] = ids
        found.extend(ids)
    unique = sorted(set(found), key=lambda x: int(x[1:]))
    return {
        "units": list(FAMILY_UNITS),
        "per_unit": per_unit,
        "ids": unique,
        "n": len(unique),
        "raw_n": len(found),
    }
