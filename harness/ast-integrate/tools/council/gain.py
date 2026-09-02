"""Information-gain metric and stop rule (TST-0263)."""
from __future__ import annotations

import math
import random
from typing import Any, Iterable

GAIN_FLOOR = 0.0
METRIC_KIND = "structured-identity"
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


BOOTSTRAP_N = 2000
BOOTSTRAP_ALPHA = 0.05


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear-interpolated percentile of an already sorted sample, q in [0, 1]."""
    if not sorted_vals:
        return 0.0
    pos = q * (len(sorted_vals) - 1)
    lo_i = int(math.floor(pos))
    hi_i = min(lo_i + 1, len(sorted_vals) - 1)
    frac = pos - lo_i
    return sorted_vals[lo_i] + (sorted_vals[hi_i] - sorted_vals[lo_i]) * frac


def bootstrap_mean_diff_ci(
    a: Iterable[float],
    b: Iterable[float],
    rng: "random.Random | int | None" = None,
    *,
    n_resamples: int = BOOTSTRAP_N,
    alpha: float = BOOTSTRAP_ALPHA,
) -> tuple[float, float]:
    """Percentile bootstrap interval for ``mean(a) - mean(b)``.

    ``rng`` is the caller's seeded :class:`random.Random` (or an int seed) so an
    independent recompute with the same seed reproduces the interval bit-for-bit.
    Returns ``(low, high)`` at the ``1 - alpha`` level.
    """
    xa = [float(x) for x in a]
    xb = [float(x) for x in b]
    if not xa or not xb:
        raise ValueError("bootstrap_mean_diff_ci: both samples must be non-empty")
    if isinstance(rng, int) or rng is None:
        rng = random.Random(0 if rng is None else rng)
    diffs: list[float] = []
    for _ in range(int(n_resamples)):
        ra = [rng.choice(xa) for _ in xa]
        rb = [rng.choice(xb) for _ in xb]
        diffs.append(mean(ra) - mean(rb))
    diffs.sort()
    return _percentile(diffs, alpha / 2.0), _percentile(diffs, 1.0 - alpha / 2.0)


SCORE_KEYS = (
    "gain",
    "new_claim_count",
    "new_evidence_count",
    "changed_votes",
    "entropy_shift",
    "lexical_new_token_types",
    "below_floor",
)


def strip_scores(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return the raw transcript rounds with every score field removed, so an
    independent :func:`score_transcript` pass can rescore them from scratch."""
    return [{k: v for k, v in r.items() if k not in SCORE_KEYS} for r in rows]


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
        row = dict(rnd)
        row.update({
            "round": int(rnd.get("round") or len(scored) + 1),
            "gain": gain,
            "new_claim_count": len(new_c),
            "new_evidence_count": len(new_e),
            "changed_votes": changed,
            "entropy_shift": float(changed),
            "lexical_new_token_types": lex_new,
            "below_floor": gain <= GAIN_FLOOR,
        })
        scored.append(row)
        seen_c |= cids
        seen_e |= eids
        last_votes = votes
        last_tokens = tokens
    return scored


def _evaluate_stop_on(scored: list[dict[str, Any]], key: str, *, patience: int = STOP_PATIENCE) -> dict[str, Any]:
    """Generic floor-collapse stop rule over ``row[key]``.

    The rule fires once the metric has sat at or below :data:`GAIN_FLOOR` for
    ``patience`` consecutive rounds after the first collapse round (a single flat
    round is not a stop). It never consults a round count: ``hardcoded_round_cap``
    is always False and :data:`SAFETY_CAP` is reported for the harness only.
    """
    collapse_round: int | None = None
    flat = 0
    stop_round: int | None = None
    for row in scored:
        value = float(row.get(key, 0.0))
        if value <= GAIN_FLOOR:
            if collapse_round is None:
                collapse_round = int(row["round"])
            flat += 1
            if flat >= patience and stop_round is None:
                stop_round = int(row["round"])
        else:
            collapse_round = None
            flat = 0
    if stop_round is None:
        return {
            "fired": False,
            "reason": "still_gaining",
            "metric": key,
            "hardcoded_round_cap": False,
            "stop_round": int(scored[-1]["round"]) if scored else 0,
            "collapse_round": collapse_round,
            "delta_from_collapse": None,
            "within_patience": None,
            "patience": patience,
        }
    delta = int(stop_round) - int(collapse_round or stop_round)
    return {
        "fired": True,
        "reason": "information_gain",
        "metric": key,
        "hardcoded_round_cap": False,
        "stop_round": int(stop_round),
        "collapse_round": int(collapse_round or stop_round),
        "delta_from_collapse": delta,
        "within_patience": delta <= patience,
        "patience": patience,
    }


def evaluate_stop(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Structured-identity stop: fires when new claims, new evidence and vote
    changes have all collapsed to zero for :data:`STOP_PATIENCE` rounds."""
    return _evaluate_stop_on(scored, "gain")


def evaluate_stop_lexical(scored: list[dict[str, Any]]) -> dict[str, Any]:
    """Lexical control: the same rule over new token types. A paraphrase keeps
    producing new wording, so this evaluator stays silent where the structured
    rule fires — that gap is what proves the metric is not lexical."""
    return _evaluate_stop_on(scored, "lexical_new_token_types")


def round_gain_crosses_floor(scored: list[dict[str, Any]]) -> bool:
    return any(float(r["gain"]) <= GAIN_FLOOR for r in scored)
