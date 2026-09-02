#!/usr/bin/env python3
"""Interleaved A/B microbenchmark harness for CNF-0052.

Two named in-process snapshots stand in for commits because this worktree is
not a git repository and CNF-0027 is absent. The identity pair tests the
noise-floor rule. The injected-regression pair is the detector control.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import math
import random
import subprocess
import time
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
UNIT = "CNF-0052"
N_REPS = 11
PAYLOAD_N = 18000
SEED = 52
WARMUP_PAIRS = 2
SLOW_EXTRA_PASSES = 8
T_CRIT_DF10 = 2.228138842064602  # Student t, df=10, two-sided 95%
CNF0027 = REPO / "command-center/confirmation/CNF-0027-baseline-variance.json"
OUT_REL = "command-center/confirmation/CNF-0052-benchmark-regression.json"
SCHEMA_REL = "command-center/schema/benchmark-report.schema.json"
COMPLETION_SENTINEL = (
    "SUCCESS:CNF-0052 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the interleaved raw "
    "values for both commits are attached and the interval arithmetic is shown. "
    "Any other terminal state is FAILED:CNF-0052 <classification> with the "
    "diagnostic tail attached."
)


def snap_a(rows: list[dict]) -> int:
    acc = 0
    for r in rows:
        acc = (acc + (int(r["w"]) * 1103515245 + 12345)) & 0xFFFFFFFF
    return acc


def snap_b_identity(rows: list[dict]) -> int:
    return snap_a(rows)


def snap_b_slow(rows: list[dict], extra: int = SLOW_EXTRA_PASSES) -> int:
    acc = snap_a(rows)
    for _ in range(extra):
        acc ^= snap_a(rows)
    return acc


def fn_digest(fn: Callable) -> str:
    return hashlib.sha256(inspect.getsource(fn).encode("utf-8")).hexdigest()


def make_rows(n: int = PAYLOAD_N, seed: int = SEED) -> list[dict]:
    rng = random.Random(seed)
    return [{"id": i, "w": rng.randint(1, 1_000_000)} for i in range(n)]


def payload_digest(rows: list[dict]) -> str:
    blob = json.dumps(rows, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def time_ns(fn: Callable, rows: list[dict]) -> tuple[int, int]:
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


def summarize(raw_ns: list[int | float]) -> dict:
    xs = [float(x) for x in raw_ns]
    n = len(xs)
    if n < 2:
        raise ValueError("need at least 2 samples")
    srt = sorted(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    sd = math.sqrt(var)
    tcrit = T_CRIT_DF10 if n == 11 else _t_crit(n - 1)
    half = tcrit * sd / math.sqrt(n)
    q1 = quantile(srt, 0.25)
    q3 = quantile(srt, 0.75)
    return {
        "n": n,
        "mean_ns": mean,
        "sample_variance_ns2": var,
        "stdev_ns": sd,
        "median_ns": quantile(srt, 0.5),
        "q1_ns": q1,
        "q3_ns": q3,
        "iqr_ns": q3 - q1,
        "min_ns": srt[0],
        "max_ns": srt[-1],
        "t_crit": tcrit,
        "ci95_halfwidth_ns": half,
        "ci95_lo_ns": mean - half,
        "ci95_hi_ns": mean + half,
        "formula_mean": "sum(x_i)/n",
        "formula_sample_variance": "sum((x_i-mean)^2)/(n-1)",
        "formula_ci95": "mean ± t_{n-1,0.975} * s / sqrt(n)",
    }


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


def ci_overlap(a: dict, b: dict) -> bool:
    return not (a["ci95_hi_ns"] < b["ci95_lo_ns"] or b["ci95_hi_ns"] < a["ci95_lo_ns"])


def noise_floor_ns(stats_a: dict, cnf0027_value: float | None) -> float:
    if cnf0027_value is not None:
        return float(cnf0027_value)
    return max(
        float(stats_a["iqr_ns"]),
        float(stats_a["stdev_ns"]),
        float(stats_a["ci95_halfwidth_ns"]),
        1.0,
    )


def classify(stats_a: dict, stats_b: dict, noise: float) -> dict:
    delta = stats_b["median_ns"] - stats_a["median_ns"]
    floor = max(float(noise), 0.0)
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
        "rule": (
            "if abs(median_B-median_A) <= noise_floor: no_measurable_change "
            "(never improvement); else if CIs disjoint and B slower: regression; "
            "else if CIs disjoint and B faster: improvement; else inconclusive"
        ),
    }


def is_abab(order: list[str]) -> bool:
    if len(order) < 2 * N_REPS:
        return False
    return all(tag == ("A" if i % 2 == 0 else "B") for i, tag in enumerate(order))


def is_blocked(order: list[str]) -> bool:
    n = len(order)
    if n < 2:
        return False
    half = n // 2
    return order[:half] == ["A"] * half and order[half:] == ["B"] * (n - half)


def run_interleaved(
    fn_a: Callable,
    fn_b: Callable,
    rows: list[dict],
    n_reps: int = N_REPS,
    warmup_pairs: int = WARMUP_PAIRS,
) -> dict:
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
        "blocked": is_blocked(order),
        "checksum_a": checksum_a,
        "checksum_b": checksum_b,
        "n_reps": n_reps,
    }


def run_blocked(
    fn_a: Callable,
    fn_b: Callable,
    rows: list[dict],
    n_reps: int = N_REPS,
) -> dict:
    order: list[str] = []
    raw_a: list[int] = []
    raw_b: list[int] = []
    for _ in range(n_reps):
        ns_a, _ra = time_ns(fn_a, rows)
        order.append("A")
        raw_a.append(ns_a)
    for _ in range(n_reps):
        ns_b, _rb = time_ns(fn_b, rows)
        order.append("B")
        raw_b.append(ns_b)
    return {
        "order": order,
        "raw_a_ns": raw_a,
        "raw_b_ns": raw_b,
        "interleaved": is_abab(order),
        "blocked": is_blocked(order),
        "n_reps": n_reps,
    }


def git_state() -> dict:
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    if p.returncode != 0 or (p.stdout or "").strip() != "true":
        err = ((p.stderr or "") + (p.stdout or "")).strip()[:400]
        return {
            "available": False,
            "reason": err or "not a git repository",
            "exit_code": p.returncode,
        }
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(REPO),
        capture_output=True,
        text=True,
        timeout=8,
    )
    return {
        "available": True,
        "head": (head.stdout or "").strip(),
        "note": (
            "git is present but this unit does not checkout commits; "
            "comparison uses named in-process snapshots"
        ),
    }


def load_cnf0027_noise_floor() -> dict:
    info: dict = {
        "path": "command-center/confirmation/CNF-0027-baseline-variance.json",
        "present": CNF0027.is_file() and CNF0027.stat().st_size > 0,
        "value_ns": None,
        "source": "local-A-arm-IQR",
    }
    if not info["present"]:
        info["note"] = "CNF-0027 artifact absent; noise floor taken from A-arm IQR"
        return info
    try:
        doc = json.loads(CNF0027.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        info["note"] = f"CNF-0027 unreadable: {type(exc).__name__}"
        return info
    val = None
    if isinstance(doc, dict):
        nf = doc.get("noise_floor") or doc.get("noise_floor_ns")
        if isinstance(nf, dict):
            val = nf.get("value_ns") or nf.get("iqr_ns")
        elif isinstance(nf, (int, float)):
            val = nf
        if val is None:
            for b in doc.get("benchmarks") or []:
                if not isinstance(b, dict):
                    continue
                for arm in b.get("arms") or []:
                    st = (arm or {}).get("statistics") or {}
                    if isinstance(st.get("iqr_ns"), (int, float)):
                        val = st["iqr_ns"]
                        break
    if isinstance(val, (int, float)) and val >= 0:
        info["value_ns"] = float(val)
        info["source"] = "CNF-0027"
        info["note"] = "loaded numeric noise floor from CNF-0027"
    else:
        info["note"] = "CNF-0027 present but no numeric noise floor; using A-arm IQR"
    return info


P1_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0052/probe1_interleaved.py"
)
P2_CMD = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0052/probe2_interval_arithmetic.py"
)


def payload(doc: dict) -> dict:
    """Domain fields live in extensions (receipt_core additionalProperties=false)."""
    if not isinstance(doc, dict):
        return {}
    ext = doc.get("extensions")
    if isinstance(ext, dict) and isinstance(ext.get("benchmarks"), list):
        merged = dict(doc)
        merged.update(ext)
        return merged
    return doc


def offline_validator():
    """Draft7 validator that resolves ast-integrate.invalid $ref from disk, never HTTPS."""
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
