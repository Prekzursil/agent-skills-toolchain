"""Participant-count sensitivity analysis. IMP-0367.

Re-runs a decision at several seat counts and publishes the decision-versus-N
curve, its stabilisation point N*, and an honest comparison of the configured
default against N*. An evidence-decisive question stabilises at low N; an
N-sensitive question publishes its flips instead of being retuned until it
looks stable (tune_until_stable exists ONLY as the documented bad practice).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

AGG_MAJORITY = "AGG_MAJORITY"
AGG_N_MODULATED = "AGG_N_MODULATED"
DEFAULT_SEAT_COUNT = 5
LOW_N_MAX = 15


@dataclass
class Result:
    ok: bool = True
    n: int = 0
    decision: str = ""
    votes: list = field(default_factory=list)
    aggregator: str = AGG_MAJORITY
    reason: str = ""

    def as_dict(self) -> dict:
        return {"ok": self.ok, "n": self.n, "decision": self.decision,
                "votes": list(self.votes), "aggregator": self.aggregator}


def load_question(path: Path | str) -> dict:
    doc = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or "votes_by_n" not in doc:
        raise ValueError(f"not a sensitivity question: {path}")
    return doc


def _majority(votes: list[str]) -> str:
    if not votes:
        return "NO-QUORUM"
    accept = sum(1 for v in votes if v == "ACCEPT")
    reject = sum(1 for v in votes if v == "REJECT")
    if accept > reject:
        return "ACCEPT"
    if reject > accept:
        return "REJECT"
    return "TIED"


def evaluate_question(q: dict, n: int,
                      aggregator: str = AGG_MAJORITY) -> Result:
    votes_by_n = q.get("votes_by_n") or {}
    key = str(n)
    votes = list(votes_by_n.get(key) or [])
    if not votes:
        raise ValueError(f"question {q.get('id')} has no votes for N={n}")
    if aggregator == AGG_N_MODULATED:
        accept = sum(1 for v in votes if v == "ACCEPT")
        reject = sum(1 for v in votes if v == "REJECT")
        weight_accept = 0.0
        weight_reject = 0.0
        for i, v in enumerate(votes):
            w = 1.0 / (i + 1)
            if v == "ACCEPT":
                weight_accept += w
            elif v == "REJECT":
                weight_reject += w
        if weight_accept > weight_reject:
            decision = "ACCEPT"
        elif weight_reject > weight_accept:
            decision = "REJECT"
        else:
            decision = "TIED"
        return Result(n=n, decision=decision, votes=votes, aggregator=aggregator)
    return Result(n=n, decision=_majority(votes), votes=votes,
                  aggregator=aggregator)
def curve(q: dict, n_min: int = 1, n_max: int = LOW_N_MAX,
          aggregator: str = AGG_MAJORITY) -> dict:
    rows = []
    for n in range(n_min, n_max + 1):
        res = evaluate_question(q, n, aggregator)
        rows.append(res.as_dict())
    out = {
        "question_id": str(q.get("id")),
        "kind": str(q.get("kind") or "unknown"),
        "aggregator": aggregator,
        "rows": [{"n": r["n"], "decision": r["decision"]} for r in rows],
    }
    flips = 0
    for a, b in zip(out["rows"], out["rows"][1:]):
        if a["decision"] != b["decision"]:
            flips = flips + 1
    stable = _stabilisation_point(out["rows"])
    out["flip_count"] = flips
    out["stabilisation_point"] = stable["n_star"]
    out["stable_decision"] = stable["decision"]
    out["is_n_sensitive"] = flips > 0
    out["published"] = True
    return out


def _stabilisation_point(rows: list[dict]) -> dict:
    if not rows:
        return {"n_star": None, "decision": ""}
    tail = rows[-1]["decision"]
    n_star = rows[-1]["n"]
    for row in reversed(rows):
        if row["decision"] == tail:
            n_star = row["n"]
        else:
            break
    return {"n_star": n_star, "decision": tail}
def compare_default(q: dict) -> dict:
    c = curve(q)
    default_n = int(q.get("default_n") or DEFAULT_SEAT_COUNT)
    at_default = None
    for row in c["rows"]:
        if row["n"] == default_n:
            at_default = row["decision"]
    above = at_default == c["stable_decision"]
    out = {
        "question_id": c["question_id"],
        "default_n": default_n,
        "stabilisation_point": c["stabilisation_point"],
        "stable_decision": c["stable_decision"],
        "decision_at_default": at_default,
        "default_above_stable": bool(above),
        "n_sensitive_question": c["is_n_sensitive"],
    }
    return out


def tune_until_stable(q: dict) -> dict:
    """The documented BAD practice: search for an N that hides the flips.

    Exists only so the negative control can show it collapsing an N-sensitive
    curve into a stable-looking single N. Production publishes the flips.
    """
    c = curve(q)
    stable = c["stabilisation_point"]
    chosen = stable if stable is not None else 1
    return {
        "question_id": c["question_id"],
        "chosen_n": chosen,
        "decision": c["stable_decision"],
        "flips_collapsed": c["flip_count"],
        "collapsed": c["flip_count"] > 0,
    }


def protocol_is_n_sensitive(c: dict) -> bool:
    return bool(c.get("is_n_sensitive"))


def public_row(c: dict) -> dict:
    return {
        "question_id": c["question_id"],
        "kind": c["kind"],
        "n_star": c["stabilisation_point"],
        "stable_decision": c["stable_decision"],
        "flip_count": c["flip_count"],
        "is_n_sensitive": c["is_n_sensitive"],
        "published": c["published"],
    }


__all__ = [
    "AGG_MAJORITY", "AGG_N_MODULATED", "DEFAULT_SEAT_COUNT", "LOW_N_MAX",
    "Result", "compare_default", "curve", "evaluate_question",
    "load_question", "protocol_is_n_sensitive", "public_row",
    "tune_until_stable",
]
