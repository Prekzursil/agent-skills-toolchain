"""Adversarial seating: real prior conflict vs manufactured disagreement.

A seat is adversarial only when a locked prior on the question axis disagrees
with another seat's locked prior from a *different* evidence source.
Assigned debating positions (assigned_stance, or oppositional role pairs
without such priors) are THEATRE and are refused, not performed.
"""
from __future__ import annotations

from typing import Any

from priors import (
    prior_polarity,
    stance_polarity,
    verify_commitment,
)

# Role pairs that *are* assigned debating positions when they lack priors.
OPPOSITIONAL_ROLES = {
    frozenset({"advocate", "critic"}),
    frozenset({"red", "blue"}),
    frozenset({"proposer", "skeptic"}),
    frozenset({"champion", "opponent"}),
    frozenset({"defense", "prosecution"}),
}

REAL_CONFLICT = "REAL_CONFLICT"
THEATRE = "THEATRE"
ALIGNED = "ALIGNED"
UNINFORMED = "UNINFORMED"


class TheatreReject(Exception):
    """Selector refused to seat a manufactured-disagreement roster."""

    def __init__(self, reason: str, pair: tuple[str, str] | None = None):
        super().__init__(reason)
        self.reason = reason
        self.pair = pair


def _role(seat: dict[str, Any]) -> str:
    return str(seat.get("role") or "").strip().lower()


def _prior(seat: dict[str, Any]) -> dict[str, Any] | None:
    p = seat.get("prior")
    return p if isinstance(p, dict) else None


def classify_pair(a: dict[str, Any], b: dict[str, Any], axis: str) -> dict[str, str]:
    """Classify one pair. Returns {code, reason}."""
    sa = stance_polarity(a.get("assigned_stance"))
    sb = stance_polarity(b.get("assigned_stance"))
    pa, pb = _prior(a), _prior(b)
    ida = str(a.get("seat_id") or "?")
    idb = str(b.get("seat_id") or "?")

    # TOKEN:THEATRE-ASSIGNED-WITHOUT-PRIOR
    if sa is not None and pa is None:
        return {"code": THEATRE, "reason": "ASSIGNED_STANCE_WITHOUT_PRIOR", "a": ida, "b": idb}
    if sb is not None and pb is None:
        return {"code": THEATRE, "reason": "ASSIGNED_STANCE_WITHOUT_PRIOR", "a": ida, "b": idb}

    # TOKEN:THEATRE-OPPOSITIONAL-ROLES-WITHOUT-PRIOR
    roles = frozenset({_role(a), _role(b)})
    if roles in OPPOSITIONAL_ROLES and (pa is None or pb is None):
        return {
            "code": THEATRE,
            "reason": "OPPOSITIONAL_ROLES_WITHOUT_PRIOR",
            "a": ida,
            "b": idb,
        }

    if pa is None or pb is None:
        return {"code": UNINFORMED, "reason": "MISSING_PRIOR", "a": ida, "b": idb}

    # TOKEN:THEATRE-COMMITMENT-MISMATCH
    if not verify_commitment(a) or not verify_commitment(b):
        return {"code": THEATRE, "reason": "COMMITMENT_MISMATCH", "a": ida, "b": idb}

    if str(pa.get("axis") or "") != axis or str(pb.get("axis") or "") != axis:
        return {"code": THEATRE, "reason": "AXIS_MISMATCH", "a": ida, "b": idb}

    pola, polb = float(pa["polarity"]), float(pb["polarity"])
    # TOKEN:THEATRE-ASSIGNED-STANCE-CONTRADICTS-PRIOR
    if sa is not None and sa * pola < 0:
        return {
            "code": THEATRE,
            "reason": "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
            "a": ida,
            "b": idb,
        }
    if sb is not None and sb * polb < 0:
        return {
            "code": THEATRE,
            "reason": "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
            "a": ida,
            "b": idb,
        }

    if sa is not None and sb is not None and sa * sb < 0:
        # TOKEN:THEATRE-OPPOSITE-STANCE-SHARED-EVIDENCE
        if str(pa.get("evidence_id")) == str(pb.get("evidence_id")):
            return {
                "code": THEATRE,
                "reason": "OPPOSITE_STANCE_SHARED_EVIDENCE",
                "a": ida,
                "b": idb,
            }
        # TOKEN:THEATRE-OPPOSITE-STANCE-SHARED-POLARITY
        if pola * polb > 0:
            return {
                "code": THEATRE,
                "reason": "OPPOSITE_STANCE_SHARED_POLARITY",
                "a": ida,
                "b": idb,
            }

    if roles in OPPOSITIONAL_ROLES and pola * polb > 0:
        return {
            "code": THEATRE,
            "reason": "OPPOSITIONAL_ROLES_SHARED_POLARITY",
            "a": ida,
            "b": idb,
        }

    if pola * polb > 0:
        return {"code": ALIGNED, "reason": "SAME_SIGN_PRIORS", "a": ida, "b": idb}
    if pola * polb == 0:
        return {"code": UNINFORMED, "reason": "ZERO_POLARITY", "a": ida, "b": idb}

    if str(pa.get("evidence_id")) == str(pb.get("evidence_id")):
        return {
            "code": THEATRE,
            "reason": "CONFLICT_CLAIM_SHARED_EVIDENCE",
            "a": ida,
            "b": idb,
        }

    # TOKEN:REAL-PRIOR-CONFLICT
    return {"code": REAL_CONFLICT, "reason": "INDEPENDENT_OPPOSITE_PRIORS", "a": ida, "b": idb}


