"""Independent CONFIRMED-missing-source census (JSON field walk, not gate evaluate).

Probe 2 must not re-run claim_gate.evaluate. This walker only inspects
whether a CONFIRMED row declares a non-empty source_probe.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

AXES = ("tool", "engine", "shell", "field")


def _text(value: Any) -> str:
    return str(value or "").strip()


def declared(probe: Any) -> bool:
    if probe is None:
        return False
    if isinstance(probe, str):
        return bool(probe.strip())
    if isinstance(probe, dict):
        return any(_text(probe.get(k)) for k in AXES)
    return bool(str(probe).strip())


def gate_shaped(probe: Any) -> bool:
    """True only when source_probe is a dict with at least one discriminating axis.

    Live claim_gate._probe_key treats a string or None as four empty strings, so a
    prose source is undeclared *to the gate* even when the JSON field is nonempty.
    """
    if not isinstance(probe, dict):
        return False
    return any(_text(probe.get(k)) for k in AXES)


def walk(doc: Any) -> dict[str, Any]:
    if isinstance(doc, dict):
        claims = doc.get("claims") or []
    elif isinstance(doc, list):
        claims = doc
    else:
        claims = []
    confirmed = 0
    missing = []
    complete = []
    missing_shaped = []
    shaped = []
    refuted = 0
    refuted_missing = []
    for item in claims:
        if not isinstance(item, dict):
            continue
        verdict = _text(item.get("verdict")).upper()
        cid = _text(item.get("id")) or "?"
        if verdict == "REFUTED":
            refuted += 1
            if not declared(item.get("source_probe")):
                refuted_missing.append(cid)
            continue
        if verdict != "CONFIRMED":
            continue
        confirmed += 1
        src = item.get("source_probe")
        if declared(src):
            complete.append(cid)
        else:
            missing.append(cid)
        if gate_shaped(src):
            shaped.append(cid)
        else:
            missing_shaped.append(cid)
    return {
        "confirmed_total": confirmed,
        "confirmed_missing_source_probe": len(missing),
        "confirmed_missing_ids": missing,
        "confirmed_with_source_ids": complete,
        "confirmed_gate_shaped_ids": shaped,
        "confirmed_missing_gate_shaped": len(missing_shaped),
        "confirmed_missing_gate_shaped_ids": missing_shaped,
        "refuted_total": refuted,
        "refuted_missing_source_probe": len(refuted_missing),
        "refuted_missing_ids": refuted_missing,
        "empty_set_not_a_pass": confirmed == 0,
        "instrument": "json-field-walk",
    }


_ABSENT = {
    "confirmed_total": 0,
    "confirmed_missing_source_probe": 0,
    "confirmed_missing_ids": [],
    "confirmed_with_source_ids": [],
    "confirmed_gate_shaped_ids": [],
    "confirmed_missing_gate_shaped": 0,
    "confirmed_missing_gate_shaped_ids": [],
    "refuted_total": 0,
    "refuted_missing_source_probe": 0,
    "refuted_missing_ids": [],
    "empty_set_not_a_pass": True,
    "instrument": "json-field-walk",
}


def walk_path(path: Path) -> dict[str, Any]:
    row = {
        "path": str(path).replace("\\", "/"),
        "present": path.is_file(),
        "parseable": False,
        "note": "",
    }
    if not path.is_file():
        row.update(_ABSENT)
        row["note"] = "file absent; 0-of-0 is an empty measurement, not a pass"
        return row
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        row.update(_ABSENT)
        row["note"] = f"unparseable:{type(exc).__name__}"
        return row
    row["parseable"] = True
    row.update(walk(doc))
    return row
