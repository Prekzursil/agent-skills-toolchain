#!/usr/bin/env python3
"""Recompute claimed metrics from raw repetition files only.

Never opens an implementer table. Claimed numbers are passed in by the
caller for comparison after the raw recompute has already run.
"""
from __future__ import annotations

import inspect
import json
import statistics
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
THIS = Path(__file__).resolve()
REL = "command-center/p2-wave/probes/CNF-0033/recompute.py"
AGREE_EPS = 1e-12


def file_line(fn) -> str:
    return f"{REL}:{inspect.getsourcelines(fn)[1]}"


def load_repetitions(path: Path) -> list[float]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"raw file is not an object: {path}")
    reps = doc.get("repetitions")
    if not isinstance(reps, list) or not reps:
        raise ValueError(f"raw file missing repetitions: {path}")
    out: list[float] = []
    for item in reps:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"non-numeric repetition in {path}: {item!r}")
        out.append(float(item))
    return out


def median_statistics(values: list[float]) -> float:
    return float(statistics.median(values))


def median_middle_index(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        raise ValueError("empty sample")
    if n % 2 == 1:
        return float(ordered[n // 2])
    return (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0


def iqr_quantiles_inclusive(values: list[float]) -> float:
    q1, _q2, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return float(q3) - float(q1)


def iqr_linear_percentile(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n < 2:
        raise ValueError("IQR needs n>=2")

    def at(p: float) -> float:
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

    return at(0.75) - at(0.25)


def two_way_median(values: list[float]) -> dict[str, Any]:
    a = median_statistics(values)
    b = median_middle_index(values)
    return {
        "metric_id": "two-way-median",
        "method_a": {
            "name": "statistics.median",
            "value": a,
            "file_line": file_line(median_statistics),
        },
        "method_b": {
            "name": "odd_n_middle_index",
            "value": b,
            "file_line": file_line(median_middle_index),
        },
        "agree": abs(a - b) <= AGREE_EPS,
        "delta": a - b,
    }


def two_way_iqr(values: list[float]) -> dict[str, Any]:
    a = iqr_quantiles_inclusive(values)
    b = iqr_linear_percentile(values)
    return {
        "metric_id": "two-way-iqr",
        "method_a": {
            "name": "statistics.quantiles_inclusive",
            "value": a,
            "file_line": file_line(iqr_quantiles_inclusive),
        },
        "method_b": {
            "name": "linear_percentile",
            "value": b,
            "file_line": file_line(iqr_linear_percentile),
        },
        "agree": abs(a - b) <= AGREE_EPS,
        "delta": a - b,
    }


def round_to(value: float, decimals: int) -> float:
    return float(round(value, decimals))


def evaluate(
    *,
    claim_id: str,
    source: str,
    raw_rel: str,
    claimed_value: float | None,
    claimed_delta: float | None,
    precision_decimals: int,
    noise_floor: float | None,
    noise_floor_file: str,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Recompute from raw_rel. Missing file => NOT-CHECKED, never MATCH."""
    raw_rel = raw_rel.replace("\\", "/")
    path = repo / raw_rel
    script = file_line(evaluate)
    base = {
        "id": claim_id,
        "source": source,
        "raw_file": raw_rel,
        "precision_decimals": precision_decimals,
        "recompute_script": script,
        "claimed_value": claimed_value,
        "claimed_delta": claimed_delta,
    }
    if not path.is_file() or path.stat().st_size <= 0:
        return {
            **base,
            "verdict": "NOT-CHECKED",
            "classification": "missing-raw-data",
            "missing_raw_file": raw_rel,
            "recomputed_value": None,
            "delta": None,
            "precision_match": None,
            "noise_floor_status": "NOT-CHECKED",
            "noise_floor_missing_file": (
                raw_rel if not path.is_file() else noise_floor_file
            ),
        }

    values = load_repetitions(path)
    recomputed = median_statistics(values)
    tw = two_way_median(values)
    if not tw["agree"]:
        raise ValueError(f"two-way median disagreement on {raw_rel}: {tw}")

    # Level claims (no claimed improvement delta): compare value only.
    # Noise-floor downgrade applies to deltas, never to a matching level.
    if claimed_value is not None:
        delta = recomputed - float(claimed_value)
    else:
        delta = None
    if claimed_delta is not None:
        delta_for_floor = abs(float(delta if delta is not None else claimed_delta))
    else:
        delta_for_floor = None

    precision_match: bool | None
    if claimed_value is None:
        precision_match = None
    else:
        precision_match = round_to(recomputed, precision_decimals) == round_to(
            float(claimed_value), precision_decimals
        )

    noise_status = "NOT-CHECKED"
    noise_missing = noise_floor_file
    if noise_floor is None:
        noise_status = "NOT-CHECKED"
    elif delta_for_floor is None:
        noise_status = "NOT-APPLICABLE"
        noise_missing = None
    elif delta_for_floor <= float(noise_floor):
        noise_status = "INSIDE"
        noise_missing = None
    else:
        noise_status = "EXCEEDS"
        noise_missing = None

    if noise_status == "INSIDE":
        verdict = "UNMEASURABLE"
        classification = "noise-dominated-claim"
    elif precision_match is True:
        verdict = "MATCH"
        classification = "confirmed"
    elif precision_match is False:
        verdict = "MISMATCH"
        classification = "overclaim"
    else:
        verdict = "MATCH"
        classification = "confirmed"

    out = {
        **base,
        "verdict": verdict,
        "classification": classification,
        "recomputed_value": recomputed,
        "delta": delta if delta is not None else (
            0.0 if claimed_value is None else recomputed - float(claimed_value)
        ),
        "precision_match": precision_match,
        "noise_floor_status": noise_status,
        "n": len(values),
        "raw_repetitions": values,
        "two_way_median_agree": tw["agree"],
    }
    if noise_missing:
        out["noise_floor_missing_file"] = noise_missing
    if verdict == "UNMEASURABLE":
        out["noise_floor_numeric"] = float(noise_floor) if noise_floor is not None else None
    return out


def evaluate_delta(
    *,
    claim_id: str,
    source: str,
    before_rel: str,
    after_rel: str,
    claimed_value: float | None,
    claimed_delta: float | None,
    precision_decimals: int,
    noise_floor: float | None,
    noise_floor_file: str,
    repo: Path = REPO,
) -> dict[str, Any]:
    """Recompute an improvement delta from before/after raw files."""
    before_rel = before_rel.replace("\\", "/")
    after_rel = after_rel.replace("\\", "/")
    before_p = repo / before_rel
    after_p = repo / after_rel
    script = file_line(evaluate_delta)
    base = {
        "id": claim_id,
        "source": source,
        "raw_file": after_rel,
        "baseline_raw_file": before_rel,
        "precision_decimals": precision_decimals,
        "recompute_script": script,
        "claimed_value": claimed_value,
        "claimed_delta": claimed_delta,
    }
    missing = None
    if not before_p.is_file() or before_p.stat().st_size <= 0:
        missing = before_rel
    elif not after_p.is_file() or after_p.stat().st_size <= 0:
        missing = after_rel
    if missing:
        return {
            **base,
            "verdict": "NOT-CHECKED",
            "classification": "missing-raw-data",
            "missing_raw_file": missing,
            "recomputed_value": None,
            "delta": None,
            "precision_match": None,
            "noise_floor_status": "NOT-CHECKED",
            "noise_floor_missing_file": missing,
        }

    before = load_repetitions(before_p)
    after = load_repetitions(after_p)
    before_med = median_statistics(before)
    after_med = median_statistics(after)
    recomputed_delta = after_med - before_med
    tw_a = two_way_median(after)
    tw_b = two_way_median(before)
    if not tw_a["agree"] or not tw_b["agree"]:
        raise ValueError("two-way median disagreement on delta pair")

    claimed_after = claimed_value
    precision_match: bool | None
    if claimed_after is None:
        precision_match = None
    else:
        precision_match = round_to(after_med, precision_decimals) == round_to(
            float(claimed_after), precision_decimals
        )
    claimed_d = claimed_delta
    if claimed_d is not None:
        delta_match = round_to(recomputed_delta, precision_decimals) == round_to(
            float(claimed_d), precision_decimals
        )
        if precision_match is None:
            precision_match = delta_match
        else:
            precision_match = bool(precision_match and delta_match)

    floor_delta = abs(recomputed_delta)
    noise_status = "NOT-CHECKED"
    noise_missing = noise_floor_file
    if noise_floor is None:
        noise_status = "NOT-CHECKED"
    elif floor_delta <= float(noise_floor):
        noise_status = "INSIDE"
        noise_missing = None
    else:
        noise_status = "EXCEEDS"
        noise_missing = None

    # Spec: a delta inside the noise floor is unmeasurable regardless of sign.
    if noise_status == "INSIDE":
        verdict = "UNMEASURABLE"
        classification = "noise-dominated-claim"
    elif precision_match is True:
        verdict = "MATCH"
        classification = "confirmed"
    elif precision_match is False:
        verdict = "MISMATCH"
        classification = "overclaim"
    else:
        verdict = "MATCH"
        classification = "confirmed"

    out = {
        **base,
        "verdict": verdict,
        "classification": classification,
        "recomputed_value": after_med,
        "recomputed_baseline": before_med,
        "delta": recomputed_delta,
        "precision_match": precision_match,
        "noise_floor_status": noise_status,
        "n_before": len(before),
        "n_after": len(after),
        "raw_repetitions": after,
        "baseline_repetitions": before,
        "two_way_median_agree": tw_a["agree"] and tw_b["agree"],
    }
    if noise_missing:
        out["noise_floor_missing_file"] = noise_missing
    if verdict == "UNMEASURABLE":
        out["noise_floor_numeric"] = float(noise_floor) if noise_floor is not None else None
    return out
