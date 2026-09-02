"""Live scaling capture for TST-0241.

(a) per-unit dispatch time across cohort sizes 16..2048
(b) bytes written per ledger append at each size
Detector: a rewrite mutant's per-write bytes grow with n; cumulative is quadratic.
Empty cohorts FAIL before a clock is read.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "command-center"))

from dispatch import dispatch_cohort, dispatch_record  # noqa: E402
from fixtures import SEED, SIZES, UNIT, input_fingerprint, make_units  # noqa: E402
from ledger import AppendLedger, EmptyInputError, RewriteLedger  # noqa: E402

from foundry.candidate_registry import CandidateRegistry, ImportRecord  # noqa: E402
import close as cc_close  # noqa: E402

N_REPS = 11
WARMUP = 2
T_CRIT_DF10 = 2.228138842064602
BAND_FORMULA = (
    "half = max(8*IQR, 6*stdev, 2*|median|); "
    "band = [median-half, median+half]; derived_from=raw_ns"
)
SOURCE_PATHS = (
    "tools/foundry/candidate_registry.py",
    "tools/command-center/close.py",
    "command-center/p2-wave/probes/TST-0241/ledger.py",
    "command-center/p2-wave/probes/TST-0241/dispatch.py",
)
OUT_REL = "command-center/receipts/TST-0241.json"
SCHEMA_REL = "command-center/schema/receipt.schema.json"
BENCH_SCHEMA_REL = "command-center/schema/benchmark-receipt.schema.json"
COMPLETION_SENTINEL = "SUCCESS:TST-0241"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def git_head() -> dict:
    try:
        probe = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=8,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}"}
    if probe.returncode != 0 or (probe.stdout or "").strip() != "true":
        return {"available": False, "reason": "not a git repository"}
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
    acc = hashlib.sha256()
    for rel in SOURCE_PATHS:
        path = REPO / rel
        sha, size = digest_file(path)
        acc.update(rel.encode("utf-8"))
        acc.update(b"\0")
        acc.update(sha.encode("ascii"))
        sources.append({"path": rel, "sha256": sha, "bytes": size, "present": True})
    content = acc.hexdigest()
    git = git_head()
    if git.get("available") and git.get("head"):
        kind, sha = "SHA-ANCHORED", str(git["head"])
    else:
        kind, sha = "CONTENT-PINNED", content
    return {
        "kind": kind,
        "sha": sha,
        "content_sha256": content,
        "git": git,
        "sources": sources,
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
    tcrit = T_CRIT_DF10 if n == 11 else 1.96
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
    }


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
    }


def close_enough(a: float, b: float, rel: float = 1e-9, abs_tol: float = 1e-6) -> bool:
    return abs(a - b) <= max(abs_tol, rel * max(abs(a), abs(b), 1.0))


def within_band(median_ns: float, band: dict) -> bool:
    return float(band["lo_ns"]) <= float(median_ns) <= float(band["hi_ns"])


def loglog_slope(xs: list[float], ys: list[float]) -> float:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(xs)
    mx = sum(lx) / n
    my = sum(ly) / n
    den = sum((a - mx) ** 2 for a in lx)
    if den == 0:
        return 0.0
    num = sum((a - mx) * (b - my) for a, b in zip(lx, ly))
    return num / den


def time_ns(fn: Callable[[], object]) -> int:
    t0 = time.perf_counter_ns()
    fn()
    t1 = time.perf_counter_ns()
    return t1 - t0


def sample(fn: Callable[[], object], n_reps: int = N_REPS, warmup: int = WARMUP) -> list[int]:
    for _ in range(warmup):
        fn()
    return [time_ns(fn) for _ in range(n_reps)]


def empty_control(control_id: str, fn: Callable[[], object]) -> dict:
    reported_time = None
    failed = False
    message = ""
    try:
        t0 = time.perf_counter_ns()
        fn()
        t1 = time.perf_counter_ns()
        reported_time = t1 - t0
        message = f"{control_id} returned a time on empty inputs (harness bug)"
    except EmptyInputError as exc:
        failed = True
        message = str(exc)
        reported_time = None
    return {
        "id": control_id,
        "n_inputs": 0,
        "failed": failed,
        "reported_time": reported_time,
        "message": message,
    }


def printed_lines(bench_id: str, stats: dict, n_inputs: int, extra: dict | None = None) -> list[str]:
    if n_inputs <= 0:
        raise EmptyInputError(f"{bench_id}: refusing to print a number next to n_inputs=0")
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


def pack_arm(arm_id: str, raw: list[int], n_inputs: int, extra: dict | None = None) -> dict:
    stats = summarize(raw)
    band = variance_band(stats)
    extra = extra or {}
    printable = {k: v for k, v in extra.items() if isinstance(v, (str, int, float))}
    printed = printed_lines(arm_id, stats, n_inputs, printable)
    return {
        "id": arm_id,
        "n_inputs": n_inputs,
        "raw_ns": raw,
        "statistics": stats,
        "variance_band": band,
        "printed": printed,
        **extra,
    }


def measure_dispatch_times(n: int, scratch: Path) -> list[int]:
    units = make_units(n)

    def run() -> None:
        path = scratch / f"disp-{n}-{time.perf_counter_ns()}.jsonl"
        dispatch_cohort(units, AppendLedger(path))

    return sample(run)


def measure_one_write(n: int, kind: str, scratch: Path) -> tuple[list[int], list[int]]:
    units = make_units(n)
    prior = units[:-1]
    last = dispatch_record(units[-1])
    cls = AppendLedger if kind == "append" else RewriteLedger
    filled = scratch / f"fill-{kind}-{n}.jsonl"
    ledger = cls(filled)
    persist_fill = kind != "rewrite"
    for unit in prior:
        if kind == "rewrite":
            ledger.write(dispatch_record(unit), persist=False)
        else:
            ledger.write(dispatch_record(unit))
    if kind == "rewrite":
        filled.write_bytes(ledger._blob)
    snap = filled.read_bytes()
    times: list[int] = []
    sizes: list[int] = []
    for i in range(WARMUP + N_REPS):
        filled.write_bytes(snap)
        ledger.records = n - 1
        if hasattr(ledger, "_blob"):
            ledger._blob = snap
        t0 = time.perf_counter_ns()
        nbytes = ledger.write(last)
        t1 = time.perf_counter_ns()
        if i >= WARMUP:
            times.append(t1 - t0)
            sizes.append(nbytes)
    return times, sizes


def write_size_curve(kind: str, scratch: Path, max_n: int = 2048) -> list[dict]:
    units = make_units(max_n)
    path = scratch / f"curve-{kind}.jsonl"
    cls = AppendLedger if kind == "append" else RewriteLedger
    ledger = cls(path)
    wanted = set(SIZES)
    rows: list[dict] = []
    cumulative = 0
    for i, unit in enumerate(units, 1):
        nbytes = ledger.write(dispatch_record(unit), persist=(i in wanted)) if kind == "rewrite" else ledger.write(dispatch_record(unit))
        cumulative += nbytes
        if i in wanted:
            rows.append(
                {
                    "n": i,
                    "bytes_this_write": nbytes,
                    "cumulative_bytes": cumulative,
                    "file_size": path.stat().st_size,
                    "kind": kind,
                }
            )
    return rows


def production_foundry_deltas(scratch: Path) -> list[dict]:
    """File-size delta of one extra _append at each n.

    CandidateRegistry._append fsyncs every line. Fill patches
    foundry.candidate_registry.os.fsync so we measure bytes, not durability.
    """
    import foundry.candidate_registry as cr_mod

    rows = []
    real_fsync = cr_mod.os.fsync
    cr_mod.os.fsync = lambda fd: None
    try:
        for n in SIZES:
            path = scratch / f"foundry-{n}.jsonl"
            if path.exists():
                path.unlink()
            reg = CandidateRegistry(path)
            for i in range(n - 1):
                reg._append(
                    {
                        "kind": "candidate",
                        "candidate_id": f"cnd_{n}_{i}",
                        "source_uri": f"tst://foundry/{n}/{i}",
                        "content_hash": f"{i:064d}"[:64],
                        "content_bytes": 8,
                        "ts": "2026-08-24T00:00:00+00:00",
                    }
                )
            before = path.stat().st_size if path.exists() else 0
            reg._append(
                {
                    "kind": "candidate",
                    "candidate_id": f"cnd_last_{n}",
                    "source_uri": f"tst://foundry/{n}/last",
                    "content_hash": "f" * 64,
                    "content_bytes": 8,
                    "ts": "2026-08-24T00:00:00+00:00",
                }
            )
            after = path.stat().st_size
            rows.append(
                {
                    "n": n,
                    "bytes_this_write": after - before,
                    "file_size_after": after,
                    "subject": "foundry.CandidateRegistry._append",
                }
            )
    finally:
        cr_mod.os.fsync = real_fsync
    return rows


def production_close_deltas(scratch: Path) -> list[dict]:
    rows = []
    for n in SIZES:
        path = scratch / f"events-{n}.jsonl"
        if path.exists():
            path.unlink()
        for i in range(n - 1):
            cc_close.append_event(
                {"id": f"e-{n}-{i}", "verb": "note", "n_inputs": n},
                path=path,
            )
        before = path.stat().st_size if path.exists() else 0
        cc_close.append_event(
            {"id": f"e-{n}-last", "verb": "note", "n_inputs": n},
            path=path,
        )
        after = path.stat().st_size
        rows.append(
            {
                "n": n,
                "bytes_this_write": after - before,
                "file_size_after": after,
                "subject": "close.append_event",
            }
        )
    return rows


def production_bytes_are_o1(rows: list[dict]) -> bool:
    sizes = [int(r["bytes_this_write"]) for r in rows]
    if not sizes:
        return False
    return max(sizes) / max(min(sizes), 1) < 2.5


def classify_curves(
    append_curve: list[dict],
    rewrite_curve: list[dict],
    dispatch_rows: list[dict],
) -> dict:
    def series(curve: list[dict], key: str) -> tuple[list[float], list[float]]:
        xs = [float(r["n"]) for r in curve]
        ys = [float(r[key]) for r in curve]
        return xs, ys

    ax, a_write = series(append_curve, "bytes_this_write")
    _, a_cum = series(append_curve, "cumulative_bytes")
    rx, r_write = series(rewrite_curve, "bytes_this_write")
    _, r_cum = series(rewrite_curve, "cumulative_bytes")
    dx = [float(r["n"]) for r in dispatch_rows]
    d_total = [float(r["median_total_ns"]) for r in dispatch_rows]
    d_unit = [float(r["per_unit_ns"]) for r in dispatch_rows]

    a16 = next(r for r in append_curve if r["n"] == 16)
    a2048 = next(r for r in append_curve if r["n"] == 2048)
    r16 = next(r for r in rewrite_curve if r["n"] == 16)
    r2048 = next(r for r in rewrite_curve if r["n"] == 2048)
    d256 = next(r for r in dispatch_rows if r["n"] == 256)
    d2048 = next(r for r in dispatch_rows if r["n"] == 2048)
    d16 = next(r for r in dispatch_rows if r["n"] == 16)

    write_ratio_append = a2048["bytes_this_write"] / max(a16["bytes_this_write"], 1)
    write_ratio_rewrite = r2048["bytes_this_write"] / max(r16["bytes_this_write"], 1)
    cum_ratio_append = a2048["cumulative_bytes"] / max(a16["cumulative_bytes"], 1)
    cum_ratio_rewrite = r2048["cumulative_bytes"] / max(r16["cumulative_bytes"], 1)
    unit_ratio = d2048["per_unit_ns"] / max(d256["per_unit_ns"], 1.0)

    verdicts = {
        "append_write_o1": write_ratio_append < 2.0,
        "rewrite_write_grows": write_ratio_rewrite >= 32.0,
        "append_cumulative_linear": 50.0 <= cum_ratio_append <= 250.0,
        "rewrite_cumulative_quadratic": cum_ratio_rewrite >= 2000.0,
        "dispatch_per_unit_flat": unit_ratio < 6.0,
        "dispatch_total_near_linear": 0.55 <= loglog_slope(dx, d_total) <= 1.45,
        "rewrite_write_loglog_near_one": loglog_slope(rx, r_write) >= 0.85,
        "append_write_loglog_near_zero": abs(loglog_slope(ax, a_write)) < 0.35,
    }
    return {
        "write_ratio_append_2048_over_16": write_ratio_append,
        "write_ratio_rewrite_2048_over_16": write_ratio_rewrite,
        "cum_ratio_append_2048_over_16": cum_ratio_append,
        "cum_ratio_rewrite_2048_over_16": cum_ratio_rewrite,
        "per_unit_ratio_2048_over_256": unit_ratio,
        "per_unit_ns_n16": d16["per_unit_ns"],
        "per_unit_ns_n256": d256["per_unit_ns"],
        "per_unit_ns_n2048": d2048["per_unit_ns"],
        "loglog_slope_append_write": loglog_slope(ax, a_write),
        "loglog_slope_rewrite_write": loglog_slope(rx, r_write),
        "loglog_slope_append_cumulative": loglog_slope(ax, a_cum),
        "loglog_slope_rewrite_cumulative": loglog_slope(rx, r_cum),
        "loglog_slope_dispatch_total": loglog_slope(dx, d_total),
        "loglog_slope_dispatch_per_unit": loglog_slope(dx, d_unit),
        "verdicts": verdicts,
        "pass": all(verdicts.values()),
    }


def capture(seed: int = SEED) -> dict:
    work = HERE / "_work"
    work.mkdir(parents=True, exist_ok=True)
    scratch = Path(tempfile.mkdtemp(prefix="tst0241-", dir=str(work)))
    try:
        print("TST-0241 capture start", flush=True)
        empty = [
            empty_control(
                "dispatch_cohort",
                lambda: dispatch_cohort([], AppendLedger(scratch / "empty-dispatch.jsonl")),
            ),
            empty_control(
                "append_ledger",
                lambda: AppendLedger(scratch / "empty-append.jsonl").write_all([]),
            ),
        ]
        if not all(row["failed"] and row["reported_time"] is None for row in empty):
            raise RuntimeError(f"empty-input control did not FAIL: {empty}")

        dispatch_rows: list[dict] = []
        dispatch_arms: list[dict] = []
        for n in SIZES:
            raw = measure_dispatch_times(n, scratch)
            stats = summarize(raw)
            per_unit = stats["median_ns"] / n
            dispatch_rows.append(
                {
                    "n": n,
                    "median_total_ns": stats["median_ns"],
                    "per_unit_ns": per_unit,
                    "raw_ns": raw,
                    "statistics": stats,
                }
            )
            dispatch_arms.append(
                pack_arm(
                    f"n{n}",
                    raw,
                    n,
                    extra={"per_unit_ns": f"{per_unit:.6f}", "bytes_mode": "append"},
                )
            )

        append_write_arms: list[dict] = []
        rewrite_write_arms: list[dict] = []
        append_write_sizes: dict[int, int] = {}
        rewrite_write_sizes: dict[int, int] = {}
        for n in SIZES:
            a_times, a_sizes = measure_one_write(n, "append", scratch)
            r_times, r_sizes = measure_one_write(n, "rewrite", scratch)
            append_write_sizes[n] = int(sorted(a_sizes)[len(a_sizes) // 2])
            rewrite_write_sizes[n] = int(sorted(r_sizes)[len(r_sizes) // 2])
            append_write_arms.append(
                pack_arm(
                    f"n{n}",
                    a_times,
                    n,
                    extra={"bytes_this_write": str(append_write_sizes[n])},
                )
            )
            rewrite_write_arms.append(
                pack_arm(
                    f"n{n}",
                    r_times,
                    n,
                    extra={"bytes_this_write": str(rewrite_write_sizes[n])},
                )
            )

        append_curve = write_size_curve("append", scratch)
        rewrite_curve = write_size_curve("rewrite", scratch)

        def suite() -> None:
            for n in SIZES:
                path = scratch / f"suite-{n}-{time.perf_counter_ns()}.jsonl"
                dispatch_cohort(make_units(n), AppendLedger(path))

        suite_raw = sample(suite)
        suite_arm = pack_arm("full_scaling_suite", suite_raw, sum(SIZES))
        foundry_rows = production_foundry_deltas(scratch)
        close_rows = production_close_deltas(scratch)
        curves = classify_curves(append_curve, rewrite_curve, dispatch_rows)

        benches = [
            {
                "id": "dispatch_per_unit",
                "name": "per-unit dispatch wall time on an append-only ledger",
                "arms": dispatch_arms,
            },
            {
                "id": "append_write",
                "name": "one append at ledger size n (bytes must stay flat)",
                "arms": append_write_arms,
            },
            {
                "id": "rewrite_write",
                "name": "one full-file rewrite at ledger size n (detector control)",
                "arms": rewrite_write_arms,
            },
            {
                "id": "suite_wall_clock",
                "name": "wall-clock of the 16..2048 append-only scaling suite",
                "arms": [suite_arm],
            },
        ]
        return {
            "seed": seed,
            "input_fingerprint": input_fingerprint(make_units(max(SIZES), seed)),
            "empty_input_controls": empty,
            "benchmarks": benches,
            "named_benchmarks": {
                "router_latency": "dispatch_per_unit",
                "hook_overhead": "append_write",
                "fanout_throughput": "dispatch_per_unit",
                "suite_wall_clock": "suite_wall_clock",
            },
            "scaling": {
                "sizes": list(SIZES),
                "dispatch": dispatch_rows,
                "append_curve": append_curve,
                "rewrite_curve": rewrite_curve,
                "append_write_sizes": {str(k): v for k, v in append_write_sizes.items()},
                "rewrite_write_sizes": {str(k): v for k, v in rewrite_write_sizes.items()},
                "production_foundry": foundry_rows,
                "production_close": close_rows,
                "classification": curves,
            },
        }
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def receipt_report(doc: dict) -> dict:
    """Measurement payload lives under report (receipt_core additionalProperties=false)."""
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("scaling"), dict):
        return rep
    return doc


def probe_fingerprint(method: str, command: str) -> str:
    return hashlib.sha256(f"{method}\n{command}".encode("utf-8")).hexdigest()


def clip_raw(text: str, limit: int = 60000) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 16] + "\n...[truncated]"


# Names used by emit_receipt.py / probes (stable aliases).
digest_file = digest_file
empty_control = empty_control
write_size_curve = write_size_curve
measure_dispatch_times = measure_dispatch_times
close_enough = close_enough
within_band = within_band
variance_band = variance_band
production_bytes_are_o1 = production_bytes_are_o1
receipt_report = receipt_report
