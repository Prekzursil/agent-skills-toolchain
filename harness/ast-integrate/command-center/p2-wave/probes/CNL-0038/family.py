"""Load and count the DELIBERATIVE family without trusting the author note."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
SLICE = HERE / "fixtures" / "family-slice.json"
LIBRARY_CANDIDATES = [
    Path("C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"),
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "design" / "council" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
]
NAMED_RE = re.compile(r"(P\d{2})\s+([a-z0-9-]+)")
FAMILY = "DELIBERATIVE"
UNIT_ID = "CNL-0038"


def catalog_unit() -> dict[str, Any]:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for item in data.get("work_units") or []:
        if isinstance(item, dict) and item.get("id") == UNIT_ID:
            return item
    raise RuntimeError("catalog-missing-CNL-0038")


def catalog_named_members() -> list[tuple[str, str]]:
    unit = catalog_unit()
    question = str(unit.get("question_or_target") or "")
    m = re.search(r"\((P01\s+[^)]+)\)", question)
    if not m:
        raise RuntimeError("catalog-named-list-absent")
    found = NAMED_RE.findall(m.group(1))
    if len(found) != 6:
        raise RuntimeError(f"catalog-named-count:{len(found)}")
    return [(pid, slug) for pid, slug in found]


def catalog_expected_n() -> int:
    unit = catalog_unit()
    ev = str(unit.get("evidence_requirement") or "")
    m = re.search(r"expected n=(\d+)", ev)
    if not m:
        raise RuntimeError("catalog-expected-n-absent")
    return int(m.group(1))


def library_on_disk() -> Path | None:
    for path in LIBRARY_CANDIDATES:
        if path.is_file():
            return path
    return None


def load_slice() -> dict[str, Any]:
    lib = library_on_disk()
    if lib is not None:
        return json.loads(lib.read_text(encoding="utf-8"))
    return json.loads(SLICE.read_text(encoding="utf-8"))


def all_protocol_records(doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    data = doc if doc is not None else load_slice()
    if isinstance(data.get("protocols"), list):
        recs = data["protocols"]
    elif isinstance(data.get("records"), list):
        recs = data["records"]
    else:
        recs = []
    return [r for r in recs if isinstance(r, dict) and r.get("id")]


def deliberative_records(doc: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    recs = [
        r
        for r in all_protocol_records(doc)
        if str(r.get("family") or "").upper() == FAMILY
    ]
    recs.sort(key=lambda r: str(r.get("id")))
    return recs


def enumeration() -> dict[str, Any]:
    named = catalog_named_members()
    expected = catalog_expected_n()
    lib = library_on_disk()
    recs = deliberative_records()
    ids = [str(r["id"]) for r in recs]
    named_ids = [p for p, _ in named]
    return {
        "family": FAMILY,
        "library_path": None if lib is None else str(lib),
        "library_present": lib is not None,
        "slice_path": str(SLICE.relative_to(REPO).as_posix()),
        "catalog_expected_n": expected,
        "catalog_named_n": len(named),
        "catalog_named": [{"id": i, "slug": s} for i, s in named],
        "slice_family_n": len(recs),
        "slice_family_ids": ids,
        "decoy_excluded": [
            str(r["id"])
            for r in all_protocol_records()
            if str(r.get("family") or "").upper() != FAMILY
        ],
        "ids_match_catalog": ids == named_ids,
        "counts_agree": (
            expected == len(named) == len(recs) == 6 and ids == named_ids
        ),
    }
