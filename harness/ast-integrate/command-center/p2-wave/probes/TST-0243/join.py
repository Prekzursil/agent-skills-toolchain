#!/usr/bin/env python3
"""Mechanical per-class join: catalog timeout_seconds vs measured p99.

Class = ID prefix (TST, IMP, …). Class timeout = minimum timeout_seconds
among units of that class (tightest declared budget). PASS for a class
requires timeout_min >= p99 * (1 + MARGIN_RATIO). A class whose p99 exceeds
that bound is a catalog defect with a proposed new timeout.
"""
from __future__ import annotations

import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

PREFIX_RE = re.compile(r"^([A-Z]{2,5})-")
UID_RE = re.compile(r"^[A-Z]{2,5}-\d{4}$")

# Declared margin: timeout must exceed p99 by this multiplicative headroom.
MARGIN_RATIO = 0.10
TIMEOUT_QUANTUM_SECONDS = 300
LOW_N = 20
VERDICT_DEFECT = "DEFECT"
VERDICT_ADEQUATE = "ADEQUATE"
VERDICT_NO_SAMPLES = "NO-SAMPLES"


def unit_class(uid: str) -> str:
    m = PREFIX_RE.match(str(uid or ""))
    return m.group(1) if m else "UNKNOWN"


def nearest_rank_percentile(sorted_xs: list[float], p: float) -> float | None:
    """Nearest-rank percentile. p in 0..100. Empty → None."""
    if not sorted_xs:
        return None
    if p <= 0:
        return float(sorted_xs[0])
    k = max(1, min(len(sorted_xs), math.ceil((p / 100.0) * len(sorted_xs))))
    return float(sorted_xs[k - 1])


def quartile_stats(samples: Iterable[float]) -> dict[str, float | int | None]:
    xs = sorted(float(x) for x in samples)
    n = len(xs)
    if n == 0:
        return {
            "n": 0,
            "median": None,
            "q1": None,
            "q3": None,
            "iqr": None,
            "p99": None,
            "min": None,
            "max": None,
        }
    q1 = nearest_rank_percentile(xs, 25.0)
    q3 = nearest_rank_percentile(xs, 75.0)
    med = nearest_rank_percentile(xs, 50.0)
    p99 = nearest_rank_percentile(xs, 99.0)
    iqr = float(q3 - q1) if q1 is not None and q3 is not None else 0.0
    return {
        "n": n,
        "median": med,
        "q1": q1,
        "q3": q3,
        "iqr": iqr,
        "p99": p99,
        "min": xs[0],
        "max": xs[-1],
        "raw": xs,
    }


def required_timeout(p99: float, margin_ratio: float = MARGIN_RATIO) -> float:
    return float(p99) * (1.0 + float(margin_ratio))


def propose_timeout(p99: float, margin_ratio: float = MARGIN_RATIO) -> int:
    need = required_timeout(p99, margin_ratio)
    q = TIMEOUT_QUANTUM_SECONDS
    return int(math.ceil(need / q) * q)


def load_catalog_units(catalog: dict[str, Any] | Path) -> list[dict[str, Any]]:
    if isinstance(catalog, Path):
        catalog = json.loads(catalog.read_text(encoding="utf-8"))
    out: list[dict[str, Any]] = []
    for u in (catalog or {}).get("work_units") or []:
        if not isinstance(u, dict):
            continue
        uid = str(u.get("id") or "")
        if not UID_RE.match(uid):
            continue
        t = u.get("timeout_seconds")
        timeout = int(t) if isinstance(t, (int, float)) else 0
        out.append({"id": uid, "timeout_seconds": timeout})
    return out