def classify_roster(seats: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    pairs = []
    theatre = []
    real = []
    for i, a in enumerate(seats):
        for b in seats[i + 1 :]:
            row = classify_pair(a, b, axis)
            pairs.append(row)
            if row["code"] == THEATRE:
                theatre.append(row)
            elif row["code"] == REAL_CONFLICT:
                real.append(row)
    if theatre:
        fired = True
        verdict = THEATRE
        reason = theatre[0]["reason"]
    elif real:
        fired = False
        verdict = REAL_CONFLICT
        reason = real[0]["reason"]
    else:
        fired = False
        verdict = UNINFORMED
        reason = pairs[0]["reason"] if pairs else "EMPTY_ROSTER"
    return {
        "verdict": verdict,
        "reason": reason,
        "fired": fired,
        "theatre_pairs": theatre,
        "real_pairs": real,
        "pair_count": len(pairs),
        "pairs": pairs,
    }


def adversarial_select(seats: list[dict[str, Any]], axis: str) -> dict[str, Any]:
    """Seat a real-prior adversarial pair or refuse theatre/uninformed pools."""
    report = classify_roster(seats, axis)
    if report["verdict"] == THEATRE:
        hit = report["theatre_pairs"][0]
        raise TheatreReject(hit["reason"], (hit["a"], hit["b"]))
    if not report["real_pairs"]:
        raise TheatreReject(report["reason"] or "NO_REAL_PRIOR_CONFLICT", None)
    best = None
    best_gap = -1.0
    by_id = {str(s.get("seat_id")): s for s in seats}
    for pair in report["real_pairs"]:
        a, b = by_id[pair["a"]], by_id[pair["b"]]
        gap = abs(prior_polarity(a) - prior_polarity(b))
        if gap > best_gap:
            best_gap = gap
            best = pair
    assert best is not None
    return {
        "seated": [best["a"], best["b"]],
        "reason": best["reason"],
        "gap": best_gap,
        "verdict": REAL_CONFLICT,
    }


def naive_select(seats: list[dict[str, Any]]) -> dict[str, Any]:
    """Broken selector: treats assigned_stance (or oppositional roles) as conflict.

    This is the state the check is meant to reject. It will seat theatre.
    """
    for i, a in enumerate(seats):
        for b in seats[i + 1 :]:
            sa = stance_polarity(a.get("assigned_stance"))
            sb = stance_polarity(b.get("assigned_stance"))
            if sa is not None and sb is not None and sa * sb < 0:
                return {
                    "seated": [str(a.get("seat_id")), str(b.get("seat_id"))],
                    "reason": "NAIVE_OPPOSITE_ASSIGNED_STANCE",
                    "verdict": "NAIVE_ACCEPT",
                }
            roles = frozenset({_role(a), _role(b)})
            if roles in OPPOSITIONAL_ROLES:
                return {
                    "seated": [str(a.get("seat_id")), str(b.get("seat_id"))],
                    "reason": "NAIVE_OPPOSITIONAL_ROLES",
                    "verdict": "NAIVE_ACCEPT",
                }
    return {"seated": [], "reason": "NAIVE_NO_LABELS", "verdict": "NAIVE_EMPTY"}
