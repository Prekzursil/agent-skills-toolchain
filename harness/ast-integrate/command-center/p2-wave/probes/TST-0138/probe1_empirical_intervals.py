#!/usr/bin/env python3
"""Probe 1: empirical interval samples across 50 runs (signal a).

PASS requires:
  * 50 independently drawn full-jitter schedules
  * at least two distinct interval tuples (non-determinism)
  * every schedule sums strictly below timeout_seconds
  * catalog-policy runs are non-empty (not a vacuous all-zero pass)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import backoff as B  # noqa: E402

ART = REPO / "command-center/receipts/TST-0138.json"
N_RUNS = 50
TIGHT = dict(max_attempts=8, base=10.0, cap=30.0, timeout_seconds=50.0)


def check_artifact() -> str | None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return "catalog output_path missing or empty"
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:TST-0138" not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return f"artifact self-declared {st}"
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if str(report.get("kind") or "") != "scheduler_report":
        return "report.kind is not scheduler_report"
    return None


def draw_runs(n: int, **kwargs) -> list[list[float]]:
    return [B.retry_schedule(**kwargs) for _ in range(n)]


def unique_tuples(runs: list[list[float]]) -> int:
    return len({tuple(r) for r in runs})


def main() -> int:
    art_err = check_artifact()
    if art_err:
        print(f"FAILED:TST-0138-probe1 {art_err}")
        return 1

    catalog_kwargs = dict(
        max_attempts=B.CATALOG_ATTEMPTS,
        base=B.CATALOG_BASE,
        cap=B.CATALOG_CAP,
        timeout_seconds=B.CATALOG_TIMEOUT,
    )
    catalog_runs = draw_runs(N_RUNS, **catalog_kwargs)
    catalog_sums = [B.schedule_sum(s) for s in catalog_runs]
    if any(s >= B.CATALOG_TIMEOUT for s in catalog_sums):
        print("FAILED:TST-0138-probe1 catalog schedule met or exceeded timeout")
        return 1
    if any(len(s) != B.CATALOG_ATTEMPTS - 1 for s in catalog_runs):
        print("FAILED:TST-0138-probe1 catalog schedule length is not attempts-1")
        return 1
    if unique_tuples(catalog_runs) < 2:
        print("FAILED:TST-0138-probe1 catalog interval sets were identical across 50 runs")
        return 1
    if all(s == 0.0 for row in catalog_runs for s in row):
        print("FAILED:TST-0138-probe1 catalog delays were all zero (vacuous jitter)")
        return 1

    # Two explicit runs, as the unit text requires "interval sets from two runs differ".
    run_a = B.retry_schedule(**catalog_kwargs)
    run_b = B.retry_schedule(**catalog_kwargs)
    differ_tries = 1
    while run_a == run_b and differ_tries < 8:
        run_b = B.retry_schedule(**catalog_kwargs)
        differ_tries += 1
    if run_a == run_b:
        print("FAILED:TST-0138-probe1 two catalog runs produced identical intervals")
        return 1

    tight_runs = draw_runs(N_RUNS, **TIGHT)
    tight_unclipped = B.worst_case_unclipped(
        TIGHT["max_attempts"], TIGHT["base"], TIGHT["cap"]
    )
    if tight_unclipped < TIGHT["timeout_seconds"]:
        print(
            "FAILED:TST-0138-probe1 tight fixture is not load-bearing: "
            f"unclipped={tight_unclipped} timeout={TIGHT['timeout_seconds']}"
        )
        return 1
    if any(B.schedule_sum(s) >= TIGHT["timeout_seconds"] for s in tight_runs):
        print("FAILED:TST-0138-probe1 tight schedule met or exceeded timeout")
        return 1
    if unique_tuples(tight_runs) < 2:
        print("FAILED:TST-0138-probe1 tight interval sets were identical across 50 runs")
        return 1

    summary = {
        "catalog_runs": N_RUNS,
        "catalog_unique_interval_sets": unique_tuples(catalog_runs),
        "catalog_sum_min": min(catalog_sums),
        "catalog_sum_max": max(catalog_sums),
        "catalog_two_runs_differ": True,
        "catalog_two_run_retry_draws": differ_tries,
        "tight_runs": N_RUNS,
        "tight_unique_interval_sets": unique_tuples(tight_runs),
        "tight_unclipped_worst_case": tight_unclipped,
        "tight_timeout": TIGHT["timeout_seconds"],
        "tight_clipping_load_bearing": True,
        "all_sums_strictly_below_timeout": True,
        "pass": True,
        "probe": "probe1-empirical-intervals",
        "unit_id": "TST-0138",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"catalog unique={summary['catalog_unique_interval_sets']}/50 "
        f"sum=[{summary['catalog_sum_min']:.6f},{summary['catalog_sum_max']:.6f}] "
        f"two_runs_differ=True tight_unclipped={tight_unclipped:.3f}>"
        f"{TIGHT['timeout_seconds']}"
    )
    print("SUCCESS:TST-0138-probe1 empirical jitter and timeout bound")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
