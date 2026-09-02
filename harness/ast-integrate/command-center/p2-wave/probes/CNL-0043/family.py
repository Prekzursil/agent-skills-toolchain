#!/usr/bin/env python3
"""FORECASTING family census for CNL-0043.

Two independent counts, then a live-library third signal if the file exists:
  1. P-ids named in the catalog question_or_target (anti-misassignment clause)
  2. records in the local fixture with family == FORECASTING
  3. records in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json if present on this tree

A disagreement in the number blocks the unit. The Windows library path from the
catalog is not assumed to exist here; absence is recorded, not filled from memory.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
CATALOG = REPO / "command-center" / "WORK-UNIT-CATALOG.json"
FIXTURE = HERE / "fixtures" / "protocols.json"
UNIT_ID = "CNL-0043"

PID_RE = re.compile(r"\bP(\d{2})\s+([a-z0-9-]+)")
FAM_RE = re.compile(r"family=([A-Z][A-Z0-9-]*)")
N_RE = re.compile(r"expected n=(\d+)")

LIBRARY_CANDIDATES = (
    "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "harness-restore/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "command-center/p2-wave/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
)


def load_catalog_unit(uid: str = UNIT_ID) -> dict:
    data = json.loads(CATALOG.read_text(encoding="utf-8"))
    for u in data.get("work_units") or []:
        if isinstance(u, dict) and u.get("id") == uid:
            return u
    raise KeyError(uid)


def catalog_anchor(
    uid: str, needle: str, *, prefer: str = "after"
) -> tuple[str, int, str]:
    """Return (path, 1-based line, snippet) for needle in THIS unit only.

    Catalog objects list evidence_requirement before `"id"` and question_or_target
    after it. Searching a bidirectional window cites the previous or next unit.
    `prefer='after'` walks forward from `"id"` first; `prefer='before'` walks back.
    """
    lines = CATALOG.read_text(encoding="utf-8").splitlines()
    start = None
    token = f'"id": "{uid}"'
    for i, line in enumerate(lines):
        if token in line:
            start = i
            break
    if start is None:
        raise KeyError(uid)
    after = range(start, min(len(lines), start + 80))
    before = range(start - 1, max(-1, start - 50), -1)
    order = (
        list(after) + list(before)
        if prefer == "after"
        else list(before) + list(after)
    )
    for j in order:
        if needle in lines[j]:
            snippet = lines[j].strip()
            return (
                "command-center/WORK-UNIT-CATALOG.json",
                j + 1,
                snippet[:240],
            )
    snippet = lines[start].strip()
    return ("command-center/WORK-UNIT-CATALOG.json", start + 1, snippet[:240])


def parse_named_members(question: str) -> list[tuple[str, str]]:
    return [(f"P{a}", b) for a, b in PID_RE.findall(question or "")]


def parse_expected(unit: dict) -> tuple[str, int]:
    ev = str(unit.get("evidence_requirement") or "")
    fam = FAM_RE.search(ev)
    n = N_RE.search(ev)
    if not fam or not n:
        raise ValueError("catalog evidence_requirement missing family=/expected n=")
    return fam.group(1), int(n.group(1))


def load_fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def fixture_family(doc: dict, family: str) -> list[dict]:
    out = []
    for rec in doc.get("records") or []:
        if isinstance(rec, dict) and rec.get("family") == family:
            out.append(rec)
    return out


def library_path() -> Path | None:
    for rel in LIBRARY_CANDIDATES:
        p = REPO / rel
        if p.is_file():
            return p
    return None


def _family_of(rec: dict) -> str | None:
    for k in ("family", "protocol_family", "Family"):
        v = rec.get(k)
        if isinstance(v, str) and v:
            return v
    return None


def _pid_of(rec: dict) -> str | None:
    for k in ("id", "pid", "P-id", "protocol_id"):
        v = rec.get(k)
        if isinstance(v, str) and re.fullmatch(r"P\d{2}", v):
            return v
    return None


def iter_library_records(doc) -> list[dict]:
    if isinstance(doc, list):
        return [x for x in doc if isinstance(x, dict)]
    if not isinstance(doc, dict):
        return []
    for key in ("protocols", "protocol_records", "records", "items"):
        v = doc.get(key)
        if isinstance(v, list) and v and isinstance(v[0], dict):
            return [x for x in v if isinstance(x, dict)]
    nested = doc.get("protocols")
    if isinstance(nested, dict):
        recs = nested.get("records") or nested.get("items")
        if isinstance(recs, list):
            return [x for x in recs if isinstance(x, dict)]
    return []


def library_family(family: str) -> dict:
    path = library_path()
    if path is None:
        return {
            "present": False,
            "path": None,
            "count": None,
            "ids": [],
            "note": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. "
                "Family membership is taken from the catalog named-member clause and "
                "the local fixture, not from invented library bytes."
            ),
        }
    doc = json.loads(path.read_text(encoding="utf-8"))
    recs = [r for r in iter_library_records(doc) if _family_of(r) == family]
    ids = [(_pid_of(r) or "") for r in recs]
    return {
        "present": True,
        "path": path.relative_to(REPO).as_posix(),
        "count": len(recs),
        "ids": ids,
        "note": "live library read",
    }


def census() -> dict:
    unit = load_catalog_unit()
    family, expected_n = parse_expected(unit)
    named = parse_named_members(str(unit.get("question_or_target") or ""))
    named_ids = [p for p, _ in named]
    named_slugs = {p: s for p, s in named}
    fix = load_fixture()
    fam_recs = fixture_family(fix, family)
    fix_ids = [str(r.get("id")) for r in fam_recs]
    lib = library_family(family)
    q_path, q_line, q_snip = catalog_anchor(
        UNIT_ID, "question_or_target", prefer="after"
    )
    e_path, e_line, e_snip = catalog_anchor(UNIT_ID, "expected n=", prefer="before")
    ra_path, ra_line, ra_snip = catalog_anchor("R-A09", "DISCOVERY", prefer="before")
    disagreements: list[str] = []
    if len(named_ids) != expected_n:
        disagreements.append(
            f"catalog-named {len(named_ids)} != expected n={expected_n}"
        )
    if len(fix_ids) != expected_n:
        disagreements.append(
            f"fixture-{family} {len(fix_ids)} != expected n={expected_n}"
        )
    if set(named_ids) != set(fix_ids):
        disagreements.append(
            f"named-set {named_ids} != fixture-set {fix_ids}"
        )
    if lib["present"] and lib["count"] != expected_n:
        disagreements.append(
            f"live-library {family} count {lib['count']} != expected n={expected_n}"
        )
    if lib["present"] and set(lib["ids"]) != set(named_ids):
        disagreements.append(
            f"live-library ids {lib['ids']} != named {named_ids}"
        )
    return {
        "unit_id": UNIT_ID,
        "family": family,
        "expected_n": expected_n,
        "signal1_catalog_named": {
            "count": len(named_ids),
            "members": [{"id": p, "slug": named_slugs[p]} for p in named_ids],
            "anchor": f"{q_path}:{q_line}",
            "snippet": q_snip,
        },
        "signal2_fixture": {
            "count": len(fix_ids),
            "ids": fix_ids,
            "path": FIXTURE.relative_to(REPO).as_posix(),
            "total_records_including_distractors": len(fix.get("records") or []),
        },
        "signal3_live_library": lib,
        "evidence_anchor": f"{e_path}:{e_line}",
        "evidence_snippet": e_snip,
        "r_a09_discovery_anchor": f"{ra_path}:{ra_line}",
        "r_a09_discovery_snippet": ra_snip,
        "disagreements": disagreements,
        "ok": not disagreements,
    }
