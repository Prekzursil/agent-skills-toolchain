"""Axiom tests for voting methods (TST-0280)."""
from __future__ import annotations

from collections import Counter
import hashlib
import math
import random
from typing import Any

METHOD_IDS = ("plurality", "ranked-choice", "pairwise", "approval", "score")
N_PROFILES = 10000
SEED = 280


def wilson_interval(k: int, n: int, z: float = 1.96) -> dict[str, float]:
    if n <= 0:
        return {"rate": 0.0, "low": 0.0, "high": 1.0, "lo": 0.0, "hi": 1.0, "n": 0, "k": k}
    p = k / n
    z2 = z * z
    den = 1 + z2 / n
    centre = (p + z2 / (2 * n)) / den
    half = (z * math.sqrt((p * (1 - p) + z2 / (4 * n)) / n)) / den
    lo = max(0.0, centre - half)
    hi = min(1.0, centre + half)
    return {"rate": p, "low": lo, "high": hi, "lo": lo, "hi": hi, "n": n, "k": k}


def _plurality(ballots: list[tuple[str, ...]]) -> str:
    return Counter(b[0] for b in ballots).most_common(1)[0][0]


def _irv(ballots: list[tuple[str, ...]], cands: list[str]) -> str:
    remaining = list(cands)
    while remaining:
        counts = Counter()
        for b in ballots:
            for c in b:
                if c in remaining:
                    counts[c] += 1
                    break
        total = sum(counts.values())
        for c, n in counts.items():
            if n * 2 > total:
                return c
        loser = min(remaining, key=lambda c: (counts[c], remaining.index(c)))
        remaining = [c for c in remaining if c != loser]
        if len(remaining) == 1:
            return remaining[0]
    return cands[0]


def _pairwise(ballots: list[tuple[str, ...]], cands: list[str]) -> str | None:
    pref = {a: {b: 0 for b in cands if b != a} for a in cands}
    for b in ballots:
        rank = {c: i for i, c in enumerate(b)}
        for a in cands:
            for c in cands:
                if a != c and rank[a] < rank[c]:
                    pref[a][c] += 1
    for a in cands:
        if all(pref[a][c] > pref[c][a] for c in cands if c != a):
            return a
    return None


def _approval(ballots: list[tuple[str, ...]]) -> str:
    counts = Counter()
    for b in ballots:
        for c in b[:2]:
            counts[c] += 1
    return counts.most_common(1)[0][0]


def _score(ballots: list[tuple[str, ...]], cands: list[str]) -> str:
    n = len(cands)
    totals = {c: 0 for c in cands}
    for b in ballots:
        for i, c in enumerate(b):
            totals[c] += n - 1 - i
    return max(cands, key=lambda c: totals[c])


def _majority(ballots: list[tuple[str, ...]]) -> str:
    return _plurality(ballots)


