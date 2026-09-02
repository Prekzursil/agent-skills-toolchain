#!/usr/bin/env python3
"""Live inventory of confirmation records, CNF-0137 frame, UNKNOWNS-REGISTER."""
from __future__ import annotations

import json
from pathlib import Path

VERDICTS = frozenset({"CONFIRMED", "REFUTED", "PARTIAL", "NOT-CHECKED", "BLOCKED"})


def _looks_like_confirmation_record(doc: object) -> bool:
    if not isinstance(doc, dict):
        return False
    cid = doc.get("claim_id")
    verdict = doc.get("verdict")
    if not isinstance(cid, str) or not cid.strip():
        return False
    if verdict not in VERDICTS:
        return False
    if doc.get("unit_id") and str(doc.get("sentinel") or "").startswith("SUCCESS:"):
        return False
    has_probe = isinstance(doc.get("source_probe"), str) and bool(doc.get("source_probe"))
    confirmer = doc.get("confirmer")
    has_confirmer = isinstance(confirmer, (dict, str)) and bool(confirmer)
    return has_probe or has_confirmer


def harvest(repo: Path) -> dict:
    frame_path = repo / "command-center/receipts/CNF-0137.json"
    unknowns = repo / "command-center/UNKNOWNS-REGISTER.md"
    claim_registry = repo / "command-center/CLAIM-REGISTRY.json"
    search_dirs = [
        repo / "command-center/receipts/confirmations",
        repo / "command-center/confirmation-records",
        repo / "command-center/confirmations",
    ]
    records: list[dict] = []
    scanned_files = 0
    for d in search_dirs:
        if not d.is_dir():
            continue
        for path in sorted(d.glob("*.json")):
            scanned_files += 1
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                continue
            if _looks_like_confirmation_record(doc):
                rec = dict(doc)
                rec["_path"] = path.relative_to(repo).as_posix()
                records.append(rec)

    frame = None
    frame_present = frame_path.is_file() and frame_path.stat().st_size > 0
    if frame_present:
        try:
            frame_doc = json.loads(frame_path.read_text(encoding="utf-8"))
            if isinstance(frame_doc, dict) and (
                isinstance(frame_doc.get("claims"), list)
                or isinstance((frame_doc.get("frame") or {}).get("claims"), list)
            ):
                frame = frame_doc.get("frame") if isinstance(frame_doc.get("frame"), dict) else frame_doc
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            frame_present = False
            frame = None

    blocked = [r for r in records if r.get("verdict") == "BLOCKED"]
    not_checked = [r for r in records if r.get("verdict") == "NOT-CHECKED"]
    return {
        "cnf_0137_present": bool(frame_present and frame is not None),
        "cnf_0137_path": "command-center/receipts/CNF-0137.json",
        "claim_registry_present": claim_registry.is_file(),
        "unknowns_register_present": unknowns.is_file(),
        "unknowns_register_path": "command-center/UNKNOWNS-REGISTER.md",
        "search_dirs": [p.relative_to(repo).as_posix() for p in search_dirs],
        "scanned_files": scanned_files,
        "record_count": len(records),
        "blocked_count": len(blocked),
        "not_checked_count": len(not_checked),
        "records": records,
        "frame": frame,
        "note": (
            "Live confirmation corpus is harvested only from confirmation-record "
            "directories (claim_id + verdict + source_probe/confirmer). Unit "
            "receipts and architecture reviews are not confirmation records."
        ),
    }
