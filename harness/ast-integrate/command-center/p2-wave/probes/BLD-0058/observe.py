"""Independent reviewer path: derive the binding RPM from traces only.

Do not load the documented-limits table. Burst successes at t=0 are the
observed ceiling; a stagger built from that ceiling must be 429-free.
"""
from __future__ import annotations

from sim import FIXTURE_RPM, TokenBucket, burst_times, fire, stagger_times


def observed_burst_capacity(n: int, rpm: int = FIXTURE_RPM) -> int:
    result = fire(burst_times(n), rpm=rpm)
    if result.n_429 <= 0:
        raise AssertionError(
            "observer vacuous: need 429s to know the burst actually hit a ceiling"
        )
    return result.n_200


def stagger_from_observed(n: int, observed_rpm: int) -> dict:
    times = stagger_times(n, admit_rpm=float(observed_rpm))
    result = fire(times, rpm=observed_rpm)
    return {
        "n": n,
        "observed_rpm": observed_rpm,
        "stagger_429": result.n_429,
        "stagger_200": result.n_200,
    }


def rederive(n_10x: int, rpm: int = FIXTURE_RPM) -> dict:
    probe_n = max(n_10x, rpm * 4)
    observed = observed_burst_capacity(probe_n, rpm=rpm)
    check = stagger_from_observed(min(n_10x, rpm * 3), observed)
    if check["stagger_429"] != 0:
        raise AssertionError(f"observed stagger still 429s: {check}")
    return {
        "method": "burst-success-count-at-t0",
        "probe_n": probe_n,
        "observed_rpm": observed,
        "stagger_confirm": check,
        "reads_documented_tables": False,
    }


def bucket_independent_of_docs_constant() -> bool:
    b = TokenBucket(7)
    got = 0
    for _ in range(20):
        if b.try_take(0):
            got += 1
    return got == 7
