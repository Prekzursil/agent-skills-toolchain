"""Meta-benchmark of the improvement loop: metric series from decision records (TST-0314).

The improvement loop proposes candidates each iteration; a *gate* decides
KEEP / REVERT / INSUFFICIENT-EVIDENCE from the candidate's per-case results.
Every decision is an append-only JSONL record.  This module

* generates deterministic synthetic candidates (``generate_candidates``) and
  gates them into a decision ledger (``ledger_from_candidates``), optionally in
  a *degrading* regime where kept candidates are reverted later
  (``role == "post_keep_revert"`` records);
* computes the loop metric series **from the records** (``series_from_records``):
  per-iteration KEEP rate, post-KEEP regression rate, iterations per accepted
  improvement and mean time to revert, with a content fingerprint so a
  hand-tallied or edited series is detectable (``verify_series``);
* raises the post-KEEP regression alarm (``detect_degradation``: early/late
  half delta plus Mann-Kendall trend) and detects a KEEP-rate jump between two
  ledgers (``detect_keep_rate_jump``: Cohen's h and a Newcombe-Wilson method 10
  interval for the difference of proportions).

Fewer than ``MIN_ITERATIONS`` iterations is ``NOT-CHECKED``: no trend claim is
made from a single iteration.  Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = 1
MIN_ITERATIONS = 5
KEEP = "KEEP"
REVERT = "REVERT"
INSUFFICIENT = "INSUFFICIENT-EVIDENCE"
DECISIONS = (KEEP, REVERT, INSUFFICIENT)
SOURCE = "decision-records"

# Pre-registered floors (mirrors probes/TST-0314/fixtures/preregistered_thresholds.json).
KEEP_RATE_JUMP_MIN = 0.15
COHENS_H_JUMP_MIN = 0.4
POST_KEEP_REGRESSION_DELTA_MIN = 0.2
ALPHA = 0.05
Z_975 = 1.959963984540054
INTERVAL_METHOD = "newcombe-wilson-method-10"

# A per-case delta must clear this to count as an improvement (noise floor).
CASE_IMPROVEMENT_MIN = 0.01

GATES: dict[str, dict[str, float]] = {
    # KEEP needs a clear mean gain on most cases; REVERT on a clear mean loss;
    # everything in between is INSUFFICIENT-EVIDENCE.
    "strict": {
        "keep_min_mean_delta": 0.05,
        "keep_min_improved_fraction": 0.75,
        "revert_max_mean_delta": -0.05,
    },
    # Deliberately permissive control: anything not clearly worse is kept.
    "permissive": {
        "keep_min_mean_delta": -0.05,
        "keep_min_improved_fraction": 0.0,
        "revert_max_mean_delta": -0.05,
    },
}

_KIND_SHIFT = {"improve": 0.16, "noop": 0.0, "regress": -0.14}
_KIND_MIX: tuple[tuple[str, int], ...] = (("improve", 3), ("noop", 3), ("regress", 4))


# ----------------------------------------------------------------- candidates + gate

def generate_candidates(
    n_iterations: int, seed: str | int, n_cases: int = 12
) -> list[dict[str, Any]]:
    """Deterministic synthetic candidates: per iteration 3 improve, 3 noop, 4 regress.

    Each candidate carries ``raw_cases`` (baseline ~0.5, after = baseline + kind
    shift + noise) so any gate can be re-applied from the raw per-case results.
    """
    if n_iterations < 1:
        raise ValueError("n_iterations must be >= 1")
    rng = random.Random(str(seed))
    out: list[dict[str, Any]] = []
    for iteration in range(1, n_iterations + 1):
        index = 0
        for kind, count in _KIND_MIX:
            for _ in range(count):
                cases = []
                for case in range(n_cases):
                    baseline = round(0.5 + rng.uniform(-0.01, 0.01), 6)
                    shift = _KIND_SHIFT[kind] + rng.uniform(-0.009, 0.009)
                    cases.append(
                        {
                            "after": round(baseline + shift, 6),
                            "baseline": baseline,
                            "case_id": f"case-{iteration}-{index}-{case}",
                        }
                    )
                out.append(
                    {
                        "candidate_id": f"cand-{iteration}-{index}",
                        "iteration": iteration,
                        "kind": kind,
                        "n_cases": n_cases,
                        "raw_cases": cases,
                    }
                )
                index += 1
    return out


def case_stats(raw_cases: Sequence[Mapping[str, Any]]) -> tuple[float, int, int]:
    """Return (mean_delta rounded to 6 dp, improved_count, n_cases) from per-case results."""
    deltas = [float(c["after"]) - float(c["baseline"]) for c in raw_cases]
    n = len(deltas)
    mean = round(sum(deltas) / n, 6) if n else 0.0
    improved = sum(1 for d in deltas if d > CASE_IMPROVEMENT_MIN)
    return mean, improved, n


def apply_gate(gate_name: str, raw_cases: Sequence[Mapping[str, Any]]) -> str:
    """Re-apply a named gate to raw per-case results and return the decision."""
    if gate_name not in GATES:
        raise KeyError(f"unknown gate {gate_name!r}")
    rule = GATES[gate_name]
    mean, improved, n = case_stats(raw_cases)
    needed = math.ceil(rule["keep_min_improved_fraction"] * n)
    if mean > rule["keep_min_mean_delta"] and improved >= needed:
        return KEEP
    if mean < rule["revert_max_mean_delta"]:
        return REVERT
    return INSUFFICIENT


def _revert_schedule(iteration: int, n_iterations: int, n_keeps: int, mode: str) -> int:
    if mode == "stable" or n_keeps == 0:
        return 0
    if mode == "degrading":
        if n_iterations <= 1:
            return 0
        return int(round((iteration - 1) / (n_iterations - 1) * n_keeps))
    raise ValueError(f"unknown revert_mode {mode!r}")


def ledger_from_candidates(
    candidates: Sequence[Mapping[str, Any]],
    gate_name: str = "strict",
    revert_mode: str = "stable",
) -> list[dict[str, Any]]:
    """Gate every candidate into decision records; ``degrading`` adds rising post-KEEP reverts."""
    if gate_name not in GATES:
        raise KeyError(f"unknown gate {gate_name!r}")
    if revert_mode not in ("stable", "degrading"):
        raise ValueError(f"unknown revert_mode {revert_mode!r}")
    iterations = sorted({int(c["iteration"]) for c in candidates})
    n_iterations = len(iterations)
    records: list[dict[str, Any]] = []
    for iteration in iterations:
        kept: list[dict[str, Any]] = []
        for cand in candidates:
            if int(cand["iteration"]) != iteration:
                continue
            raw = list(cand["raw_cases"])
            mean, improved, n = case_stats(raw)
            decision = apply_gate(gate_name, raw)
            record = {
                "candidate_id": str(cand["candidate_id"]),
                "decided_at_epoch": float(iteration * 1000),
                "decision": decision,
                "gate": gate_name,
                "improved_count": improved,
                "iteration": iteration,
                "keep_record_id": None,
                "kind": str(cand.get("kind") or "unknown"),
                "mean_delta": mean,
                "n_cases": n,
                "raw_cases": raw,
                "record_id": f"gate-{gate_name}-{cand['candidate_id']}",
                "role": "gate",
                "schema_version": SCHEMA_VERSION,
            }
            records.append(record)
            if decision == KEEP:
                kept.append(record)
        n_reverts = _revert_schedule(iteration, n_iterations, len(kept), revert_mode)
        for keep_rec in kept[:n_reverts]:
            records.append(
                {
                    "candidate_id": keep_rec["candidate_id"],
                    "decided_at_epoch": keep_rec["decided_at_epoch"] + 500.0,
                    "decision": REVERT,
                    "gate": gate_name,
                    "improved_count": 0,
                    "iteration": iteration,
                    "keep_record_id": keep_rec["record_id"],
                    "kind": keep_rec["kind"],
                    "mean_delta": round(-abs(float(keep_rec["mean_delta"])) / 2.0, 6),
                    "n_cases": keep_rec["n_cases"],
                    "raw_cases": [],
                    "record_id": f"post-keep-revert-{gate_name}-{keep_rec['candidate_id']}",
                    "role": "post_keep_revert",
                    "schema_version": SCHEMA_VERSION,
                }
            )
    return records


# ----------------------------------------------------------------- JSONL persistence

def write_records(path: str | Path, records: Iterable[Mapping[str, Any]]) -> Path:
    """Write records as canonical JSONL (one sorted-key object per line)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(dict(r), sort_keys=True, separators=(",", ":")) for r in records]
    target.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return target


