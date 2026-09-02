#!/usr/bin/env python3
"""Independent recount of the four share statistics from raw transcript events.

Does not import tools.council.simulate.share helpers. Token counts are
re-derived from spoken text (whitespace split), not from event.token_count.
Surviving claims are unrebutted claim ids attributed to the emitting seat.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

SHARE_KEYS = ("turns", "tokens", "surviving_claims", "cited_evidence")


def tokens_of(text: str) -> list[str]:
    return [t for t in str(text or "").split() if t]


def recount(events: Sequence[Mapping[str, Any]], seats: Sequence[str]) -> dict[str, Any]:
    turns: Counter[str] = Counter()
    tokens: Counter[str] = Counter()
    evidence: Counter[str] = Counter()
    emitted: dict[str, str] = {}
    rebutted: set[str] = set()
    for ev in events:
        if not isinstance(ev, Mapping):
            continue
        if ev.get("kind") != "turn":
            continue
        seat = str(ev.get("seat") or "")
        if seat not in seats:
            continue
        turns[seat] += 1
        spoken = tokens_of(str(ev.get("text") or ""))
        tokens[seat] += len(spoken)
        evidence[seat] += len(ev.get("evidence") or [])
        for claim in ev.get("claims") or []:
            if not isinstance(claim, Mapping):
                continue
            cid = str(claim.get("id") or "")
            if cid:
                emitted[cid] = seat
        for rid in ev.get("rebuts") or []:
            if rid:
                rebutted.add(str(rid))
    surviving: Counter[str] = Counter()
    for cid, seat in emitted.items():
        if cid not in rebutted:
            surviving[seat] += 1
    counts: dict[str, dict[str, int]] = {}
    for s in seats:
        counts[s] = {
            "turns": int(turns.get(s, 0)),
            "tokens": int(tokens.get(s, 0)),
            "surviving_claims": int(surviving.get(s, 0)),
            "cited_evidence": int(evidence.get(s, 0)),
        }
    totals = {k: sum(counts[s][k] for s in seats) for k in SHARE_KEYS}
    shares: dict[str, dict[str, float]] = {}
    for s in seats:
        shares[s] = {
            k: (float(counts[s][k]) / totals[k]) if totals[k] else 0.0 for k in SHARE_KEYS
        }
    return {"counts": counts, "shares": shares, "totals": totals}


def effect_from_counts(
    pre_counts: Mapping[str, Mapping[str, int]],
    post_counts: Mapping[str, Mapping[str, int]],
    loud: str,
    seats: Sequence[str],
) -> dict[str, Any]:
    def share(counts: Mapping[str, Mapping[str, int]], key: str) -> float:
        tot = sum(int(counts[s][key]) for s in seats)
        if tot == 0:
            return 0.0
        return float(counts[loud][key]) / tot

    pre_t = share(pre_counts, "turns")
    post_t = share(post_counts, "turns")
    delta = pre_t - post_t
    post_s = share(post_counts, "surviving_claims")
    return {
        "loud_seat": loud,
        "metric": "loud_turn_share",
        "pre": pre_t,
        "post": post_t,
        "delta": delta,
        "interval": [delta, delta],
        "post_surviving_claims_share": post_s,
        "outcome_dominance_persists": post_s > post_t,
    }


def counts_equal(a: Mapping[str, Mapping[str, int]], b: Mapping[str, Mapping[str, int]]) -> bool:
    if set(a) != set(b):
        return False
    for s in a:
        if dict(a[s]) != dict(b[s]):
            return False
    return True
