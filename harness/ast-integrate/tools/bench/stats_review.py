"""Independent statistics reviewer for the loop meta-benchmark (TST-0314).

Recounts KEEP rates, Wilson intervals, gate decisions and the KEEP-rate jump
directly from the raw decision records, without reading the series
fingerprint, so a hand-tallied series or a misapplied gate is caught by a
second code path.  Shares only the gate *definition* (``bench.metaloop.GATES``)
with the module under review.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from bench import metaloop as _m

TOLERANCE = 1e-12


def _gate_records(records: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [r for r in records if r.get("role") == "gate"]


def _wilson(k: int, n: int, z: float = _m.Z_975) -> tuple[float, float]:
    if n <= 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1.0 + z * z / n
    centre = (p + z * z / (2.0 * n)) / denom
    half = z * math.sqrt(p * (1.0 - p) / n + z * z / (4.0 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def series_keep_rates_agree(
    series: Mapping[str, Any], records: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Recount per-iteration KEEP rates (with Wilson intervals) and compare to the series."""
    gate_recs = _gate_records(records)
    declared = {int(r["iteration"]): r for r in (series.get("per_iteration") or [])}
    rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    iterations = sorted({int(r["iteration"]) for r in gate_recs})
    for iteration in iterations:
        decided = [r for r in gate_recs if int(r["iteration"]) == iteration]
        kept = sum(1 for r in decided if r.get("decision") == _m.KEEP)
        recount = kept / len(decided)
        low, high = _wilson(kept, len(decided))
        row = {
            "iteration": iteration,
            "k": kept,
            "n": len(decided),
            "keep_rate_recount": recount,
            "keep_rate_series": None,
            "wilson_low": low,
            "wilson_high": high,
        }
        series_row = declared.get(iteration)
        if series_row is None:
            mismatches.append({"iteration": iteration, "reason": "missing from series"})
        else:
            row["keep_rate_series"] = series_row.get("keep_rate")
            try:
                gap = abs(float(series_row.get("keep_rate")) - recount)
            except (TypeError, ValueError):
                gap = math.inf
            if gap > TOLERANCE:
                mismatches.append(
                    {"iteration": iteration, "series": series_row.get("keep_rate"), "recount": recount}
                )
        rows.append(row)
    for iteration in sorted(set(declared) - set(iterations)):
        mismatches.append({"iteration": iteration, "reason": "not in records"})
    return {
        "ok": not mismatches,
        "n_iterations": len(iterations),
        "per_iteration": rows,
        "mismatches": mismatches,
    }


def records_match_reapplied_gate(
    records: Sequence[Mapping[str, Any]], gate_name: str
) -> dict[str, Any]:
    """Re-apply ``gate_name`` to every gate record's raw cases; recorded fields must match."""
    mismatches: list[dict[str, Any]] = []
    checked = 0
    for rec in _gate_records(records):
        checked += 1
        raw = rec.get("raw_cases") or []
        mean, improved, n = _m.case_stats(raw)
        expected = _m.apply_gate(gate_name, raw)
        problems = []
        if rec.get("gate") != gate_name:
            problems.append(f"gate {rec.get('gate')!r} != {gate_name!r}")
        if rec.get("decision") != expected:
            problems.append(f"decision {rec.get('decision')!r} != reapplied {expected!r}")
        if abs(float(rec.get("mean_delta", 0.0)) - mean) > 1e-9:
            problems.append(f"mean_delta {rec.get('mean_delta')} != {mean}")
        if int(rec.get("improved_count", -1)) != improved:
            problems.append(f"improved_count {rec.get('improved_count')} != {improved}")
        if int(rec.get("n_cases", -1)) != n:
            problems.append(f"n_cases {rec.get('n_cases')} != {n}")
        if problems:
            mismatches.append({"record_id": rec.get("record_id"), "problems": problems})
    return {"ok": checked > 0 and not mismatches, "n_checked": checked, "mismatches": mismatches}


def reproduce_jump(
    records_a: Sequence[Mapping[str, Any]], records_b: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    """Independently recount the KEEP-rate jump, Cohen's h and the Newcombe interval."""
    a = _gate_records(records_a)
    b = _gate_records(records_b)
    k1 = sum(1 for r in a if r.get("decision") == _m.KEEP)
    k2 = sum(1 for r in b if r.get("decision") == _m.KEEP)
    n1, n2 = len(a), len(b)
    if n1 == 0 or n2 == 0:
        raise ValueError("both ledgers need at least one gate record")
    p1, p2 = k1 / n1, k2 / n2
    l1, u1 = _wilson(k1, n1)
    l2, u2 = _wilson(k2, n2)
    diff = p2 - p1
    return {
        "k_a": k1,
        "n_a": n1,
        "k_b": k2,
        "n_b": n2,
        "keep_rate_a": p1,
        "keep_rate_b": p2,
        "jump": diff,
        "effect_size_cohens_h": 2.0 * math.asin(math.sqrt(p2)) - 2.0 * math.asin(math.sqrt(p1)),
        "interval": {
            "low": diff - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2),
            "high": diff + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2),
            "alpha": _m.ALPHA,
            "method": _m.INTERVAL_METHOD,
        },
    }


__all__ = [
    "TOLERANCE",
    "records_match_reapplied_gate",
    "reproduce_jump",
    "series_keep_rates_agree",
]
