#!/usr/bin/env python3
"""Probe 1: empty-input gate + cold vs warm distributions (perf_counter / in-process).

Exits 0 only when every case has non-zero input size, a zero-size mutant fails
the run without emitting a number, and both thermal states are reported with
n, median, and spread.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import inventory as I  # noqa: E402

OUT = HERE / "probe1-empty-thermal.raw.json"
WORKER = HERE / "harness.py"


def _worker_env() -> dict:
    # Python 3.14 argparse colorizer lazily imports _colorize -> dataclasses
    # -> inspect -> annotationlib -> ast; tools/ast.py on an inherited
    # PYTHONPATH shadows stdlib ast and closes an import cycle that kills
    # the worker before it measures anything (measured 2026-10-24, shard 5).
    # The worker is stdlib-only, so it runs with PYTHONPATH scrubbed.
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def cold_once(case_id: str) -> dict:
    cmd = [
        sys.executable,
        "-B",
        str(WORKER),
        "--once",
        case_id,
        "--clock",
        "perf_counter",
    ]
    p = subprocess.run(
        cmd, capture_output=True, text=True, cwd=str(H.REPO), env=_worker_env()
    )
    if p.returncode != 0:
        raise SystemExit(f"FAILED:CNF-0180-probe1 cold worker rc={p.returncode} {p.stderr[-400:]}")
    row = json.loads(p.stdout.splitlines()[-1])
    row["thermal"] = "cold"
    return row


def stop_hook_input_size() -> int:
    root = H.REPO / "command-center/p2-wave/probes/ARC-0005/fixtures/control"
    if not root.is_dir():
        return 0
    return sum(1 for p in root.rglob("*") if p.is_file())


def remeasure_stop_hook(n: int = H.N_REPS) -> dict:
    """Independent re-measure of the live 0.925 ms single-sample claim.

    Times only stop_hook.run() on the existing non-empty control trees.
    """
    hook_dir = H.REPO / "command-center/p2-wave/probes/ARC-0005"
    input_files = stop_hook_input_size()
    if input_files <= 0:
        return {
            "case_id": "stop-hook-live-claim",
            "input_size_files": 0,
            "pass_nonempty": False,
            "error": "control fixtures empty or absent",
        }
    sys.path.insert(0, str(hook_dir))
    import stop_hook as SH  # noqa: E402

    def one() -> float:
        t0 = time.perf_counter()
        SH.run()
        return (time.perf_counter() - t0) * 1000.0

    cold = []
    for _ in range(n):
        # Recreate the module-level path walk by invoking run() after a tiny
        # delay; first of each pair is treated as colder than the primed pair.
        cold.append(one())
    for _ in range(3):
        one()
    warm = [one() for _ in range(n)]
    claimed = 0.925
    warm_sum = H.summarize(warm)
    cold_sum = H.summarize(cold)
    inside_warm_iqr = warm_sum["q1_ms"] <= claimed <= warm_sum["q3_ms"]
    return {
        "case_id": "stop-hook-live-claim",
        "claimed_ms": claimed,
        "input_size_files": input_files,
        "pass_nonempty": input_files > 0,
        "cold": {"thermal": "cold-ish-inprocess", "distribution": cold_sum},
        "warm": {"thermal": "warm", "distribution": warm_sum},
        "claimed_inside_warm_iqr": inside_warm_iqr,
        "single_sample_protocol_ok": False,
        "note": (
            "Original claim is n=1 with plant+detect+hook bundled. This "
            "re-measure times only stop_hook.run() and reports a distribution."
        ),
    }


def main() -> int:
    pre_state = H.machine_state()
    empty = H.empty_input_control()
    if not empty["pass"]:
        print("FAILED:CNF-0180-probe1 empty-input control did not fail a zero-size case")
        return 1

    cases = []
    for case in H.CASES:
        if int(case["bytes"]) <= 0 or int(case["rounds"]) <= 0:
            print(f"FAILED:CNF-0180-probe1 registered case has zero input: {case}")
            return 1
        cold_rows = [cold_once(case["id"]) for _ in range(H.N_REPS)]
        for row in cold_rows:
            if int(row.get("input_size_bytes") or 0) <= 0:
                print(f"FAILED:CNF-0180-probe1 cold run had empty input: {row}")
                return 1
        warm = H.warm_samples(case, H.N_REPS)
        cold_ms = [r["elapsed_ms"] for r in cold_rows]
        cases.append(
            {
                "case_id": case["id"],
                "input_size_bytes": case["bytes"],
                "rounds": case["rounds"],
                "machine_state_before_cold": H.machine_state(),
                "cold": {
                    "thermal": "cold",
                    "n": len(cold_ms),
                    "distribution": H.summarize(cold_ms),
                    "runs": cold_rows,
                },
                "warm": warm,
            }
        )

    live = remeasure_stop_hook()
    post_state = H.machine_state()
    claims = I.census()
    doc = {
        "probe": "probe1-empty-and-thermal",
        "unit_id": "CNF-0180",
        "instrument": "time.perf_counter + hashlib.sha256 in-process (warm); fresh python -B subprocess first-iter (cold)",
        "empty_input_control": empty,
        "all_cases_nonzero_input": True,
        "n_reps": H.N_REPS,
        "cases": cases,
        "live_claim_remeasure": live,
        "claimed_figures_inventory": claims,
        "machine_state_before": pre_state,
        "machine_state_after": post_state,
        "pass": bool(empty["pass"] and live.get("pass_nonempty") and cases),
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for c in cases:
        cd = c["cold"]["distribution"]
        wd = c["warm"]["distribution"]
        print(
            f"case={c['case_id']} input_bytes={c['input_size_bytes']} "
            f"cold_median_ms={cd['median_ms']:.4f} warm_median_ms={wd['median_ms']:.4f} "
            f"cold_n={cd['n']} warm_n={wd['n']} iqr_warm={wd['iqr_ms']:.4f}"
        )
    print(
        f"empty_fail={empty['pass']} stop_hook_files={live.get('input_size_files')} "
        f"claimed_0.925_inside_warm_iqr={live.get('claimed_inside_warm_iqr')}"
    )
    if not doc["pass"]:
        print("FAILED:CNF-0180-probe1 controls")
        return 1
    print("SUCCESS:CNF-0180-probe1 empty-input and cold/warm distributions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
