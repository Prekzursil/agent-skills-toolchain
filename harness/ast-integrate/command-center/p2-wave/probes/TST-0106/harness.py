#!/usr/bin/env python3
"""Regression gate: pinned baseline + variance-derived tolerance.

TST-0025 / TST-0105 / TST-0109 catalog artifacts are absent on this tree.
This unit pins a local non-empty baseline, computes the variance band from
raw repetitions, declares a tolerance from that band, and classifies a
candidate against the declared tolerance (never a single-run comparison).
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import random
import time
from pathlib import Path
from typing import Callable


def _repo_root(start: Path) -> Path:
    for p in [start, *start.parents]:
        if (p / "command-center" / "WORK-UNIT-CATALOG.json").is_file():
            return p
    raise RuntimeError(f"cannot locate repo root from {start}")


HERE = Path(__file__).resolve().parent
REPO = _repo_root(HERE)
UNIT = "TST-0106"
N_REPS = 11
MIN_N = 11
PAYLOAD_N = 18000
SEED = 106
WARMUP_PAIRS = 2
SLOW_EXTRA_PASSES = 8
T_CRIT_DF10 = 2.228138842064602
OUT_REL = "command-center/receipts/TST-0106.json"
SCHEMA_REL = "command-center/schema/benchmark-receipt.schema.json"
DEP_PATHS = {
    "TST-0025": "command-center/receipts/TST-0025.json",
    "TST-0105": "command-center/receipts/TST-0105.json",
    "TST-0109": "command-center/receipts/TST-0109.json",
}
COMPLETION_SENTINEL = "SUCCESS:TST-0106"
P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0106/probe1_planted_slowdown.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0106/probe2_within_noise.py"
)
MIN_BYTES = 2048


class MeasuredNothing(ValueError):
    """Empty input must FAIL, not emit a number."""


def snap_a(rows: list[int]) -> int:
    acc = 0
    for w in rows:
        acc = (acc + (int(w) * 1103515245 + 12345)) & 0xFFFFFFFF
    return acc


def snap_b_identity(rows: list[int]) -> int:
    return snap_a(rows)


def snap_b_slow(rows: list[int], extra: int = SLOW_EXTRA_PASSES) -> int:
    acc = snap_a(rows)
    for _ in range(extra):
        acc ^= snap_a(rows)
    return acc


def fn_digest(fn: Callable) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()


def make_rows(n: int = PAYLOAD_N, seed: int = SEED) -> list[int]:
    if n < 0:
        raise ValueError("n must be >= 0")
    rng = random.Random(seed)
    return [rng.randint(1, 1_000_000) for _ in range(n)]


def payload_digest(rows: list[int]) -> str:
    blob = json.dumps(rows, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def require_nonempty(rows: list[int]) -> None:
    if not rows:
        raise MeasuredNothing("empty input is FAILED, not a number")


def time_ns(fn: Callable, rows: list[int]) -> tuple[int, int]:
    require_nonempty(rows)
    t0 = time.perf_counter_ns()
    result = fn(rows)
    t1 = time.perf_counter_ns()
    return t1 - t0, int(result)


def quantile(sorted_xs: list[float], p: float) -> float:
    if not sorted_xs:
        raise ValueError("empty sample")
    if p <= 0:
        return float(sorted_xs[0])
    if p >= 1:
        return float(sorted_xs[-1])
    n = len(sorted_xs)
    idx = (n - 1) * p
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    w = idx - lo
    return float(sorted_xs[lo]) * (1.0 - w) + float(sorted_xs[hi]) * w


def _t_crit(df: int) -> float:
    table = {
        1: 12.706204736,
        2: 4.3026527299,
        3: 3.1824463053,
        4: 2.7764451052,
        5: 2.5705818366,
        6: 2.4469118511,
        7: 2.3646242516,
        8: 2.3060041352,
        9: 2.2621571628,
        10: T_CRIT_DF10,
        11: 2.2009851601,
        12: 2.1788128297,
        20: 2.0859634473,
        30: 2.0422724563,
    }
    return table.get(df, 1.96)


def summarize(raw_ns: list[int | float]) -> dict:
    xs = [float(x) for x in raw_ns]
    n = len(xs)
    if n < MIN_N:
        raise ValueError(f"gate refuses n<{MIN_N}; single-run comparison is not a verdict")
    srt = sorted(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    tcrit = _t_crit(n - 1)
    half = tcrit * sd / math.sqrt(n)
    q1 = quantile(srt, 0.25)
    q3 = quantile(srt, 0.75)
    iqr = q3 - q1
    return {
        "n": n,
        "mean_ns": mean,
        "sample_variance_ns2": var,
        "stdev_ns": sd,
        "median_ns": quantile(srt, 0.5),
        "q1_ns": q1,
        "q3_ns": q3,
        "iqr_ns": iqr,
        "min_ns": srt[0],
        "max_ns": srt[-1],
        "t_crit": tcrit,
        "ci95_halfwidth_ns": half,
        "ci95_lo_ns": mean - half,
        "ci95_hi_ns": mean + half,
        "formula_mean": "sum(x_i)/n",
        "formula_sample_variance": "sum((x_i-mean)^2)/(n-1)",
        "formula_ci95": "mean ± t_{n-1,0.975} * s / sqrt(n)",
        "n_inputs": None,
    }


def variance_band(raw_ns: list[int | float]) -> dict:
    st = summarize(raw_ns)
    mde = st["t_crit"] * st["stdev_ns"] * math.sqrt(2.0 / st["n"])
    return {
        "n": st["n"],
        "mean_ns": st["mean_ns"],
        "stdev_ns": st["stdev_ns"],
        "median_ns": st["median_ns"],
        "iqr_ns": st["iqr_ns"],
        "ci95_lo_ns": st["ci95_lo_ns"],
        "ci95_hi_ns": st["ci95_hi_ns"],
        "ci95_halfwidth_ns": st["ci95_halfwidth_ns"],
        "min_detectable_effect_ns": mde,
        "formula_mde": "t_{n-1,0.975} * s * sqrt(2/n)  # two-sample",
        "raw_ns": [float(x) for x in raw_ns],
        "source": "this-unit pin; TST-0109 artifact absent",
        "t_crit": st["t_crit"],
    }


def derive_tolerance(band: dict) -> dict:
    t = max(
        float(band["iqr_ns"]),
        float(band["min_detectable_effect_ns"]),
        float(band["ci95_halfwidth_ns"]),
    )
    if t <= 0:
        t = max(float(band["stdev_ns"]), 1.0)
    return {
        "tolerance_ns": t,
        "formula": "max(IQR, MDE, CI95_halfwidth) with MDE=t*s*sqrt(2/n)",
        "quoted_from": "variance_band on pinned baseline (TST-0109 stand-in)",
        "iqr_ns": band["iqr_ns"],
        "min_detectable_effect_ns": band["min_detectable_effect_ns"],
        "ci95_halfwidth_ns": band["ci95_halfwidth_ns"],
        "n": band["n"],
        "t_crit": band["t_crit"],
    }


def ci_overlap(a: dict, b: dict) -> bool:
    return not (a["ci95_hi_ns"] < b["ci95_lo_ns"] or b["ci95_hi_ns"] < a["ci95_lo_ns"])


def classify(stats_a: dict, stats_b: dict, tolerance_ns: float) -> dict:
    """Classify B vs pinned/live A using a DECLARED tolerance.

    abs(delta) <= T is never a regression (within-noise).
    """
    if stats_a["n"] < MIN_N or stats_b["n"] < MIN_N:
        raise ValueError(f"gate refuses n<{MIN_N}")
    delta = stats_b["median_ns"] - stats_a["median_ns"]
    floor = max(float(tolerance_ns), 0.0)
    overlap = ci_overlap(stats_a, stats_b)
    if abs(delta) <= floor:
        label = "no_measurable_change"
    elif delta > floor and not overlap:
        label = "regression"
    elif delta < -floor and not overlap:
        label = "improvement"
    else:
        label = "inconclusive"
    return {
        "ci_overlap": overlap,
        "delta_median_ns": delta,
        "label": label,
        "noise_floor_ns": floor,
        "tolerance_ns": floor,
        "rule": (
            "if abs(median_B-median_A) <= declared_tolerance: no_measurable_change "
            "(never regression); else if CIs disjoint and B slower: regression; "
            "else if CIs disjoint and B faster: improvement; else inconclusive"
        ),
    }


def is_abab(order: list[str]) -> bool:
    if len(order) < 2 * N_REPS:
        return False
    return all(tag == ("A" if i % 2 == 0 else "B") for i, tag in enumerate(order))


def run_interleaved(
    fn_a: Callable,
    fn_b: Callable,
    rows: list[int],
    n_reps: int = N_REPS,
    warmup_pairs: int = WARMUP_PAIRS,
) -> dict:
    require_nonempty(rows)
    for _ in range(warmup_pairs):
        time_ns(fn_a, rows)
        time_ns(fn_b, rows)
    order: list[str] = []
    raw_a: list[int] = []
    raw_b: list[int] = []
    seq: list[dict] = []
    checksum_a = checksum_b = None
    for i in range(n_reps):
        ns_a, ra = time_ns(fn_a, rows)
        order.append("A")
        raw_a.append(ns_a)
        seq.append({"seq": 2 * i, "arm": "A", "ns": ns_a})
        ns_b, rb = time_ns(fn_b, rows)
        order.append("B")
        raw_b.append(ns_b)
        seq.append({"seq": 2 * i + 1, "arm": "B", "ns": ns_b})
        checksum_a, checksum_b = ra, rb
    return {
        "order": order,
        "raw_a_ns": raw_a,
        "raw_b_ns": raw_b,
        "sequence": seq,
        "interleaved": is_abab(order),
        "checksum_a": checksum_a,
        "checksum_b": checksum_b,
        "n_reps": n_reps,
        "n_inputs": len(rows),
    }


def pin_baseline(rows: list[int], n_reps: int = N_REPS) -> dict:
    """Pin n repetitions of the baseline snapshot (TST-0025 stand-in)."""
    require_nonempty(rows)
    for _ in range(WARMUP_PAIRS):
        time_ns(snap_a, rows)
    raw: list[int] = []
    checksum = None
    for _ in range(n_reps):
        ns, checksum = time_ns(snap_a, rows)
        raw.append(ns)
    return {
        "raw_ns": raw,
        "checksum": checksum,
        "n_reps": n_reps,
        "n_inputs": len(rows),
        "function": "harness.snap_a",
        "source_sha256": fn_digest(snap_a),
    }


def empty_input_control() -> dict:
    try:
        time_ns(snap_a, [])
        return {"raised": False, "failed_as_required": False}
    except MeasuredNothing as exc:
        return {
            "raised": True,
            "failed_as_required": True,
            "exception": type(exc).__name__,
            "message": str(exc),
        }


def n_lt_min_control() -> dict:
    try:
        summarize([1.0, 2.0, 3.0])
        return {"raised": False, "failed_as_required": False}
    except ValueError as exc:
        return {
            "raised": True,
            "failed_as_required": True,
            "exception": type(exc).__name__,
            "message": str(exc),
        }


def dep_status() -> dict:
    out = {}
    for uid, rel in DEP_PATHS.items():
        path = REPO / rel
        present = path.is_file() and path.stat().st_size > 0
        out[uid] = {
            "path": rel,
            "present": present,
            "stand_in": True,
        }
        if uid == "TST-0025":
            out[uid]["role"] = "pinned-baseline"
            out[uid]["note"] = (
                "catalog receipt absent; this unit pins a local non-empty baseline"
                if not present
                else "catalog receipt present; still records a local pin for this gate"
            )
        elif uid == "TST-0105":
            out[uid]["role"] = "nonempty-input-control"
            out[uid]["note"] = (
                "catalog receipt absent; harness refuses n_inputs==0"
                if not present
                else "catalog receipt present"
            )
        else:
            out[uid]["role"] = "variance-band"
            out[uid]["note"] = (
                "catalog receipt absent; variance band computed from this-unit pin"
                if not present
                else "catalog receipt present"
            )
    return out


def payload(doc: dict) -> dict:
    """Domain fields live in extensions (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    ext = doc.get("extensions")
    if isinstance(ext, dict) and (
        isinstance(ext.get("benchmarks"), list) or isinstance(ext.get("baseline"), dict)
    ):
        merged = dict(doc)
        merged.update(ext)
        return merged
    rpt = doc.get("report")
    if isinstance(rpt, dict) and isinstance(rpt.get("benchmarks"), list):
        merged = dict(doc)
        merged.update(rpt)
        return merged
    return doc


def offline_validator():
    """Draft7 validator that resolves ast-integrate.invalid $ref from disk."""
    import jsonschema

    shim = json.loads((REPO / SCHEMA_REL).read_text(encoding="utf-8"))
    profiles = json.loads(
        (REPO / "platform/schema/artifact-class-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    store = {}
    for d in (shim, profiles, receipt):
        sid = d.get("$id")
        if isinstance(sid, str) and sid:
            store[sid] = d
    resolver = jsonschema.RefResolver.from_schema(shim, store=store)
    return jsonschema.Draft7Validator(shim, resolver=resolver)


def schema_errors(doc: dict) -> list[str]:
    v = offline_validator()
    out = []
    for err in v.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)
