#!/usr/bin/env python3
"""AUD-0056 NAMED PROBE 2: external wall-clock per module (invoked separately).

Catalog evidence_requirement Probe 2: "an external wall-clock measurement per
module invoked separately, because the in-runner report excludes collection
and fixture setup attributed elsewhere."

Method:
  1. Collect the same TARGET_ARGS scope as probe 1.
  2. Enumerate unique test modules (pytest --collect-only).
  3. For EACH module, spawn a fresh pytest process targeting only that path
     and measure external wall-clock (time.perf_counter from process start
     to process end) -- NOT pytest --durations.
  4. Rank modules by external wall-clock; record top-10.
  5. Run the full per-module profile TWICE; require top-10 ranking stable
     (same tests_required control as probe 1).
  6. GROUND TRUTH: the deliberately-slow control module must appear in the
     top-10 by external wall-clock.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
OUT = PROBE / "probe2-external-wallclock.json"
RAW = PROBE / "probe2-external-wallclock.raw.txt"

GROUND_TRUTH_MODULE = (
    "command-center/p2-wave/probes/AUD-0056/fixtures/slow_control/"
    "test_deliberately_slow.py"
)
TOP_N = 10


def target_args() -> list[str]:
    sys.path.insert(0, str(FIXTURES))
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def collect_modules() -> list[str]:
    args = [
        sys.executable,
        "-m",
        "pytest",
        *target_args(),
        "--collect-only",
        "-q",
        "-p",
        "no:cacheprovider",
    ]
    r = subprocess.run(args, cwd=str(REPO), capture_output=True, text=True, timeout=180)
    out = (r.stdout or "") + (r.stderr or "")
    modules: list[str] = []
    seen: set[str] = set()
    for line in out.splitlines():
        line = line.strip()
        if "::" not in line:
            continue
        mod = line.split("::", 1)[0]
        if mod and mod not in seen:
            seen.add(mod)
            modules.append(mod)
    return modules


def time_module(module: str) -> dict:
    args = [
        sys.executable,
        "-m",
        "pytest",
        module,
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]
    t0 = time.perf_counter()
    try:
        r = subprocess.run(
            args,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=300,
        )
        rc = r.returncode
        out = ((r.stdout or "") + (r.stderr or ""))[-500:]
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"TIMEOUT: {e}"
    elapsed = time.perf_counter() - t0
    return {
        "module": module,
        "wall_seconds": round(elapsed, 6),
        "returncode": rc,
        "output_tail": out,
    }


def rank_modules(results: list[dict]) -> list[dict]:
    ranked = sorted(results, key=lambda x: (-x["wall_seconds"], x["module"]))
    return ranked


def top_names(ranked: list[dict], n: int = TOP_N) -> list[str]:
    return [r["module"] for r in ranked[:n]]


def run_profile(run_id: int, modules: list[str]) -> tuple[dict, str]:
    lines = [f"===== RUN {run_id} modules={len(modules)} ====="]
    results: list[dict] = []
    for mod in modules:
        row = time_module(mod)
        results.append(row)
        lines.append(
            f"MODULE wall={row['wall_seconds']:.6f}s rc={row['returncode']} {mod}"
        )
    ranked = rank_modules(results)
    top = top_names(ranked, TOP_N)
    gt_rank = next(
        (
            i + 1
            for i, r in enumerate(ranked)
            if r["module"] == GROUND_TRUTH_MODULE
            or r["module"].endswith("test_deliberately_slow.py")
        ),
        None,
    )
    lines.append(f"TOP10={top}")
    lines.append(f"ground_truth_rank={gt_rank}")
    payload = {
        "run_id": run_id,
        "module_count": len(modules),
        "results": ranked,
        "top10_modules": top,
        "ground_truth_module_rank": gt_rank,
        "ground_truth_in_top10": gt_rank is not None and gt_rank <= TOP_N,
    }
    return payload, "\n".join(lines)


def main() -> int:
    lines: list[str] = [
        "AUD-0056 NAMED PROBE 2: external wall-clock per module (x2)",
        "unit=AUD-0056",
        f"scope={target_args()}",
        f"started={datetime.now(timezone.utc).isoformat()}",
    ]
    modules = collect_modules()
    lines.append(f"collected_modules={len(modules)}")
    if GROUND_TRUTH_MODULE not in modules and not any(
        m.endswith("test_deliberately_slow.py") for m in modules
    ):
        lines.append("FAILED: ground-truth slow module not collected")
        RAW.write_text("\n".join(lines) + "\n", encoding="utf-8")
        OUT.write_text(
            json.dumps({"ok": False, "error": "ground-truth not collected"}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        print("\n".join(lines))
        return 1

    runs: list[dict] = []
    raw_chunks: list[str] = []
    for run_id in (1, 2):
        payload, chunk = run_profile(run_id, modules)
        runs.append(payload)
        raw_chunks.append(chunk)
        lines.append(
            f"RUN{run_id} top10={payload['top10_modules']} "
            f"gt_rank={payload['ground_truth_module_rank']}"
        )

    ranking_stable = (
        len(runs) == 2
        and bool(runs[0]["top10_modules"])
        and runs[0]["top10_modules"] == runs[1]["top10_modules"]
    )
    mismatches: list[dict] = []
    if len(runs) == 2:
        a, b = runs[0]["top10_modules"], runs[1]["top10_modules"]
        for i in range(max(len(a), len(b))):
            left = a[i] if i < len(a) else None
            right = b[i] if i < len(b) else None
            if left != right:
                mismatches.append({"rank": i + 1, "run1": left, "run2": right})

    ground_truth_ok = all(r.get("ground_truth_in_top10") for r in runs)
    measured_ok = all(r["module_count"] > 0 for r in runs)
    ok = measured_ok and ranking_stable and ground_truth_ok

    lines.append(
        f"CONTROL ranking_stable={ranking_stable} mismatches={len(mismatches)} "
        f"ground_truth_ok={ground_truth_ok} ok={ok}"
    )
    if not ranking_stable:
        lines.append(
            "NOTE: top-10 module ranking unstable across two runs -- "
            "measurement is contention-dominated and cannot be used as a baseline"
        )

    # Median wall seconds per module across the two runs (for headline).
    medians: dict[str, float] = {}
    if len(runs) == 2:
        by_mod: dict[str, list[float]] = {}
        for run in runs:
            for row in run["results"]:
                by_mod.setdefault(row["module"], []).append(row["wall_seconds"])
        for mod, vals in by_mod.items():
            medians[mod] = round(sorted(vals)[len(vals) // 2], 6)
    median_ranked = sorted(
        [{"module": m, "median_wall_seconds": medians[m]} for m in medians],
        key=lambda x: (-x["median_wall_seconds"], x["module"]),
    )

    payload = {
        "unit": "AUD-0056",
        "probe": "probe2_external_wallclock",
        "scope": target_args(),
        "modules": modules,
        "top_n": TOP_N,
        "runs": [
            {
                "run_id": r["run_id"],
                "module_count": r["module_count"],
                "top10_modules": r["top10_modules"],
                "ground_truth_module_rank": r["ground_truth_module_rank"],
                "ground_truth_in_top10": r["ground_truth_in_top10"],
                "results": r["results"],
            }
            for r in runs
        ],
        "ranking_stable": ranking_stable,
        "rank_mismatches": mismatches,
        "median_ranked": median_ranked,
        "ground_truth": {
            "module": GROUND_TRUTH_MODULE,
            "ok": ground_truth_ok,
        },
        "ok": ok,
        "contention_dominated": not ranking_stable,
        "ended_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    RAW.write_text("\n".join(lines) + "\n\n" + "\n".join(raw_chunks), encoding="utf-8")
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print(f"WROTE {OUT}")
    # Exit 0 when measurement completed and ground truth fired; instability
    # is recorded in JSON for the pack (honest BLOCKED), not a probe crash.
    return 0 if (measured_ok and ground_truth_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
