#!/usr/bin/env python3
"""Signal 1: per-round information gain from set cardinality + vote Hamming.

gain(t) = |claims_t - claims_{t-1}| + |evidence_t - evidence_{t-1}|
          + Hamming(votes_t, votes_{t-1})

This is arithmetic over set sizes and pairwise vote mismatches. It is not
a hash and not an entropy. A round with gain > 0 is still moving.
"""
from __future__ import annotations

from typing import Any


def _ids(round_doc: dict[str, Any], key: str) -> frozenset[str]:
    values = round_doc.get(key) or []
    return frozenset(str(v) for v in values)


def _votes(round_doc: dict[str, Any]) -> dict[str, str]:
    raw = round_doc.get("votes") or {}
    return {str(k): str(v) for k, v in raw.items()}


def vote_hamming(prev: dict[str, str], curr: dict[str, str]) -> int:
    members = set(prev) | set(curr)
    n = 0
    for m in members:
        if prev.get(m) != curr.get(m):
            n += 1
    return n


def round_gain(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    prev_claims = _ids(prev, "claim_ids")
    curr_claims = _ids(curr, "claim_ids")
    prev_ev = _ids(prev, "evidence_ids")
    curr_ev = _ids(curr, "evidence_ids")
    new_claims = curr_claims - prev_claims
    new_ev = curr_ev - prev_ev
    dropped_claims = prev_claims - curr_claims
    pv, cv = _votes(prev), _votes(curr)
    hamming = vote_hamming(pv, cv)
    content = len(new_claims) + len(new_ev)
    gain = content + hamming
    return {
        "new_claim_ids": sorted(new_claims),
        "new_evidence_ids": sorted(new_ev),
        "dropped_claim_ids": sorted(dropped_claims),
        "new_claim_count": len(new_claims),
        "new_evidence_count": len(new_ev),
        "vote_hamming": hamming,
        "content_gain": content,
        "gain": gain,
        "signal": "set-cardinality-plus-vote-hamming",
    }


def attach_trace(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-round gain. Round 1 has no predecessor so gain is undefined (None)."""
    trace: list[dict[str, Any]] = []
    if not rounds:
        return trace
    first = {
        "round": int(rounds[0].get("n") or 1),
        "gain": None,
        "note": "no-predecessor",
        "signal": "set-cardinality-plus-vote-hamming",
    }
    trace.append(first)
    for i in range(1, len(rounds)):
        row = round_gain(rounds[i - 1], rounds[i])
        row["round"] = int(rounds[i].get("n") or (i + 1))
        trace.append(row)
    return trace


def last_defined_gain(trace: list[dict[str, Any]]) -> int | None:
    for row in reversed(trace):
        g = row.get("gain")
        if g is None:
            continue
        return int(g)
    return None
