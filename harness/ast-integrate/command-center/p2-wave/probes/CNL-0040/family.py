"""Independent JUDICIAL family enumeration for CNL-0040.

Two mechanisms:
  1. Regex over WORK-UNIT-CATALOG.json CNL-0040.question_or_target
  2. JSON load of fixtures/ranging_set.json
Optional third: if 12-COUNCIL-PROTOCOLS-AND-PRESETS.json appears on disk,
count records with family=JUDICIAL.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
RANGING = HERE / "fixtures" / "ranging_set.json"
UNIT_ID = "CNL-0040"
EXPECTED_N = 6
MEMBER_RE = re.compile(r"(P\d{2})\s+([a-z0-9-]+)")
LIBRARY_CANDIDATES = [
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "design" / "council" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]


def catalog_unit(uid: str = UNIT_ID) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def parse_named_ranging(question: str) -> list[dict]:
    start = question.find("(")
    end = question.find(")", start + 1) if start >= 0 else -1
    if start < 0 or end < 0:
        raise ValueError("named ranging parenthetical missing")
    blob = question[start + 1 : end]
    members = [{"id": m.group(1), "slug": m.group(2)} for m in MEMBER_RE.finditer(blob)]
    if not members:
        raise ValueError("no P-ids in named ranging parenthetical")
    return members


def ranging_from_catalog() -> dict:
    unit = catalog_unit()
    members = parse_named_ranging(str(unit.get("question_or_target") or ""))
    return {
        "mechanism": "catalog-question-regex",
        "family": "JUDICIAL",
        "expected_n": EXPECTED_N,
        "n": len(members),
        "ids": [m["id"] for m in members],
        "members": members,
        "question": unit.get("question_or_target"),
        "output_path": unit.get("output_path"),
        "sentinel": unit.get("completion_sentinel"),
    }


def ranging_from_fixture() -> dict:
    doc = json.loads(RANGING.read_text(encoding="utf-8"))
    members = list(doc.get("members") or [])
    ids = [str(m["id"]) for m in members]
    return {
        "mechanism": "ranging-set-json",
        "family": str(doc.get("family") or ""),
        "expected_n": int(doc.get("expected_n") or 0),
        "n": len(ids),
        "ids": ids,
        "members": members,
        "library_on_this_tree": bool(
            ((doc.get("source") or {}).get("library_on_this_tree"))
        ),
    }


def library_path() -> Path | None:
    for p in LIBRARY_CANDIDATES:
        if p.is_file() and p.stat().st_size > 0:
            return p
    return None


def _records(doc) -> list:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("protocols", "records", "items", "protocol_records"):
        val = doc.get(key)
        if isinstance(val, list):
            return [x for x in val if isinstance(x, dict)]
    return []


def ranging_from_library() -> dict | None:
    path = library_path()
    if path is None:
        return {
            "mechanism": "library-file",
            "present": False,
            "n": None,
            "ids": [],
            "path": None,
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    recs = _records(doc)
    judicial = []
    for r in recs:
        fam = str(r.get("family") or r.get("Family") or "").upper()
        pid = str(r.get("id") or r.get("protocol_id") or r.get("pid") or "")
        if fam == "JUDICIAL" and pid:
            judicial.append(pid)
    return {
        "mechanism": "library-file",
        "present": True,
        "path": str(path.relative_to(REPO)).replace("\\", "/"),
        "n": len(judicial),
        "ids": judicial,
    }


def enumerate_family() -> dict:
    cat = ranging_from_catalog()
    fix = ranging_from_fixture()
    lib = ranging_from_library()
    ids_cat = list(cat["ids"])
    ids_fix = list(fix["ids"])
    match = ids_cat == ids_fix and cat["n"] == EXPECTED_N and fix["n"] == EXPECTED_N
    lib_ok = True
    if lib and lib.get("present"):
        lib_ok = sorted(lib["ids"]) == sorted(ids_cat) and lib["n"] == EXPECTED_N
        match = match and lib_ok
    return {
        "expected_n": EXPECTED_N,
        "family": "JUDICIAL",
        "catalog": cat,
        "fixture": fix,
        "library": lib,
        "ids": ids_cat,
        "match": match,
        "library_ok": lib_ok,
    }
