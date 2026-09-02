#!/usr/bin/env python3
"""Baseline capture harness for TST-0025.

Measures four named benches against live worktree code:
  * router latency     — tools.router.shadow.select_from_catalog
  * hook overhead      — tools.plugin.exec_policy check_spawn/write/network
  * fan-out throughput — ThreadPoolExecutor fan-out of the same router selects
  * suite wall-clock   — the three above as one timed suite

Empty input sets raise EmptyInputError *before* a time is taken. Same seed
rebuilds the same inputs. Variance bands are derived from raw_ns, not from
a hand-written summary.
"""
from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from exec_policy import (  # noqa: E402
    PolicyDenied,
    build_policy,
    check_network,
    check_spawn,
    check_write,
)
from router.shadow import load_catalog, select_from_catalog  # noqa: E402

import fixtures as F  # noqa: E402

UNIT = "TST-0025"
OUT_REL = "command-center/receipts/TST-0025.json"
SCHEMA_REL = "command-center/schema/benchmark-receipt.schema.json"
COMPLETION_SENTINEL = "SUCCESS:TST-0025"
N_REPS = 11
WARMUP = 3
T_CRIT_DF10 = 2.228138842064602
BAND_FORMULA = (
    "half = max(8*IQR, 6*stdev, 2*|median|); "
    "band = [median-half, median+half]; derived_from=raw_ns (no OS floor)"
)
SOURCE_PATHS = (
    "tools/router/shadow.py",
    "tools/router/shadow_catalog.json",
    "tools/plugin/exec_policy.py",
)


class EmptyInputError(ValueError):
    """Input cardinality is zero; the harness must not emit a time."""


def assert_nonempty(bench_id: str, inputs: list) -> int:
    n = len(inputs)
    if n == 0:
        raise EmptyInputError(
            f"{bench_id}: input cardinality is 0; FAIL rather than report a time"
        )
    return n


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def git_head() -> dict:
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
    return {"available": True, "head": (head.stdout or "").strip()}


def pin_state() -> dict:
    sources = []
    h = hashlib.sha256()
    for rel in SOURCE_PATHS:
        path = REPO / rel
        sha, size = digest_file(path)
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(sha.encode("ascii"))
        sources.append({"path": rel, "sha256": sha, "bytes": size, "present": True})
    content = h.hexdigest()
    git = git_head()
    if git.get("available") and git.get("head"):
        kind = "SHA-ANCHORED"
        sha = str(git["head"])
    else:
        kind = "CONTENT-PINNED"
        sha = content
    return {
        "kind": kind,
        "sha": sha,
        "content_sha256": content,
        "git": git,
        "sources": sources,
        "note": (
            "git HEAD when available; otherwise a content digest of the measured "
            "router/hook sources so the freeze is still pinned"
        ),
    }


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
        10: T_CRIT_DF10,
        20: 2.0859634473,
        30: 2.0422724563,
    }
    return table.get(df, 1.96)


def variance_band(stats: dict) -> dict:
    median = float(stats["median_ns"])
    iqr = float(stats["iqr_ns"])
    stdev = float(stats["stdev_ns"])
    half = max(8.0 * iqr, 6.0 * stdev, 2.0 * abs(median))
    return {
        "lo_ns": median - half,
        "hi_ns": median + half,
        "half_ns": half,
        "formula": BAND_FORMULA,
        "derived_from": "raw_ns",
        "components": {
            "eight_iqr": 8.0 * iqr,
            "six_stdev": 6.0 * stdev,
            "two_abs_median": 2.0 * abs(median),
        },
    }


def printed_lines(bench_id: str, stats: dict, n_inputs: int, extra: dict | None = None) -> list[str]:
    if n_inputs <= 0:
        raise EmptyInputError(
            f"{bench_id}: refusing to print a number next to n_inputs=0"
        )
    lines = [
        f"{bench_id}.median_ns={stats['median_ns']:.6f} n_inputs={n_inputs}",
        f"{bench_id}.mean_ns={stats['mean_ns']:.6f} n_inputs={n_inputs}",
        f"{bench_id}.iqr_ns={stats['iqr_ns']:.6f} n_inputs={n_inputs}",
        (
            f"{bench_id}.ci95=[{stats['ci95_lo_ns']:.6f},{stats['ci95_hi_ns']:.6f}] "
            f"n_inputs={n_inputs}"
        ),
    ]
    if extra:
        for key, val in extra.items():
            lines.append(f"{bench_id}.{key}={val} n_inputs={n_inputs}")
    return lines


