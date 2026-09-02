"""Enumerate ENGINEERING-REVIEW family members from fixtures and catalog."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FAMILY = "ENGINEERING-REVIEW"
EXPECTED_N = 7
NAMED_IDS = ("P45", "P46", "P47", "P48", "P49", "P50", "P51")
NAMED_SLUGS = {
    "P45": "scientific-peer-review",
    "P46": "architecture-review-board",
    "P47": "incident-war-room",
    "P48": "kill-the-company",
    "P49": "socratic-interrogation",
    "P50": "evidence-clerk-led",
    "P51": "timeboxed-spike-council",
}
CATALOGUE = HERE / "fixtures" / "catalogue.json"
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
LIBRARY_CANDIDATES = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_catalogue(path: Path | None = None) -> dict:
    return load_json(path or CATALOGUE)


def records_of(doc: dict) -> list[dict]:
    recs = doc.get("records") or []
    return [r for r in recs if isinstance(r, dict)]


def family_members(records: list[dict], family: str = FAMILY) -> list[dict]:
    return [r for r in records if r.get("family") == family]


def member_ids(members: list[dict]) -> list[str]:
    return [str(r.get("id") or "") for r in members]


def library_hits() -> dict[str, bool]:
    return {rel: (REPO / rel).is_file() for rel in LIBRARY_CANDIDATES}


def library_on_this_tree() -> bool:
    return any(library_hits().values())


def catalog_unit(uid: str = "CNL-0045") -> dict:
    data = load_json(CATALOG)
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def catalog_named_ids(unit: dict | None = None) -> list[str]:
    """Independent of the fixture: P-ids in CNL-0045 question_or_target."""
    u = unit if unit is not None else catalog_unit()
    q = str(u.get("question_or_target") or "")
    return re.findall(r"\b(P\d{2})\b", q)


def catalog_named_slugs(unit: dict | None = None) -> dict[str, str]:
    u = unit if unit is not None else catalog_unit()
    q = str(u.get("question_or_target") or "")
    found = re.findall(r"\b(P\d{2}) ([a-z0-9-]+)", q)
    return {pid: slug for pid, slug in found}


def catalog_expected_n(unit: dict | None = None) -> int:
    u = unit if unit is not None else catalog_unit()
    ev = str(u.get("evidence_requirement") or "")
    m = re.search(r"expected n=(\d+)", ev)
    if not m:
        raise ValueError("expected n= missing from evidence_requirement")
    return int(m.group(1))
