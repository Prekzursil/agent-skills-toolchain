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
