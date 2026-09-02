#!/usr/bin/env python3
"""Independent re-tabulation of ledger/synthesis coverage.

Walks JSON recursively collecting idea_id / cites_idea_ids / covers_mechanisms
instead of calling ledger.signal_a_missing_idea_ids. A disagreement in the
counts with the author's check blocks the unit.
"""
from __future__ import annotations

from typing import Any


def _walk(obj: Any, found: dict[str, list[Any]]) -> None:
    if isinstance(obj, dict):
        if "idea_id" in obj and isinstance(obj.get("idea_id"), str):
            found["idea_records"].append(obj)
        if isinstance(obj.get("cites_idea_ids"), list):
            found["cites"].extend(
                x for x in obj["cites_idea_ids"] if isinstance(x, str) and x
            )
        if isinstance(obj.get("covers_mechanisms"), list):
            found["covers"].extend(
                x for x in obj["covers_mechanisms"] if isinstance(x, str) and x
            )
        for value in obj.values():
            _walk(value, found)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, found)


def tabulate(doc: dict) -> dict:
    found: dict[str, list[Any]] = {"idea_records": [], "cites": [], "covers": []}
    _walk(doc, found)
    required_ids: list[str] = []
    required_mechs: list[str] = []
    for row in found["idea_records"]:
        dup = row.get("duplicate_of")
        if dup not in (None, "", []):
            continue
        iid = row.get("idea_id")
        mech = row.get("canonical_mechanism")
        if isinstance(iid, str) and iid:
            required_ids.append(iid)
        if isinstance(mech, str) and mech:
            required_mechs.append(mech)
    req_ids = set(required_ids)
    req_mechs = set(required_mechs)
    cited = set(found["cites"])
    covered = set(found["covers"])
    missing_ids = sorted(req_ids - cited)
    missing_mechs = sorted(req_mechs - covered)
    return {
        "n_idea_records": len(found["idea_records"]),
        "n_required": len(req_ids),
        "n_cited": len(cited),
        "n_covered": len(covered),
        "n_missing_ids": len(missing_ids),
        "n_missing_mechs": len(missing_mechs),
        "missing_ids": missing_ids,
        "missing_mechs": missing_mechs,
        "required_ids": sorted(req_ids),
        "required_mechs": sorted(req_mechs),
        "walk": "recursive-json-collect",
    }


def numbers_agree(author: dict, indep: dict) -> tuple[bool, str]:
    a = author.get("signal_a") or {}
    b = author.get("signal_b") or {}
    checks = [
        ("n_canonical", author.get("n_canonical"), indep.get("n_required")),
        ("n_missing_ids", a.get("n_missing"), indep.get("n_missing_ids")),
        ("n_missing_mechs", b.get("n_missing"), indep.get("n_missing_mechs")),
        ("missing_ids", list(a.get("missing") or []), list(indep.get("missing_ids") or [])),
        (
            "missing_mechs",
            list(b.get("missing") or []),
            list(indep.get("missing_mechs") or []),
        ),
    ]
    for name, left, right in checks:
        if left != right:
            return False, f"{name} author={left!r} indep={right!r}"
    return True, "ok"
