"""Enumerate ADVERSARIAL family members without reading the design note."""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE = HERE / "fixtures" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
UNIT_ID = "CNL-0039"
FAMILY = "ADVERSARIAL"
PID_RE = re.compile(r"\b(P\d{2})\s+([a-z0-9-]+(?:\s*\([^)]+\))?)", re.I)
EXPECTED_N_RE = re.compile(r"expected n=(\d+)")

LIBRARY_CANDIDATES = (
    REPO / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    REPO / "command-center" / "sources" / "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_fixture() -> dict:
    return load_json(FIXTURE)


def adversarial_from_fixture(doc: dict | None = None) -> list[dict]:
    data = doc if doc is not None else load_fixture()
    rows = [
        p
        for p in (data.get("protocols") or [])
        if isinstance(p, dict) and p.get("family") == FAMILY
    ]
    return sorted(rows, key=lambda p: str(p.get("id") or ""))


def ids_from_fixture(doc: dict | None = None) -> list[str]:
    return [str(p["id"]) for p in adversarial_from_fixture(doc)]


def catalog_unit(uid: str = UNIT_ID) -> dict:
    data = load_json(CATALOG)
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def parse_ranging(question: str) -> list[tuple[str, str]]:
    """Pull (P-id, slug) pairs from a CNL ranging sentence.

    Must not slice on the first ')' — P48's slug contains '(war-game)'.
    """
    out: list[tuple[str, str]] = []
    for pid, slug in PID_RE.findall(question):
        slug_n = re.sub(r"\s+", "-", slug.strip().lower())
        slug_n = re.sub(r"[()]", "", slug_n)
        slug_n = re.sub(r"-{2,}", "-", slug_n).strip("-")
        out.append((pid.upper(), slug_n))
    return out


def ids_from_catalog_question(unit: dict | None = None) -> list[str]:
    rec = unit if unit is not None else catalog_unit()
    pairs = parse_ranging(str(rec.get("question_or_target") or ""))
    return [pid for pid, _ in pairs]


def slugs_from_catalog_question(unit: dict | None = None) -> dict[str, str]:
    rec = unit if unit is not None else catalog_unit()
    return dict(parse_ranging(str(rec.get("question_or_target") or "")))


def expected_n_from_evidence(unit: dict | None = None) -> int:
    rec = unit if unit is not None else catalog_unit()
    m = EXPECTED_N_RE.search(str(rec.get("evidence_requirement") or ""))
    if not m:
        raise ValueError("expected n= missing from evidence_requirement")
    return int(m.group(1))


def library_on_disk() -> Path | None:
    for path in LIBRARY_CANDIDATES:
        if path.is_file():
            return path
    return None


def plant_family_undercount(doc: dict) -> dict:
    """Retag P13 so ADVERSARIAL count drops by one."""
    planted = json.loads(json.dumps(doc))
    for p in planted.get("protocols") or []:
        if p.get("id") == "P13":
            p["family"] = "JUDICIAL"
            p["planted"] = "family-misassignment"
    return planted
