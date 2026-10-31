"""IMP-0221: quota-aware scheduler - synthetic 429 storm loses ZERO units; backoff bounded."""
from __future__ import annotations

from agentspec.clock import FixedClock
from agentspec.rails import Always429Rail, TokenBucketRail
from agentspec.retry import RATE_LIMITED_BACKOFF_CAP_MS, RATE_LIMITED_MAX_RETRIES
from agentspec.scheduler import QuotaAwareScheduler, run_naive_drop


def _storm_scheduler() -> tuple[QuotaAwareScheduler, VirtualClock]:
    clock = FixedClock()
    return QuotaAwareScheduler(quota=None, max_concurrency=4, clock=clock), clock


def test_synthetic_429_storm_zero_lost_units() -> None:
    """Storm: capacity 3, refill 0.5/s, 40 units -> throughput degraded (waits happen)
    but accounting sums to 100%: every unit completes or carries a typed record."""
    sched, clock = _storm_scheduler()
    rail = TokenBucketRail(capacity=3, refill_per_s=0.5, clock=clock, retry_after_s=1.0)
    report = sched.run((f"u{i}" for i in range(40)), rail)
    assert report.submitted == 40
    assert report.lost == 0
    assert report.accounted == report.submitted, "every unit must carry a terminal record"
    assert report.accounting_pct == 100.0
    kinds = {r.status for r in report.records}
    assert kinds <= {"completed", "rate-limited", "overload", "error"}, kinds
    assert "completed" in kinds, "storm must degrade throughput, not refuse everything"
    assert report.records[0].status in {"completed", "rate-limited"}


def test_backoff_bounded_run_terminates() -> None:
    """Always-429 rail: the run TERMINATES with typed rate-limited records; the retry
    count and waits stay within the bounded-backoff policy (never retries forever)."""
    sched, clock = _storm_scheduler()
    rail = Always429Rail(clock, retry_after_s=2.0)
    report = sched.run((f"u{i}" for i in range(10)), rail)
    assert report.terminated is True
    assert report.completed == 0
    assert report.rate_limited == 10
    assert report.lost == 0
    assert report.accounting_pct == 100.0
    assert report.max_attempts_seen <= RATE_LIMITED_MAX_RETRIES + 1
    assert report.max_wait_ms_seen <= RATE_LIMITED_BACKOFF_CAP_MS


def test_naive_drop_is_the_loss_counterfactual() -> None:
    """Both-states control: the naive single-attempt scheduler is where work is LOST;
    the quota-aware scheduler is not. If the naive scheduler stopped losing units this
    control would stop discriminating."""
    clock = FixedClock()
    rail = TokenBucketRail(capacity=1, refill_per_s=0.001, clock=clock, retry_after_s=1.0)
    naive = run_naive_drop((f"u{i}" for i in range(10)), rail)
    assert naive.lost == 9, "naive scheduler must LOSE rate-limited units (control)"
    assert all(r.status == "lost" for r in naive.records if r.unit_id != "u0")
