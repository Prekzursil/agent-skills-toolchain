"""B07-shaped tally: majority / supermajority / unanimity with quorum, weights, abstention.

Production tools/council/vote/tally.py is absent on this worktree. This module is the
configured-methods oracle the enumerator and validation-time flag run against. Semantics:

* ABSTAIN is not a ballot for an alternative; it drops the seat from the participating pool.
* quorum kind=count: participating seat count must be >= min.
* quorum kind=weight: participating weight must be >= min.
* quorum kind=none: a decision is always returned; empty participation yields status-quo A.
* QUORUM_FAIL is a first-class outcome, distinct from A/B. A voter who can meet quorum by
  casting any real ballot cannot obtain QUORUM_FAIL except by abstaining — that is the
  strategic-abstention hole this unit enumerates.
* Ties and failed thresholds resolve to status-quo alternatives[0] ('A'), so equal-weight
  no-quorum majority cannot manufacture a unique-by-abstention outcome (negative control).
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

ABSTAIN = "ABSTAIN"
QUORUM_FAIL = "QUORUM_FAIL"
STATUS_QUO = "A"
ALTERNATIVES = ("A", "B")
METHODS = ("majority", "supermajority", "unanimity")


def _as_quorum(quorum: Any) -> dict[str, Any]:
    if quorum is None:
        return {"kind": "none"}
    if isinstance(quorum, dict):
        kind = str(quorum.get("kind") or "none")
        if kind in {"none", "null", ""}:
            return {"kind": "none"}
        return {"kind": kind, "min": int(quorum["min"])}
    raise TypeError(f"quorum must be None or dict, got {type(quorum)}")


def participating(
    ballots: Sequence[str], weights: Sequence[int], *, abstain: str = ABSTAIN
) -> tuple[list[int], int]:
    idx = [i for i, b in enumerate(ballots) if b != abstain]
    return idx, int(sum(weights[i] for i in idx))


def scores_for(
    ballots: Sequence[str],
    weights: Sequence[int],
    alternatives: Sequence[str],
    *,
    abstain: str = ABSTAIN,
) -> dict[str, int]:
    out = {a: 0 for a in alternatives}
    for ballot, weight in zip(ballots, weights):
        if ballot == abstain:
            continue
        if ballot not in out:
            raise ValueError(f"ballot {ballot!r} not in {list(alternatives)}")
        out[ballot] += int(weight)
    return out


def _meets_quorum(n_part: int, w_part: int, quorum: Mapping[str, Any]) -> bool:
    kind = quorum.get("kind")
    if kind == "none":
        return True
    minimum = int(quorum["min"])
    if kind == "count":
        return n_part >= minimum
    if kind == "weight":
        return w_part >= minimum
    raise ValueError(f"unknown quorum kind {kind!r}")


def _pick_threshold_winner(
    scores: Mapping[str, int],
    method: str,
    w_part: int,
    alternatives: Sequence[str],
) -> str:
    if w_part <= 0:
        return alternatives[0]
    if method == "majority":
        # Strict majority of participating weight; otherwise status quo / lex among tied max.
        best = max(scores[a] for a in alternatives)
        tied = [a for a in alternatives if scores[a] == best]
        if best * 2 > w_part and len(tied) == 1:
            return tied[0]
        return tied[0]
    if method == "supermajority":
        # >= 2/3 of participating weight, exact integer test 3*score >= 2*w_part.
        qualified = [a for a in alternatives if scores[a] * 3 >= 2 * w_part]
        if len(qualified) == 1:
            return qualified[0]
        return alternatives[0]
    if method == "unanimity":
        unanimous = [a for a in alternatives if scores[a] == w_part]
        if len(unanimous) == 1:
            return unanimous[0]
        return alternatives[0]
    raise ValueError(f"unknown method {method!r}")


def tally(
    ballots: Sequence[str],
    *,
    method: str,
    weights: Sequence[int],
    quorum: Any = None,
    alternatives: Sequence[str] = ALTERNATIVES,
    abstain: str = ABSTAIN,
) -> str:
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}")
    if len(ballots) != len(weights):
        raise ValueError("ballots and weights must be the same length")
    if not alternatives:
        raise ValueError("alternatives must be non-empty")
    q = _as_quorum(quorum)
    idx, w_part = participating(ballots, weights, abstain=abstain)
    if not _meets_quorum(len(idx), w_part, q):
        return QUORUM_FAIL
    scored = scores_for(ballots, weights, alternatives, abstain=abstain)
    return _pick_threshold_winner(scored, method, w_part, alternatives)


def config_key(method: str, quorum: Any, weights: Iterable[int]) -> str:
    q = _as_quorum(quorum)
    if q["kind"] == "none":
        qpart = "none"
    else:
        qpart = f"{q['kind']}:{q['min']}"
    wpart = ",".join(str(int(w)) for w in weights)
    return f"{method}|{qpart}|{wpart}"
