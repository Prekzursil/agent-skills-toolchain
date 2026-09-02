"""Probe-1 detector: pairwise exclusive polarities with both spans quoted."""
from __future__ import annotations

from typing import Any

EXCLUSIVE = {
    ("OPEN", "CLOSED"),
    ("CLOSED", "OPEN"),
    ("EXISTS", "ABSENT"),
    ("ABSENT", "EXISTS"),
}


def exclusive_polarities(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if a.get("object_key") != b.get("object_key"):
        return False
    if a.get("claim_id") == b.get("claim_id"):
        return False
    pa, pb = a.get("polarity"), b.get("polarity")
    if (pa, pb) in EXCLUSIVE:
        return True
    if pa == "NUMERIC" and pb == "NUMERIC":
        return a.get("numeric_value") != b.get("numeric_value")
    return False


def candidate_id(a: dict[str, Any], b: dict[str, Any]) -> str:
    ids = sorted([a["claim_id"], b["claim_id"]])
    return f"CAND-{ids[0]}-{ids[1]}"


def candidates(
    claims: list[dict[str, Any]],
    *,
    always: bool = False,
) -> list[dict[str, Any]]:
    """Return pairwise contradiction *candidates* (untyped by time).

    `always=True` is the both-states mutant: every unordered pair is emitted.
    That mutant is not an extractor; probe 1 requires it to be rejected.
    """
    out: list[dict[str, Any]] = []
    for i, a in enumerate(claims):
        for b in claims[i + 1 :]:
            if always or exclusive_polarities(a, b):
                out.append(
                    {
                        "id": candidate_id(a, b),
                        "left_id": a["claim_id"],
                        "right_id": b["claim_id"],
                        "object_key": a.get("object_key")
                        if a.get("object_key") == b.get("object_key")
                        else f"{a.get('object_key')}|{b.get('object_key')}",
                        "left_span": a.get("span") or "",
                        "right_span": b.get("span") or "",
                        "left_source": f"{a.get('source_path')}:{a.get('source_line')}",
                        "right_source": f"{b.get('source_path')}:{b.get('source_line')}",
                        "left_polarity": a.get("polarity"),
                        "right_polarity": b.get("polarity"),
                        "exclusive": exclusive_polarities(a, b),
                    }
                )
    out.sort(key=lambda r: r["id"])
    return out


def pair_in(cands: list[dict[str, Any]], id_a: str, id_b: str) -> dict[str, Any] | None:
    want = candidate_id({"claim_id": id_a}, {"claim_id": id_b})
    for c in cands:
        if c["id"] == want:
            return c
    return None
