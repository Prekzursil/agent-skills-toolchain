#!/usr/bin/env python3
"""AUD-0056 NAMED PROBE 1: runner --durations report (recorded twice).

Catalog evidence_requirement Probe 1: "the runner's own --durations report."
Catalog tests_required: "record the profile twice and require the ranking of
the top 10 to be stable; an unstable ranking means the measurement is
contention-dominated and cannot be used as a baseline."

Method:
  1. Collect the documented command-center/ slice (fixtures/collectible_scope.py).
  2. Run pytest twice with --durations=0 --durations-min=0 -vv (shows every
     call/setup/teardown duration the runner attributes; without
     --durations-min=0, pytest hides sub-5ms rows even with -vv).
  3. Parse the durations table; aggregate `call` phase seconds per module
     (file path before ::). Rank modules descending.
  4. CONTROL: top-10 module ranking must be identical across the two runs.
     If not, mark ranking_stable=False (contention-dominated) -- honest
     BLOCKED path, never a fake SUCCESS baseline.
  5. GROUND TRUTH: fixtures/slow_control/test_deliberately_slow.py must appear
     in the slowest set (top-10 call rows and/or top-10 modules).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

PROBE = Path(__file__).resolve().parent
REPO = PROBE.parents[3]
FIXTURES = PROBE / "fixtures"
OUT = PROBE / "probe1-runner-durations.json"
RAW = PROBE / "probe1-runner-durations.raw.txt"

DUR_RE = re.compile(
    r"^([0-9]+(?:\.[0-9]+)?)s\s+(call|setup|teardown)\s+(\S+)\s*$"
)
GROUND_TRUTH_SUBSTRING = "test_aud0056_deliberately_slow_control"
GROUND_TRUTH_MODULE = (
    "command-center/p2-wave/probes/AUD-0056/fixtures/slow_control/"
    "test_deliberately_slow.py"
)
TOP_N = 10


def target_args() -> list[str]:
    sys.path.insert(0, str(FIXTURES))
    import collectible_scope  # noqa: E402

    return list(collectible_scope.TARGET_ARGS)


def parse_durations(text: str) -> list[dict]:
    rows: list[dict] = []
    in_table = False
    for line in text.splitlines():
        if "slowest" in line.lower() and "duration" in line.lower():
            in_table = True
            continue
        if not in_table:
            continue
        if line.startswith("=") and "passed" in line.lower():
            break
        if line.startswith("=") and in_table and rows:
            break
        m = DUR_RE.match(line.strip())
        if not m:
            continue
        seconds = float(m.group(1))
        phase = m.group(2)
        nodeid = m.group(3)
        module = nodeid.split("::", 1)[0]
        rows.append(
            {
                "seconds": seconds,
                "phase": phase,
                "nodeid": nodeid,
                "module": module,
            }
        )
    return rows


def aggregate_modules(rows: list[dict], phase: str = "call") -> list[dict]:
    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for r in rows:
        if r["phase"] != phase:
            continue
        totals[r["module"]] = totals.get(r["module"], 0.0) + r["seconds"]
        counts[r["module"]] = counts.get(r["module"], 0) + 1
    ranked = [
        {
            "module": mod,
            "call_seconds": round(totals[mod], 6),
            "call_rows": counts[mod],
        }
        for mod in totals
    ]
    ranked.sort(key=lambda x: (-x["call_seconds"], x["module"]))
    return ranked


def top_names(ranked: list[dict], n: int = TOP_N) -> list[str]:
    return [r["module"] for r in ranked[:n]]


def run_once(run_id: int) -> tuple[int, str, list[dict], list[dict]]:
    args = [
        sys.executable,
        "-m",
        "pytest",
        *target_args(),
        "--durations=0",
        "--durations-min=0",
        "-vv",
        "-q",
        "--tb=no",
        "-p",
        "no:cacheprovider",
    ]
    try:
        r = subprocess.run(
            args,
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=600,
        )
        out = (r.stdout or "") + (r.stderr or "")
        rc = r.returncode
    except subprocess.TimeoutExpired as e:
        rc, out = 124, f"TIMEOUT: {e}"
    rows = parse_durations(out)
    modules = aggregate_modules(rows)
    header = (
        f"\n===== RUN {run_id} rc={rc} duration_rows={len(rows)} "
        f"modules={len(modules)} =====\n"
    )
    return rc, header + out, rows, modules


def main() -> int:
    lines: list[str] = [
        "AUD-0056 NAMED PROBE 1: runner --durations report (x2)",
        "unit=AUD-0056",
        f"scope={target_args()}",
        f"started={datetime.now(timezone.utc).isoformat()}",
    ]

    runs: list[dict] = []
    raw_chunks: list[str] = []
    for run_id in (1, 2):
        rc, out, rows, modules = run_once(run_id)
        raw_chunks.append(out)
        call_rows = [r for r in rows if r["phase"] == "call"]
        call_rows_sorted = sorted(call_rows, key=lambda r: -r["seconds"])
        top_tests = [
            {"seconds": r["seconds"], "nodeid": r["nodeid"]}
            for r in call_rows_sorted[:TOP_N]
        ]
        top_mods = top_names(modules, TOP_N)
        gt_in_top_tests = any(
            GROUND_TRUTH_SUBSTRING in t["nodeid"] for t in top_tests
        )
        gt_mod_rank = next(
            (
                i + 1
                for i, m in enumerate(modules)
                if GROUND_TRUTH_MODULE in m["module"]
                or m["module"].endswith("test_deliberately_slow.py")
            ),
            None,
        )
        lines.append(
            f"RUN{run_id} rc={rc} call_rows={len(call_rows)} "
            f"modules={len(modules)} top10_modules={top_mods} "
            f"gt_in_top_tests={gt_in_top_tests} gt_mod_rank={gt_mod_rank}"
        )
        runs.append(
            {
                "run_id": run_id,
                "returncode": rc,
                "duration_row_count": len(rows),
                "call_row_count": len(call_rows),
                "module_count": len(modules),
                "top10_modules": top_mods,
                "top10_tests": top_tests,
                "modules_ranked": modules,
                "ground_truth_in_top10_tests": gt_in_top_tests,
                "ground_truth_module_rank": gt_mod_rank,
            }
        )

    ranking_stable = (
        len(runs) == 2
        and bool(runs[0]["top10_modules"])
        and runs[0]["top10_modules"] == runs[1]["top10_modules"]
    )
    # Prefer exact list equality; also record pairwise position mismatches.
    mismatches: list[dict] = []
    if len(runs) == 2:
        a, b = runs[0]["top10_modules"], runs[1]["top10_modules"]
        for i in range(max(len(a), len(b))):
            left = a[i] if i < len(a) else None
            right = b[i] if i < len(b) else None
            if left != right:
                mismatches.append({"rank": i + 1, "run1": left, "run2": right})

    ground_truth_ok = all(
        r.get("ground_truth_in_top10_tests")
        or (
            r.get("ground_truth_module_rank") is not None
            and r["ground_truth_module_rank"] <= TOP_N
        )
        for r in runs
    ) and bool(runs)

    ok = (
        all(r["call_row_count"] > 0 for r in runs)
        and ranking_stable
        and ground_truth_ok
    )
    # Even if ranking unstable, probes measured something real; pack will
    # record contention-dominated defect. Probe "ok" requires stable+control.
    lines.append(
        f"CONTROL ranking_stable={ranking_stable} mismatches={len(mismatches)} "
        f"ground_truth_ok={ground_truth_ok} ok={ok}"
    )
    if not ranking_stable:
        lines.append(
            "NOTE: top-10 module ranking unstable across two runs -- "
            "measurement is contention-dominated and cannot be used as a baseline"
        )

    payload = {
        "unit": "AUD-0056",
        "probe": "probe1_runner_durations",
        "scope": target_args(),
        "top_n": TOP_N,
        "runs": runs,
        "ranking_stable": ranking_stable,
        "rank_mismatches": mismatches,
        "ground_truth": {
            "nodeid_substring": GROUND_TRUTH_SUBSTRING,
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
    return 0 if (all(r["call_row_count"] > 0 for r in runs) and ground_truth_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
