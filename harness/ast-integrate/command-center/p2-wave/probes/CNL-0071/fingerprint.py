#!/usr/bin/env python3
"""Signal 2: per-round change via sha256 of canonical dumps, not set sizes.

A round 'moved' iff the claim fingerprint, evidence fingerprint, or vote
tuple differs from the previous round. This is equality of hashes/tuples,
a different mechanism from gain.py's cardinalities.
"""
from __future__ import annotations

import hashlib
from typing import Any


def _canon_ids(round_doc: dict[str, Any], key: str) -> str:
    values = sorted(str(v) for v in (round_doc.get(key) or []))
    return "\n".join(values)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def claim_fingerprint(round_doc: dict[str, Any]) -> str:
    return sha256_text(_canon_ids(round_doc, "claim_ids"))


def evidence_fingerprint(round_doc: dict[str, Any]) -> str:
    return sha256_text(_canon_ids(round_doc, "evidence_ids"))


def vote_tuple(round_doc: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    raw = round_doc.get("votes") or {}
    return tuple(sorted((str(k), str(v)) for k, v in raw.items()))


def round_changed(prev: dict[str, Any], curr: dict[str, Any]) -> dict[str, Any]:
    c_prev, c_curr = claim_fingerprint(prev), claim_fingerprint(curr)
    e_prev, e_curr = evidence_fingerprint(prev), evidence_fingerprint(curr)
    v_prev, v_curr = vote_tuple(prev), vote_tuple(curr)
    claims_moved = c_prev != c_curr
    evidence_moved = e_prev != e_curr
    votes_moved = v_prev != v_curr
    moved = claims_moved or evidence_moved or votes_moved
    return {
        "claims_fp_prev": c_prev,
        "claims_fp_curr": c_curr,
        "evidence_fp_prev": e_prev,
        "evidence_fp_curr": e_curr,
        "votes_moved": votes_moved,
        "claims_moved": claims_moved,
        "evidence_moved": evidence_moved,
        "moved": moved,
        "signal": "sha256-canonical-dump-inequality",
    }


def attach_moves(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not rounds:
        return rows
    rows.append(
        {
            "round": int(rounds[0].get("n") or 1),
            "moved": None,
            "note": "no-predecessor",
            "signal": "sha256-canonical-dump-inequality",
        }
    )
    for i in range(1, len(rounds)):
        row = round_changed(rounds[i - 1], rounds[i])
        row["round"] = int(rounds[i].get("n") or (i + 1))
        rows.append(row)
    return rows