def time_ns(fn: Callable[[], object]) -> int:
    t0 = time.perf_counter_ns()
    fn()
    t1 = time.perf_counter_ns()
    return t1 - t0


def make_policy() -> dict:
    F.ALLOWED_ROOT.mkdir(parents=True, exist_ok=True)
    return build_policy(
        policy_id="tst-0025-hook-baseline",
        allowed_executables=[sys.executable],
        allowed_write_roots=[str(F.ALLOWED_ROOT)],
        network_mode="deny",
        description="TST-0025 hook-overhead baseline policy",
    )


def run_router(queries: list[str], catalog) -> int:
    n = assert_nonempty("router_latency", queries)
    for q in queries:
        select_from_catalog(q, catalog)
    return n


def run_hooks(subjects: list[dict], policy: dict) -> int:
    n = assert_nonempty("hook_overhead", subjects)
    for item in subjects:
        kind = item["kind"]
        try:
            if kind == "spawn":
                check_spawn(item["argv"], policy=policy)
            elif kind == "write":
                check_write(item["path"], policy=policy)
            elif kind == "net":
                check_network(item["host"], int(item["port"]), policy=policy)
            else:
                raise RuntimeError(f"unknown hook subject kind {kind}")
        except PolicyDenied:
            pass
    return n


def run_fanout(queries: list[str], catalog, ex: ThreadPoolExecutor) -> int:
    n = assert_nonempty("fanout_throughput", queries)

    def one(q: str):
        return select_from_catalog(q, catalog)

    list(ex.map(one, queries))
    return n


def run_suite(
    queries: list[str],
    subjects: list[dict],
    catalog,
    policy: dict,
    ex: ThreadPoolExecutor,
) -> int:
    n = (
        assert_nonempty("suite_wall_clock.router", queries)
        + assert_nonempty("suite_wall_clock.hooks", subjects)
        + assert_nonempty("suite_wall_clock.fanout", queries)
    )
    run_router(queries, catalog)
    run_hooks(subjects, policy)
    run_fanout(queries, catalog, ex)
    return n


def sample(fn: Callable[[], object], n_reps: int = N_REPS, warmup: int = WARMUP) -> list[int]:
    for _ in range(warmup):
        fn()
    raw: list[int] = []
    for _ in range(n_reps):
        raw.append(time_ns(fn))
    return raw


def empty_control(bench_id: str, fn: Callable[[], object]) -> dict:
    reported_time = None
    failed = False
    message = ""
    try:
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        reported_time = t1 - t0
        message = f"{bench_id} returned a time on empty inputs (harness bug)"
    except EmptyInputError as exc:
        failed = True
        message = str(exc)
        reported_time = None
    return {
        "id": bench_id,
        "n_inputs": 0,
        "failed": failed,
        "reported_time": reported_time,
        "message": message,
    }


