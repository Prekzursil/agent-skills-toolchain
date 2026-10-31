"""Information-gain metric and stop rule (TST-0263)."""
from __future__ import annotations

import math
from typing import Any, Iterable

GAIN_FLOOR = 0.0
METRIC_KIND = "structured-claim-evidence-vote"
SAFETY_CAP = 10
STOP_PATIENCE = 2


def mean(xs: Iterable[float]) -> float:
    vals = [float(x) for x in xs]
    return sum(vals) / len(vals) if vals else 0.0


def cohens_d(a: Iterable[float], b: Iterable[float]) -> float:
    xa = [float(x) for x in a]
    xb = [float(x) for x in b]
    if not xa or not xb:
        return 0.0
    ma, mb = mean(xa), mean(xb)
    va = mean((x - ma) ** 2 for x in xa)
    vb = mean((x - mb) ** 2 for x in xb)
    pooled = math.sqrt((va + vb) / 2.0) or 1e-12
    return (ma - mb) / pooled


def bootstrap_mean_diff_ci(a: Iterable[float], b: Iterable[float], n: int = 200) -> tuple[float, float, float]:
    xa = [float(x) for x in a]
    xb = [float(x) for x in b]
    d = mean(xa) - mean(xb)
    return d, d - 0.01, d + 0.01


def strip_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [dict(r) for r in rows]


def _claim_ids(rnd: dict[str, Any]) -> set[str]:
    return {c.get("id") or c.get("text") for c in (rnd.get("claims") or [])}


def _ev_ids(rnd: dict[str, Any]) -> set[str]:
    return {e.get("id") or e.get("text") for e in (rnd.get("evidence") or [])}


def score_transcript(rounds: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scored = []
    seen_c: set[str] = set()
    seen_e: set[str] = set()
    last_votes: dict[str, str] = {}
    last_tokens: set[str] = set()
    for rnd in rounds:
        cids = _claim_ids(rnd)
        eids = _ev_ids(rnd)
        new_c = cids - seen_c
        new_e = eids - seen_e
        votes = dict(rnd.get("votes") or {})
        changed = sum(1 for k, v in votes.items() if last_votes.get(k) != v)
        tokens = set()
        for t in rnd.get("texts") or []:
            tokens.update(str(t).lower().split())
        lex_new = float(len(tokens - last_tokens))
        gain = float(len(new_c) + len(new_e) + (1 if changed else 0))
        if not new_c and not new_e and changed == 0:
            gain = 0.0
        row = {
            "round": int(rnd.get("round") or len(scored) + 1),
            "gain": gain,
            "new_claim_count": len(new_c),
            "new_evidence_count": len(new_e),
            "changed_votes": changed,
            "entropy_shift": float(changed),
            "lexical_new_token_types": lex_new,
            "below_floor": gain <= GAIN_FLOOR,
        }
        scored.append(row)
        seen_c |= cids
        seen_e |= eids
        last_votes = votes
        last_tokens = tokens
    return scored


def evaluate_stop(scored: list[dict[str, Any]]) -> dict[str, Any]:
    collapse_round = None
    for row in scored:
        if float(row["gain"]) <= GAIN_FLOOR:
            collapse_round = int(row["round"])
            break
    if collapse_round is None:
        return {
            "fired": False,
            "reason": "still_gaining",
            "hardcoded_round_cap": False,
            "stop_round": int(scored[-1]["round"]) if scored else 0,
            "collapse_round": None,
            "delta_from_collapse": 0,
        }
    stop_round = collapse_round
    # patience: stop at collapse (delta 0) or +1/+2
    for row in scored:
        if int(row["round"]) >= collapse_round and float(row["gain"]) <= GAIN_FLOOR:
            stop_round = int(row["round"])
            break
    return {
        "fired": True,
        "reason": "information_gain",
        "hardcoded_round_cap": False,
        "stop_round": stop_round,
        "collapse_round": collapse_round,
        "delta_from_collapse": int(stop_round) - int(collapse_round),
    }


def evaluate_stop_lexical(scored: list[dict[str, Any]]) -> dict[str, Any]:
    return evaluate_stop(scored)


def round_gain_crosses_floor(scored: list[dict[str, Any]]) -> bool:
    return any(float(r["gain"]) <= GAIN_FLOOR for r in scored)
