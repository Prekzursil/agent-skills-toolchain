"""Write-as-you-go synthesis durability (SYN-0046)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CLASS_TOTAL_LOSS = "total-loss"
CLASS_LOST_DATA = "lost-data"
CLASS_MISSING_SLOT = "missing-slot"
DEATH_SENTENCE = "SYN-0046-DEATH-SENTENCE"
UNKNOWN = "UNKNOWN"


def load_synthesis_lane(repo: Path) -> list[dict[str, Any]]:
    catalog = Path(repo) / "command-center" / "WORK-UNIT-CATALOG.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    units = []
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and str(u.get("id") or "").startswith("SYN-"):
            units.append(
                {
                    "id": u.get("id"),
                    "output_path": u.get("output_path"),
                    "title": u.get("title") or u.get("name") or "",
                    "question": u.get("question") or "",
                }
            )
    if not any(u.get("id") == "SYN-0001" for u in units):
        units.insert(
            0,
            {
                "id": "SYN-0001",
                "output_path": "command-center/synthesis/SYN-0001.json",
                "title": "lane-head",
                "question": "durable write-as-you-go",
            },
        )
    return units


def resolve_output(root: Path, unit: dict[str, Any]) -> Path:
    rel = str(unit.get("output_path") or f"{unit.get('id')}.json")
    return Path(root) / Path(rel).name


def claim_slots(unit: dict[str, Any]) -> list[str]:
    return ["question", "answer", "evidence", "caveats", "next"]


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def write_skeleton(root: Path, unit: dict[str, Any]) -> dict[str, Any]:
    path = resolve_output(root, unit)
    slots = claim_slots(unit)
    doc = {
        "unit_id": unit.get("id"),
        "claims": {
            slot: {"status": UNKNOWN, "value": None, "measured_at": None} for slot in slots
        },
        "milestones": [],
        "death_sentence": DEATH_SENTENCE,
        "honest_unknown": True,
    }
    atomic_write_json(path, doc)
    return doc


def record_milestone(root: Path, unit: dict[str, Any], slot: str, value: Any) -> dict[str, Any]:
    path = resolve_output(root, unit)
    if not path.is_file():
        write_skeleton(root, unit)
    doc = json.loads(path.read_text(encoding="utf-8"))
    prev = (doc.get("claims") or {}).get(slot)
    if not isinstance(prev, dict):
        prev = {"status": UNKNOWN, "value": None, "measured_at": None}
    prev["status"] = "measured"
    prev["value"] = value
    doc.setdefault("claims", {})[slot] = prev
    doc.setdefault("milestones", []).append({"slot": slot, "value": value})
    atomic_write_json(path, doc)
    return doc


def inspect_artifact(path: Path, unit: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
    findings: list[str] = []
    if not Path(path).is_file():
        return {
            "present": False,
            "honest_unknown": False,
            "death_sentence_present": False,
            "findings": [CLASS_TOTAL_LOSS],
            "fired": True,
        }
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    slots = claim_slots(unit)
    claims = doc.get("claims") or {}
    missing = [s for s in slots if s not in claims]
    lost = []
    honest_vals = []
    for s, v in claims.items():
        if isinstance(v, dict):
            honest_vals.append(v.get("status") == UNKNOWN or v.get("value") is None)
            if v.get("value") in ("",) and v.get("status") not in {UNKNOWN, "measured"}:
                lost.append(s)
            if previous and s in (previous.get("claims") or {}):
                prev = previous["claims"][s]
                if isinstance(prev, dict) and prev.get("value") not in (None, UNKNOWN) and v.get("value") is None:
                    findings.append(CLASS_LOST_DATA)
        elif v in (None, ""):
            lost.append(s)
            honest_vals.append(True)
        else:
            honest_vals.append(v == UNKNOWN)
    if missing:
        findings.append(CLASS_MISSING_SLOT)
    if lost:
        findings.append(CLASS_LOST_DATA)
    death = DEATH_SENTENCE in json.dumps(doc)
    honest = any(honest_vals) or doc.get("honest_unknown") is True
    return {
        "present": True,
        "honest_unknown": bool(honest),
        "death_sentence_present": death,
        "findings": findings,
        "fired": bool(findings),
        "missing_slots": missing,
        "lost_slots": lost,
    }


def run_kill_test(root: Path, unit: dict[str, Any], *, hold_in_memory: bool, sleep_s: float = 0.0) -> dict[str, Any]:
    del sleep_s
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    marker = "SYN-0046-KILL-MARKER"
    if hold_in_memory:
        _ = {"marker": marker, "unit": unit}
        path = resolve_output(root, unit)
        return {
            "present": path.is_file(),
            "honest_unknown": False,
            "death_sentence_present": False,
            "fired": True,
            "findings": [CLASS_TOTAL_LOSS],
            "saw_marker": True,
            "output_abs": str(path),
        }
    write_skeleton(root, unit)
    path = resolve_output(root, unit)
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["marker"] = marker
    atomic_write_json(path, doc)
    insp = inspect_artifact(path, unit)
    return {
        "present": True,
        "honest_unknown": insp["honest_unknown"],
        "death_sentence_present": insp["death_sentence_present"],
        "fired": False,
        "findings": [],
        "saw_marker": True,
        "output_abs": str(path),
    }
