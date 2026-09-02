"""Bind CNF-0126 to catalog unit row and owner questions OQ-3 / OQ-9."""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
UID = "CNF-0126"


def load_catalog() -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("FAILED:CNF-0126 catalog is not an object")
    return data


def catalog_unit(data: dict | None = None) -> dict:
    data = data if data is not None else load_catalog()
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UID:
            return u
    raise SystemExit("FAILED:CNF-0126 catalog unit missing")


def owner_question(oid: str, data: dict | None = None) -> dict:
    data = data if data is not None else load_catalog()
    for q in data.get("owner_questions") or []:
        if isinstance(q, dict) and q.get("id") == oid:
            return q
    raise SystemExit(f"FAILED:CNF-0126 owner_question {oid} missing")


def release_mode_from_oq3(q: dict | None = None) -> dict:
    q = q if q is not None else owner_question("OQ-3")
    answer = str(q.get("answer") or "").strip()
    mode = "UNKNOWN"
    if answer.upper().startswith("PR-ONLY") or answer.upper() == "PR-ONLY.":
        mode = "PR-ONLY"
    elif "PRIVATE CANARY" in answer.upper() or "PRIVATE-CANARY" in answer.upper():
        mode = "PRIVATE-CANARY"
    elif "MARKETPLACE" in answer.upper():
        mode = "PUBLIC-MARKETPLACE"
    return {
        "id": "OQ-3",
        "state": str(q.get("state") or ""),
        "answer": answer,
        "answer_detail": str(q.get("answer_detail") or ""),
        "answered_on": str(q.get("answered_on") or ""),
        "answer_provenance": str(q.get("answer_provenance") or ""),
        "release_mode": mode,
        "receipt_path": "command-center/WORK-UNIT-CATALOG.json",
        "receipt_field": "owner_questions[id=OQ-3]",
    }


def oq9_substitute(q: dict | None = None) -> dict:
    q = q if q is not None else owner_question("OQ-9")
    return {
        "id": "OQ-9",
        "state": str(q.get("state") or ""),
        "text": str(q.get("text") or ""),
        "answer": str(q.get("answer") or ""),
        "answer_detail": str(q.get("answer_detail") or ""),
        "answered_on": str(q.get("answered_on") or ""),
        "answer_provenance": str(q.get("answer_provenance") or ""),
        "receipt_path": "command-center/WORK-UNIT-CATALOG.json",
        "receipt_field": "owner_questions[id=OQ-9]",
    }
