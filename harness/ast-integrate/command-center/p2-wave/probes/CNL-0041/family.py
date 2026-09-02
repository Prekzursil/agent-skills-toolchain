"""Independent ANONYMOUS-family roster for CNL-0041.

Two signals, different mechanisms:
  1. Regex extract of named P-ids from WORK-UNIT-CATALOG.json CNL-0041.question_or_target
  2. Count members in fixtures/family_roster.json (family=ANONYMOUS)

12-COUNCIL-PROTOCOLS-AND-PRESETS.json is searched, never invented. Absence is a
measured fact, not a count of 6 from that file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
ROSTER = HERE / "fixtures" / "family_roster.json"
EXPECTED_N = 6
FAMILY = "ANONYMOUS"
UNIT_ID = "CNL-0041"

LIBRARY_NAME = "12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
LIBRARY_CANDIDATES = (
    LIBRARY_NAME,
    f"command-center/sources/{LIBRARY_NAME}",
    f"command-center/design/council/{LIBRARY_NAME}",
    f"command-center/{LIBRARY_NAME}",
    f"harness-restore-20260806/{LIBRARY_NAME}",
)

PAREN_RE = re.compile(r"\((P\d{2}[^)]*)\)")
PAIR_RE = re.compile(r"(P\d{2})\s+([a-z0-9-]+)")


def library_hits(repo: Path | None = None) -> list[str]:
    root = repo or REPO
    hits: list[str] = []
    for rel in LIBRARY_CANDIDATES:
        p = root / rel
        if p.is_file():
            hits.append(rel.replace("\\", "/"))
    return hits


def catalog_unit(repo: Path | None = None) -> dict:
    root = repo or REPO
    data = json.loads(root.joinpath("command-center/WORK-UNIT-CATALOG.json").read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == UNIT_ID:
            return u
    raise RuntimeError("CNL-0041 missing from catalog")


def catalog_named_members(unit: dict | None = None) -> list[dict]:
    u = unit or catalog_unit()
    q = str(u.get("question_or_target") or "")
    paren = PAREN_RE.search(q)
    blob = paren.group(1) if paren else q
    seen: set[str] = set()
    out: list[dict] = []
    for pid, slug in PAIR_RE.findall(blob):
        if pid in seen:
            continue
        seen.add(pid)
        out.append({"id": pid, "slug": slug, "family": FAMILY})
    return out


def load_roster(path: Path | None = None) -> dict:
    p = path or ROSTER
    return json.loads(p.read_text(encoding="utf-8"))


def roster_members(doc: dict | None = None) -> list[dict]:
    d = doc if doc is not None else load_roster()
    members = d.get("members") or []
    return [m for m in members if isinstance(m, dict)]


def member_ids(members: list[dict]) -> list[str]:
    return [str(m.get("id") or "") for m in members]


def family_count_check(members: list[dict], expected_ids: list[str]) -> dict:
    ids = member_ids(members)
    fam = {str(m.get("id") or "") for m in members if str(m.get("family") or "") == FAMILY}
    expected = list(expected_ids)
    fired = False
    reasons: list[str] = []
    if len(ids) != EXPECTED_N:
        fired = True
        reasons.append(f"count={len(ids)} expected={EXPECTED_N}")
    if set(ids) != set(expected):
        fired = True
        reasons.append(f"id-set {sorted(set(ids))} != {sorted(set(expected))}")
    if fam != set(expected):
        fired = True
        reasons.append("family-field mis-assignment")
    if len(ids) != len(set(ids)):
        fired = True
        reasons.append("duplicate-id")
    return {
        "fired": fired,
        "silent": not fired,
        "count": len(ids),
        "expected_n": EXPECTED_N,
        "ids": ids,
        "reasons": reasons,
    }
