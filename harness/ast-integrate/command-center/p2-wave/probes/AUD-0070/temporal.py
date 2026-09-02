"""Probe-2 detector: temporal reclassification of exclusive pairs.

If a later claim describes the same object and is a resolving polarity
(CLOSED/ABSENT) relative to an earlier OPEN/EXISTS claim, the edge is
SUPERSEDED rather than CONTRADICTION. Same as_of stays CONTRADICTION.
Missing timestamps cannot supersede.
"""
from __future__ import annotations

from datetime import date
from typing import Any

RESOLVING = {"CLOSED", "ABSENT"}


def parse_as_of(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(str(raw)[:10])
    except ValueError:
        return None


def classify_pair(
    a: dict[str, Any],
    b: dict[str, Any],
    *,
    blind: bool = False,
) -> str:
    """Return CONTRADICTION or SUPERSEDED.

    `blind=True` is the both-states mutant: timestamps are ignored, so a
    later resolution is misclassified as CONTRADICTION. Probe 2 requires
    that mutant to fail the known pair.
    """
    ta = parse_as_of(None if blind else a.get("as_of"))
    tb = parse_as_of(None if blind else b.get("as_of"))
    if ta is None or tb is None or ta == tb:
        return "CONTRADICTION"
    earlier, later = (a, b) if ta < tb else (b, a)
    if later.get("polarity") in RESOLVING and earlier.get("polarity") not in RESOLVING:
        return "SUPERSEDED"
    return "CONTRADICTION"


def classify_candidates(
    claims_by_id: dict[str, dict[str, Any]],
    cands: list[dict[str, Any]],
    *,
    blind: bool = False,
) -> list[dict[str, Any]]:
    edges = []
    for cand in cands:
        if not cand.get("exclusive"):
            continue
        a = claims_by_id[cand["left_id"]]
        b = claims_by_id[cand["right_id"]]
        edge_type = classify_pair(a, b, blind=blind)
        earlier, later = a, b
        ta, tb = parse_as_of(a.get("as_of")), parse_as_of(b.get("as_of"))
        if ta is not None and tb is not None and tb < ta:
            earlier, later = b, a
        row = dict(cand)
        row["edge_type"] = edge_type
        row["earlier_id"] = earlier["claim_id"]
        row["later_id"] = later["claim_id"]
        row["earlier_as_of"] = earlier.get("as_of")
        row["later_as_of"] = later.get("as_of")
        row["blind"] = blind
        edges.append(row)
    edges.sort(key=lambda r: r["id"])
    return edges