def join(
    units: list[dict[str, Any]],
    durations_by_class: dict[str, list[float]],
    margin_ratio: float = MARGIN_RATIO,
) -> dict[str, Any]:
    """Join catalog timeouts to measured durations. Never eyeballed."""
    by_class: dict[str, list[int]] = defaultdict(list)
    for u in units:
        by_class[unit_class(u["id"])].append(int(u["timeout_seconds"]))

    rows: list[dict[str, Any]] = []
    defects: list[dict[str, Any]] = []
    for cls in sorted(by_class):
        timeouts = sorted(by_class[cls])
        n_units = len(timeouts)
        timeout_min = timeouts[0]
        timeout_max = timeouts[-1]
        timeout_p50 = timeouts[n_units // 2]
        counts = dict(Counter(timeouts))
        samples = [float(x) for x in (durations_by_class.get(cls) or [])]
        stats = quartile_stats(samples)
        p99 = stats["p99"]
        row: dict[str, Any] = {
            "class": cls,
            "n_units": n_units,
            "n_samples": stats["n"],
            "timeout_min": timeout_min,
            "timeout_p50": timeout_p50,
            "timeout_max": timeout_max,
            "timeout_value_counts": {str(k): v for k, v in sorted(counts.items())},
            "p50_seconds": stats["median"],
            "p99_seconds": p99,
            "min_seconds": stats["min"],
            "max_seconds": stats["max"],
            "q1_seconds": stats["q1"],
            "q3_seconds": stats["q3"],
            "iqr_seconds": stats["iqr"],
            "low_n": bool(stats["n"] and stats["n"] < LOW_N),
            "margin_ratio": margin_ratio,
            "required_timeout_seconds": None,
            "adequate": None,
            "verdict": VERDICT_NO_SAMPLES,
            "proposed_new_timeout_seconds": None,
        }
        if p99 is None:
            rows.append(row)
            continue
        need = required_timeout(p99, margin_ratio)
        adequate = timeout_min >= need
        row["required_timeout_seconds"] = need
        row["adequate"] = adequate
        if adequate:
            row["verdict"] = VERDICT_ADEQUATE
        else:
            proposed = propose_timeout(p99, margin_ratio)
            if proposed <= timeout_min:
                proposed = timeout_min + TIMEOUT_QUANTUM_SECONDS
            row["verdict"] = VERDICT_DEFECT
            row["proposed_new_timeout_seconds"] = proposed
            defects.append(
                {
                    "class": cls,
                    "timeout_min": timeout_min,
                    "p99_seconds": p99,
                    "n_samples": stats["n"],
                    "required_timeout_seconds": need,
                    "proposed_new_timeout_seconds": proposed,
                    "reason": (
                        f"{cls} p99={p99:.3f}s exceeds timeout_min={timeout_min}s "
                        f"by declared margin {margin_ratio:.2f} "
                        f"(need>={need:.3f}s)"
                    ),
                }
            )
        rows.append(row)

    return {
        "margin_ratio": margin_ratio,
        "margin_declared": (
            f"timeout_min >= p99_seconds * (1 + {margin_ratio}) "
            f"[class timeout = min timeout_seconds in class]"
        ),
        "timeout_quantum_seconds": TIMEOUT_QUANTUM_SECONDS,
        "class_timeout_rule": "minimum timeout_seconds among units of the class",
        "percentile_rule": "nearest-rank p99 over ledger durations of that class",
        "low_n_threshold": LOW_N,
        "n_classes": len(rows),
        "n_compared": sum(1 for r in rows if r["verdict"] != VERDICT_NO_SAMPLES),
        "n_defects": len(defects),
        "n_adequate": sum(1 for r in rows if r["verdict"] == VERDICT_ADEQUATE),
        "n_no_samples": sum(1 for r in rows if r["verdict"] == VERDICT_NO_SAMPLES),
        "rows": rows,
        "defects": defects,
        "eyeballed": False,
    }


def overlay_class_timeout(
    units: list[dict[str, Any]], cls: str, timeout_seconds: int
) -> list[dict[str, Any]]:
    """In-memory catalog overlay. Does not write the catalog."""
    out = []
    for u in units:
        rec = dict(u)
        if unit_class(rec["id"]) == cls:
            rec["timeout_seconds"] = int(timeout_seconds)
        out.append(rec)
    return out


def synthetic_both_states() -> dict[str, Any]:
    """Deterministic both-states control: short timeout must be reported."""
    units = [{"id": f"FIX-{i:04d}", "timeout_seconds": 3600} for i in range(1, 6)]
    units += [{"id": f"OKY-{i:04d}", "timeout_seconds": 3600} for i in range(1, 6)]
    durations = {
        "FIX": [10.0 + (i / 100.0) for i in range(100)],
        "OKY": [8.0 + (i / 200.0) for i in range(100)],
    }
    good = join(units, durations)
    bad_units = overlay_class_timeout(units, "FIX", 1)
    bad = join(bad_units, durations)
    fix_good = next(r for r in good["rows"] if r["class"] == "FIX")
    fix_bad = next(r for r in bad["rows"] if r["class"] == "FIX")
    oky_bad = next(r for r in bad["rows"] if r["class"] == "OKY")
    fired = any(d["class"] == "FIX" for d in bad["defects"])
    silent = not any(d["class"] == "FIX" for d in good["defects"])
    oky_untouched = not any(d["class"] == "OKY" for d in bad["defects"])
    proposed = fix_bad.get("proposed_new_timeout_seconds")
    return {
        "id": "artificially-short-timeout-on-one-class",
        "good": {
            "verdict": fix_good["verdict"],
            "timeout_min": fix_good["timeout_min"],
            "p99_seconds": fix_good["p99_seconds"],
            "defects": good["defects"],
        },
        "broken": {
            "verdict": fix_bad["verdict"],
            "timeout_min": fix_bad["timeout_min"],
            "p99_seconds": fix_bad["p99_seconds"],
            "proposed_new_timeout_seconds": proposed,
            "defects": bad["defects"],
        },
        "control_class_untouched": oky_untouched,
        "control_class_verdict": oky_bad["verdict"],
        "silent_on_good": silent,
        "fires_on_short_timeout": fired,
        "proposed_present": proposed is not None,
        "pass": silent and fired and oky_untouched and proposed is not None,
    }