def load_records(path: str | Path) -> list[dict[str, Any]]:
    """Load a JSONL ledger; blank lines are ignored, malformed lines raise."""
    out: list[dict[str, Any]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        if not isinstance(rec, dict):
            raise ValueError(f"{path}:{number}: record is not an object")
        out.append(rec)
    return out


# ----------------------------------------------------------------- series

def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _fingerprint(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _series_rows(records: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    gate_recs = [r for r in records if r.get("role") == "gate"]
    reverts = [r for r in records if r.get("role") == "post_keep_revert"]
    by_id = {r.get("record_id"): r for r in gate_recs}
    rows: list[dict[str, Any]] = []
    cumulative_keeps = 0
    for position, iteration in enumerate(sorted({int(r["iteration"]) for r in gate_recs}), 1):
        decided = [r for r in gate_recs if int(r["iteration"]) == iteration]
        keeps = [r for r in decided if r.get("decision") == KEEP]
        n_revert = sum(1 for r in decided if r.get("decision") == REVERT)
        n_insufficient = sum(1 for r in decided if r.get("decision") == INSUFFICIENT)
        post = [r for r in reverts if int(r.get("iteration", -1)) == iteration]
        cumulative_keeps += len(keeps)
        times = []
        for rev in post:
            keep_rec = by_id.get(rev.get("keep_record_id"))
            if keep_rec is not None:
                times.append(float(rev["decided_at_epoch"]) - float(keep_rec["decided_at_epoch"]))
        rows.append(
            {
                "iteration": iteration,
                "iterations_per_accepted_improvement": (
                    position / cumulative_keeps if cumulative_keeps else None
                ),
                "keep_rate": len(keeps) / len(decided) if decided else 0.0,
                "mean_time_to_revert": _mean(times) if times else None,
                "n_decisions": len(decided),
                "n_insufficient_evidence": n_insufficient,
                "n_keep": len(keeps),
                "n_post_keep_revert": len(post),
                "n_revert": n_revert,
                "post_keep_regression_rate": len(post) / len(keeps) if keeps else 0.0,
            }
        )
    return rows, len(gate_recs)


def series_from_records(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Per-iteration loop metrics computed from gate decision records."""
    rows, n_gate = _series_rows(records)
    n_iterations = len(rows)
    checked = n_iterations >= MIN_ITERATIONS
    series: dict[str, Any] = {
        "checked": checked,
        "fingerprint": _fingerprint({"n_gate_records": n_gate, "per_iteration": rows}),
        "metrics": [
            "keep_rate",
            "post_keep_regression_rate",
            "iterations_per_accepted_improvement",
            "mean_time_to_revert",
        ],
        "min_iterations": MIN_ITERATIONS,
        "n_gate_records": n_gate,
        "n_iterations": n_iterations,
        "per_iteration": rows,
        "source": SOURCE,
        "status": "CHECKED" if checked else "NOT-CHECKED",
    }
    if not checked:
        series["reason"] = (
            f"{n_iterations} iteration(s) < {MIN_ITERATIONS}: no trend claim is made"
        )
    return series


def verify_series(series: Mapping[str, Any], records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Recompute the series from records; any divergence marks it hand-tallied."""
    expected = series_from_records(records)
    declared_rows = list(series.get("per_iteration") or [])
    mismatched: list[int] = []
    for exp_row in expected["per_iteration"]:
        match = next(
            (r for r in declared_rows if r.get("iteration") == exp_row["iteration"]), None
        )
        if match is None or any(match.get(k) != v for k, v in exp_row.items()):
            mismatched.append(int(exp_row["iteration"]))
    extra = [
        r.get("iteration")
        for r in declared_rows
        if r.get("iteration") not in {x["iteration"] for x in expected["per_iteration"]}
    ]
    fingerprint_ok = series.get("fingerprint") == expected["fingerprint"]
    ok = fingerprint_ok and not mismatched and not extra and series.get("source") == SOURCE
    return {
        "ok": ok,
        "hand_tallied": not ok,
        "declared_fingerprint": series.get("fingerprint"),
        "expected_fingerprint": expected["fingerprint"],
        "fingerprint_matches": fingerprint_ok,
        "mismatched_iterations": mismatched,
        "unexpected_iterations": extra,
    }


# ----------------------------------------------------------------- alarms

def mann_kendall_s(values: Sequence[float]) -> dict[str, Any]:
    """Mann-Kendall S statistic (sum of pairwise signs) with its trend direction."""
    s = 0
    n = len(values)
    for i in range(n):
        for j in range(i + 1, n):
            diff = values[j] - values[i]
            s += (diff > 0) - (diff < 0)
    return {"s": s, "n": n, "direction": "rising" if s > 0 else "falling" if s < 0 else "flat"}


def detect_degradation(series: Mapping[str, Any]) -> dict[str, Any]:
    """Post-KEEP regression alarm: late-half mean minus early-half mean and a rising trend."""
    rows = list(series.get("per_iteration") or [])
    base = {
        "metric": "post_keep_regression_rate",
        "delta_min": POST_KEEP_REGRESSION_DELTA_MIN,
        "n_iterations": len(rows),
    }
    if series.get("status") != "CHECKED" or len(rows) < MIN_ITERATIONS:
        return {
            **base,
            "status": "NOT-CHECKED",
            "fired": False,
            "alarm": None,
            "delta": 0.0,
            "early_mean": None,
            "late_mean": None,
            "mann_kendall": {"s": 0, "n": len(rows), "direction": "flat"},
            "reason": series.get("reason") or "series is not CHECKED",
        }
    rates = [float(r.get("post_keep_regression_rate") or 0.0) for r in rows]
    half = len(rates) // 2
    early, late = rates[:half], rates[half:]
    delta = _mean(late) - _mean(early)
    trend = mann_kendall_s(rates)
    fired = delta >= POST_KEEP_REGRESSION_DELTA_MIN and trend["s"] > 0
    return {
        **base,
        "status": "CHECKED",
        "fired": fired,
        "alarm": "post-KEEP-regression-rate" if fired else None,
        "delta": delta,
        "early_mean": _mean(early),
        "late_mean": _mean(late),
        "mann_kendall": trend,
        "series": rates,
    }


def wilson_interval(k: int, n: int, z: float = Z_975) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def newcombe_interval(k1: int, n1: int, k2: int, n2: int, z: float = Z_975) -> dict[str, float]:
    """Newcombe (1998) method 10 interval for p2 - p1 from two Wilson intervals."""
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = wilson_interval(k1, n1, z)
    l2, u2 = wilson_interval(k2, n2, z)
    diff = p2 - p1
    return {
        "low": diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
        "high": diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2),
    }


def cohens_h(p1: float, p2: float) -> float:
    """Cohen's h effect size between two proportions (p2 relative to p1)."""
    return 2.0 * math.asin(math.sqrt(p2)) - 2.0 * math.asin(math.sqrt(p1))


def keep_counts(records: Sequence[Mapping[str, Any]]) -> tuple[int, int]:
    """(kept, decided) over gate records."""
    gate_recs = [r for r in records if r.get("role") == "gate"]
    return sum(1 for r in gate_recs if r.get("decision") == KEEP), len(gate_recs)


def detect_keep_rate_jump(
    strict_records: Sequence[Mapping[str, Any]],
    permissive_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Detect a KEEP-rate jump of the second ledger over the first (degradation control)."""
    k1, n1 = keep_counts(strict_records)
    k2, n2 = keep_counts(permissive_records)
    if n1 == 0 or n2 == 0:
        raise ValueError("both ledgers need at least one gate record")
    p1, p2 = k1 / n1, k2 / n2
    jump = p2 - p1
    h = cohens_h(p1, p2)
    interval = newcombe_interval(k1, n1, k2, n2)
    excludes_zero = interval["low"] > 0.0 or interval["high"] < 0.0
    fired = jump >= KEEP_RATE_JUMP_MIN and h >= COHENS_H_JUMP_MIN and excludes_zero
    return {
        "fired": fired,
        "alarm": "keep-rate-jump" if fired else None,
        "keep_rate_strict": p1,
        "keep_rate_permissive": p2,
        "k_strict": k1,
        "n_strict": n1,
        "k_permissive": k2,
        "n_permissive": n2,
        "jump": jump,
        "jump_min": KEEP_RATE_JUMP_MIN,
        "cohens_h": h,
        "cohens_h_min": COHENS_H_JUMP_MIN,
        "interval": {**interval, "alpha": ALPHA, "method": INTERVAL_METHOD},
        "ci_excludes_zero": excludes_zero,
    }


__all__ = [
    "ALPHA",
    "COHENS_H_JUMP_MIN",
    "DECISIONS",
    "GATES",
    "INSUFFICIENT",
    "KEEP",
    "KEEP_RATE_JUMP_MIN",
    "MIN_ITERATIONS",
    "POST_KEEP_REGRESSION_DELTA_MIN",
    "REVERT",
    "SOURCE",
    "apply_gate",
    "case_stats",
    "cohens_h",
    "detect_degradation",
    "detect_keep_rate_jump",
    "generate_candidates",
    "keep_counts",
    "ledger_from_candidates",
    "load_records",
    "mann_kendall_s",
    "newcombe_interval",
    "series_from_records",
    "verify_series",
    "wilson_interval",
    "write_records",
]