def capture(seed: int = F.SEED) -> dict:
    queries = F.make_queries(seed)
    hooks = F.make_hook_subjects(seed)
    catalog = load_catalog()
    if not catalog:
        raise RuntimeError("router catalog is empty; refusing to measure nothing")
    policy = make_policy()
    fingerprint = F.input_fingerprint(queries, hooks)
    workers = min(8, max(2, len(queries)))
    ex = ThreadPoolExecutor(max_workers=workers)
    try:
        empty = [
            empty_control(
                "router_latency", lambda: run_router([], catalog)
            ),
            empty_control(
                "hook_overhead", lambda: run_hooks([], policy)
            ),
        ]
        if not all(row["failed"] and row["reported_time"] is None for row in empty):
            raise RuntimeError(f"empty-input control did not FAIL: {empty}")

        raw_router = sample(lambda: run_router(queries, catalog))
        raw_hook = sample(lambda: run_hooks(hooks, policy))
        raw_fan = sample(lambda: run_fanout(queries, catalog, ex))
        raw_suite = sample(
            lambda: run_suite(queries, hooks, catalog, policy, ex)
        )
    finally:
        ex.shutdown(wait=True)

    def pack(
        bench_id: str,
        name: str,
        raw: list[int],
        n_inputs: int,
        unit: str,
        extra: dict | None = None,
    ) -> dict:
        stats = summarize(raw)
        band = variance_band(stats)
        extra_print = extra or {}
        if unit == "qps":
            median_s = stats["median_ns"] / 1e9
            qps = (n_inputs / median_s) if median_s > 0 else 0.0
            extra_print = {**extra_print, "qps": f"{qps:.6f}"}
            value = qps
        else:
            value = stats["median_ns"]
        printed = printed_lines(bench_id, stats, n_inputs, extra_print)
        arm = {
            "id": "baseline",
            "n_inputs": n_inputs,
            "printed": printed,
            "raw_ns": raw,
            "statistics": stats,
            "unit": unit,
            "value": value,
            "variance_band": band,
            "verdict": "FROZEN",
        }
        return {
            "id": bench_id,
            "name": name,
            "n_inputs": n_inputs,
            "value": value,
            "unit": unit,
            "printed": printed,
            "raw_ns": raw,
            "statistics": stats,
            "variance_band": band,
            "verdict": "FROZEN",
            "arms": [arm],
        }

    benches = [
        pack(
            "router_latency",
            "router latency (select_from_catalog over query set)",
            raw_router,
            len(queries),
            "ns",
        ),
        pack(
            "hook_overhead",
            "hook overhead (exec_policy spawn/write/net checks)",
            raw_hook,
            len(hooks),
            "ns",
        ),
        pack(
            "fanout_throughput",
            "fan-out throughput (thread-pool router selects)",
            raw_fan,
            len(queries),
            "qps",
            {"workers": str(workers)},
        ),
        pack(
            "suite_wall_clock",
            "suite wall-clock (router+hook+fanout as one timed suite)",
            raw_suite,
            len(queries) + len(hooks) + len(queries),
            "ns",
        ),
    ]
    return {
        "seed": seed,
        "input_fingerprint": fingerprint,
        "n_queries": len(queries),
        "n_hooks": len(hooks),
        "n_catalog": len(catalog),
        "empty_input_controls": empty,
        "benchmarks": benches,
        "named_benchmarks": {
            "router_latency": "router_latency",
            "hook_overhead": "hook_overhead",
            "fanout_throughput": "fanout_throughput",
            "suite_wall_clock": "suite_wall_clock",
        },
    }


def within_band(median_ns: float, band: dict) -> bool:
    return float(band["lo_ns"]) <= float(median_ns) <= float(band["hi_ns"])


def close(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def compiled_schema() -> dict:
    """Physical benchmark-receipt contract without following the catalog shim $ref.

    command-center/schema/benchmark-receipt.schema.json is a generated shim whose
    $ref is https://ast-integrate.invalid/... Stock jsonschema 4.10 Draft7Validator
    retrieves that URI over HTTPS. This inlines receipt.schema.json $defs so
    validation stays on disk.
    """
    receipt = json.loads(
        (REPO / "platform/schema/receipt.schema.json").read_text(encoding="utf-8")
    )
    defs = receipt.get("$defs")
    if not isinstance(defs, dict) or "generic_report" not in defs:
        raise RuntimeError("receipt.schema.json missing generic_report")
    return {
        "$id": (
            "https://ast-integrate.invalid/command-center/p2-wave/probes/"
            "TST-0025/benchmark-receipt.local.json"
        ),
        "allOf": [
            {"$ref": "#/$defs/generic_report"},
            {
                "type": "object",
                "properties": {
                    "report": {
                        "required": ["kind"],
                        "properties": {
                            "kind": {"const": "benchmark-receipt"},
                        },
                    }
                },
            },
        ],
        "$defs": defs,
    }


def schema_errors(doc: object) -> list[str]:
    import jsonschema  # local: keep harness import-light for capture()

    out: list[str] = []
    for err in jsonschema.Draft7Validator(compiled_schema()).iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def payload(doc: dict) -> dict:
    """Merge report.* so probes can read benches after receipt_core nesting."""
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    view = dict(report)
    view.update({k: v for k, v in doc.items() if k != "report"})
    return view
