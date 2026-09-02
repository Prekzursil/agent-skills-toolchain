"""Independent census of the CNL-0042 GENERATIVE closed set.

Two mechanically different counts:
  1. Regex extract of P-ids from WORK-UNIT-CATALOG.json CNL-0042.question_or_target
  2. Roster records with family=GENERATIVE (decoy FORECASTING P33 excluded)

12-COUNCIL-PROTOCOLS-AND-PRESETS.json is searched; absence is recorded, not
invented. The catalog parenthetical is the ranging set the unit itself names
so no member can fall through a family mis-assignment.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
ROSTER = HERE / "fixtures" / "family_roster.json"
DECOY = HERE / "fixtures" / "decoy_non_generative.json"
EXPECTED_N = 7
NAMED_IDS = ("P26", "P27", "P28", "P29", "P30", "P31", "P32")
PID_IN_QUESTION = re.compile(r"\b(P2[6-9]|P3[0-2])\s+([a-z0-9-]+)")
LIBRARY_CANDIDATES = (
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_unit() -> dict:
    data = load_json(CATALOG)
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == "CNL-0042":
            return u
    raise RuntimeError("CNL-0042 missing from catalog")


def named_from_catalog_question(question: str) -> list[tuple[str, str]]:
    found = PID_IN_QUESTION.findall(question)
    # Preserve first-seen order, drop duplicates.
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pid, slug in found:
        if pid in seen:
            continue
        seen.add(pid)
        out.append((pid, slug))
    return out


def library_hits() -> dict:
    hits = []
    present = []
    for rel in LIBRARY_CANDIDATES:
        p = REPO / rel
        hits.append({"path": rel, "present": p.is_file()})
        if p.is_file():
            present.append(rel)
    return {"tried": hits, "present": present}


def roster_generative() -> list[dict]:
    doc = load_json(ROSTER)
    return [r for r in doc.get("records") or [] if r.get("family") == "GENERATIVE"]


def decoy_ids() -> list[str]:
    doc = load_json(DECOY)
    return [str(r.get("id")) for r in doc.get("records") or []]


def census() -> dict:
    unit = catalog_unit()
    q = str(unit.get("question_or_target") or "")
    named = named_from_catalog_question(q)
    roster = roster_generative()
    named_ids = [p for p, _ in named]
    roster_ids = [str(r["id"]) for r in roster]
    decoys = decoy_ids()
    lib = library_hits()
    agree = named_ids == list(NAMED_IDS) and roster_ids == list(NAMED_IDS)
    leaked_decoy = any(d in roster_ids or d in named_ids for d in decoys)
    return {
        "expected_n": EXPECTED_N,
        "catalog_named": [{"id": p, "slug": s} for p, s in named],
        "catalog_n": len(named),
        "roster_ids": roster_ids,
        "roster_n": len(roster),
        "decoy_ids": decoys,
        "decoy_excluded": not leaked_decoy,
        "library": lib,
        "library_used_as_census": False,
        "counts_agree": agree and len(named) == EXPECTED_N and not leaked_decoy,
        "counts_agree": agree and len(named) == EXPECTED_N and not leaked_decoy,
        "named_ids": named_ids,
        "decoy_ids": decoys,
    }


REPO = REPO
EXPECTED_N = EXPECTED_N
NAMED_IDS = NAMED_IDS
roster_generative = roster_generative
named_from_catalog_question = named_from_catalog_question
catalog_unit = catalog_unit
decoy_ids = decoy_ids
roster_generative = roster_generative
named_from_catalog_question = named_from_catalog_question
catalog_unit = catalog_unit
decoy_ids = decoy_ids
