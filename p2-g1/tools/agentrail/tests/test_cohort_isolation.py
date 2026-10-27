"""IMP-0222: per-unit pipeline isolation - one hung unit cannot deadlock the cohort."""
from __future__ import annotations

import time

from agentrail.runner import (
    TIMEOUT,
    run_cohort_isolated,
)


def _cohort_jobs(n: int = 50, hang_at: int = 7, work_s: float = 0.001, hang_s: float = 2.0):
    jobs = {}
    for i in range(n):
        if i == hang_at:
            jobs[f"U-{i:04d}"] = (lambda s=hang_s: time.sleep(s) or "done")
        else:
            jobs[f"U-{i:04d}"] = (lambda s=work_s: time.sleep(s) or "done")
    return jobs


def test_planted_hang_49_of_50_complete_one_typed_timeout() -> None:
    report = run_cohort_isolated(_cohort_jobs(), timeout_s=0.5, max_workers=10)
    assert report["submitted"] == 50
    assert report["completed_count"] == 49
    assert report["timed_out_count"] == 1
    assert report["timed_out_units"] == ["U-0007"]
    ledger_by_id = {r["unit_id"]: r for r in report["ledger"]}
    assert ledger_by_id["U-0007"]["status"] == "timeout-typed"
    assert ledger_by_id["U-0007"]["declared_timeout_s"] == 0.5
    assert all(r["status"] == "completed" for r in report["ledger"] if r["unit_id"] != "U-0007")


def test_no_unit_waits_past_declared_timeout_timestamp_audit() -> None:
    report = run_cohort_isolated(_cohort_jobs(), timeout_s=0.5, max_workers=10)
    assert report["no_completed_unit_past_timeout"] is True
    for r in report["ledger"]:
        if r["status"] == "completed":
            assert r["elapsed_s"] < 0.5, f"{r['unit_id']} exceeded the declared timeout"
    # cohort wall is bounded by max(healthy work, timeout), NOT by the hung sibling
    assert report["wall_s"] < 1.5, "cohort wall must not wait on the hung sibling"
    assert report["abandoned_workers"] >= 1, "the hung worker must be accounted as abandoned"


def test_barrier_coupled_counterfactual_stalls() -> None:
    """Both-states control: the barrier-coupled model DOES stall the whole cohort,
    so the isolation property is load-bearing, not vacuous."""
    from agentrail.runner import CoupledBarrierRunner, make_cohort, summarize

    cohort = make_cohort(n=50, hang_at=7)
    coupled = summarize(cohort, isolated=False)
    assert coupled["terminal"] == TIMEOUT
    assert coupled["completed"] == [], "coupled barrier must stall ALL siblings"
    isolated = summarize(cohort, isolated=True)
    assert isolated["terminal"] == "completed" and len(isolated["completed"]) == 49