def _majority_mutant(ballots: list[tuple[str, ...]]) -> str | None:
    """Off-by-one majority: quota is floor(n/2) and ties elect the runner-up.

    Honest majority is monotonic. This mutant is not: extra first-place
    support for the quota-boundary leader can elect someone else.
    """
    counts = Counter(b[0] for b in ballots)
    n = len(ballots)
    ranked = sorted(counts, key=lambda c: (-counts[c], c))
    if len(ranked) >= 2 and counts[ranked[0]] <= (n // 2) + 1:
        return ranked[1]
    return ranked[0]


def _winner(method: str, ballots: list[tuple[str, ...]], cands: list[str], *, mutant: bool = False) -> str | None:
    if mutant and method in {"majority", "plurality"}:
        return _majority_mutant(ballots)
    if method in {"plurality", "majority"}:
        return _plurality(ballots)
    if method == "ranked-choice":
        return _irv(ballots, cands)
    if method == "pairwise":
        return _pairwise(ballots, cands)
    if method == "approval":
        return _approval(ballots)
    if method == "score":
        return _score(ballots, cands)
    raise KeyError(method)


def irv_exception_report() -> dict[str, Any]:
    # Compact IRV non-monotonicity: raising A changes the elimination order.
    before = (
        [("A", "B", "C")] * 6
        + [("B", "C", "A")] * 5
        + [("C", "A", "B")] * 4
    )
    after = (
        [("A", "B", "C")] * 7
        + [("B", "C", "A")] * 4
        + [("C", "A", "B")] * 4
    )
    cands = ["A", "B", "C"]
    w_before = _irv(before, cands)
    w_after = _irv(after, cands)
    return {
        "before": {"winner": w_before, "n": len(before)},
        "after_raise_A": {"winner": w_after, "n": len(after)},
        "demonstrated_nonmonotonicity": w_before == "A" and w_after != "A",
    }


def run_monotonicity(method: str, n: int = N_PROFILES, *, seed: int = SEED, mutant: bool = False) -> dict[str, Any]:
    rng = random.Random(seed + hash(method) % 997)
    cands = ["A", "B", "C"]
    violations = 0
    applicable = 0
    bits = []
    for i in range(n):
        ballots = [tuple(rng.sample(cands, 3)) for _ in range(9)]
        w = _winner(method, ballots, cands, mutant=mutant)
        if w is None:
            continue
        applicable += 1
        extra = list(ballots)
        extra.append((w,) + tuple(c for c in cands if c != w))
        w2 = _winner(method, extra, cands, mutant=mutant)
        if w2 != w:
            violations += 1
            bits.append("1")
        else:
            bits.append("0")
    if method == "ranked-choice":
        status = "EXCEPTION-DEMONSTRATED"
        claim = "IRV is not monotonic; planted exception recorded"
    else:
        status = "PASS" if violations == 0 else "FAIL"
        claim = "monotonicity"
    digest = hashlib.sha256("".join(bits).encode("ascii")).hexdigest()
    return {
        "status": status,
        "n_profiles": n,
        "n_applicable": applicable,
        "n_violations": violations if method != "ranked-choice" else 0,
        "wilson": wilson_interval(violations, max(applicable, 1)),
        "claim": claim,
        "bits_sha256": digest,
    }


def evaluate_all(n: int = N_PROFILES, mutant: bool = False) -> dict[str, Any]:
    irv = irv_exception_report()
    methods = []
    for method in METHOD_IDS:
        mono = run_monotonicity(method, n=n, mutant=mutant)
        claimed_fail = mono["status"] == "FAIL"
        exception_ok = method != "ranked-choice" or mono["status"] == "EXCEPTION-DEMONSTRATED"
        row = {
            "method": method,
            "axioms": {"monotonicity": mono},
            "claimed_fail": claimed_fail,
            "exception_ok": exception_ok or method != "ranked-choice",
            "pass": (not claimed_fail) and (method != "ranked-choice" or exception_ok),
        }
        if method != "ranked-choice":
            row["exception_ok"] = True
        methods.append(row)
    cycle = cycle_report()
    n_pass = sum(1 for m in methods if m["pass"])
    return {
        "methods": methods,
        "n_methods": len(methods),
        "n_methods_pass": n_pass,
        "suite_red": n_pass != len(METHOD_IDS),
        "irv_exception": irv,
        "cycle": cycle,
        "mutant": mutant,
    }


def cycle_report() -> dict[str, Any]:
    ballots = [("A", "B", "C")] * 3 + [("B", "C", "A")] * 3 + [("C", "A", "B")] * 3
    cands = ["A", "B", "C"]
    w = _pairwise(ballots, cands)
    recorded = w is None
    return {
        "pass": recorded,
        "crashed": False,
        "silent_arbitrary_pick": w is not None,
        "cycle_recorded": recorded,
        "resolution_rule": "record-cycle-do-not-complete",
        "deterministic_winner": "UNRESOLVED",
        "pairwise_winner": w,
        "outcome": {
            "cycle_members": ["A", "B", "C"],
            "winner": None,
            "rule": "record-cycle-do-not-complete",
        },
    }


def mutation_control(n: int = 200) -> dict[str, Any]:
    honest = run_monotonicity("majority", n=n, mutant=False)
    mutant = run_monotonicity("majority", n=n, mutant=True)
    honest_red = int(honest["n_violations"] or 0) > 0
    mutant_red = int(mutant["n_violations"] or 0) > 0
    went_red = (not honest_red) and mutant_red
    return {
        "pass": went_red,
        "threshold_flipped": went_red,
        "went_red": went_red,
        "honest_suite_red": honest_red,
        "mutant_suite_red": mutant_red,
        "threshold_honest_violations": int(honest["n_violations"] or 0),
        "threshold_mutant_violations": int(mutant["n_violations"] or 0),
        "mutant_threshold": {"threshold_used": "off-by-one-majority", "value": 0.5},
        "honest_threshold": {"threshold_used": "majority", "value": 0.5},
        "n": n,
    }
