"""TST-0259 participant behavioural divergence statistic.

D is the mean of four [0, 1] components over one round of seat outputs:
  1. mean pairwise Jaccard distance of claim sets
  2. mean pairwise Jaccard distance of evidence-id sets
  3. vote dispersion (unique votes - 1) / (n - 1)
  4. mean pairwise Jaccard distance of opening-brief token sets

Panel FAILS (collapsed) when D < floor. Panel PASSES when D >= floor.
The floor is loaded from floor.json (pre-declared, not fitted here).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

HERE = Path(__file__).resolve().parent
TOKEN_RE = re.compile(r"[a-z0-9]+")
VOTE_MAP = {"approve": 1, "reject": -1, "abstain": 0, "+1": 1, "-1": -1, "0": 0}


def load_floor() -> dict[str, Any]:
    return json.loads((HERE / "floor.json").read_text(encoding="utf-8"))


def floor_value() -> float:
    return float(load_floor()["floor"])


def tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in TOKEN_RE.findall((text or "").lower()) if len(t) >= 3)


def jaccard_distance(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 0.0
    union = sa | sb
    return 1.0 - (len(sa & sb) / len(union))


def pairwise_mean_distance(sets: list[Iterable[str]]) -> float:
    n = len(sets)
    if n < 2:
        return 0.0
    total = 0.0
    count = 0
    for i in range(n):
        for j in range(i + 1, n):
            total += jaccard_distance(sets[i], sets[j])
            count += 1
    return total / count


def coerce_vote(raw: Any) -> int:
    if isinstance(raw, bool):
        raise TypeError("vote must not be a boolean")
    if isinstance(raw, int):
        if raw not in (-1, 0, 1):
            raise ValueError(f"vote int out of range: {raw}")
        return raw
    key = str(raw).strip().lower()
    if key not in VOTE_MAP:
        raise ValueError(f"unknown vote: {raw!r}")
    return VOTE_MAP[key]


def vote_dispersion(votes: list[int]) -> float:
    n = len(votes)
    if n < 2:
        return 0.0
    return (len(set(votes)) - 1) / (n - 1)


def score_from_raw(participants: list[dict[str, Any]]) -> dict[str, Any]:
    if len(participants) < 2:
        raise ValueError("need at least two participants")
    claims = [list(p.get("claims") or []) for p in participants]
    evidence = [list(p.get("evidence") or []) for p in participants]
    openings = [str(p.get("opening") or "") for p in participants]
    votes = [coerce_vote(p.get("vote")) for p in participants]
    claim_d = pairwise_mean_distance(claims)
    evidence_d = pairwise_mean_distance(evidence)
    lexical_d = pairwise_mean_distance([tokens(t) for t in openings])
    vote_d = vote_dispersion(votes)
    d = (claim_d + evidence_d + vote_d + lexical_d) / 4.0
    fl = floor_value()
    collapsed = d < fl
    return {
        "D": d,
        "claim_jaccard_distance": claim_d,
        "evidence_jaccard_distance": evidence_d,
        "vote_dispersion": vote_d,
        "lexical_jaccard_distance": lexical_d,
        "floor": fl,
        "n_seats": len(participants),
        "unique_votes": sorted(set(votes)),
        "panel": "FAIL" if collapsed else "PASS",
        "collapsed": collapsed,
        "votes": votes,
        "seat_ids": [str(p.get("seat_id")) for p in participants],
        "roles": [str(p.get("role")) for p in participants],
    }


def score_transcript(transcript: dict[str, Any]) -> dict[str, Any]:
    parts = list(transcript.get("participants") or [])
    out = score_from_raw(parts)
    out["cast_id"] = transcript.get("cast_id")
    out["round"] = transcript.get("round", 1)
    return out
