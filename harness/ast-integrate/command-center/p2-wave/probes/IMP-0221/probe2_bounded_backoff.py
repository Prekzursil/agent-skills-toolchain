#!/usr/bin/env python3
"""Named probe 2: backoff is bounded; the run reaches a terminal state.

Perpetual 429s: plan_retry caps retries, Retry-After is capped at the
dispatch backoff cap, every unit gets a typed rate-limited terminal, and
max_concurrency is unchanged. Negative control: a loop that ignores
plan_retry hits a tripwire (would not terminate).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib import TOOLS_AGENTSPEC, load_receipt  # noqa: E402

sys.path.insert(0, str(TOOLS_AGENTSPEC))
from agentspec.clock import FakeClock  # noqa: E402
from agentspec.quota import Quota  # noqa: E402
from agentspec.rails import Always429Rail, OverloadRail  # noqa: E402
from agentspec.retry import (  # noqa: E402
    RATE_LIMITED_BACKOFF_CAP_MS,
    RATE_LIMITED_MAX_RETRIES,
)
from agentspec.scheduler import (  # noqa: E402
    QuotaAwareScheduler,
    unbounded_429_loop,
)

N = 12


def main() -> int:
    load_receipt()
    units = [f"x{i:03d}" for i in range(N)]

    clock = FakeClock()
    rail = Always429Rail(clock, retry_after_s=2.0)
    report = QuotaAwareScheduler(
        Quota(tokens_per_window=5, window_s=1.0),
        max_concurrency=8,
        clock=clock,
    ).run(units, rail)

    if not report.terminated:
        print("FAILED:IMP-0221-probe2 run did not terminate")
        return 1
    if report.lost != 0 or report.accounted != N or report.accounting_pct != 100.0:
        print("FAILED:IMP-0221-probe2 accounting not 100% under perpetual 429")
        print(json.dumps(report.as_dict(), indent=2))
        return 1
    if report.rate_limited != N:
        print("FAILED:IMP-0221-probe2 expected all units typed rate-limited")
        print(json.dumps(report.as_dict(), indent=2))
        return 1
    if report.max_attempts_seen > RATE_LIMITED_MAX_RETRIES + 1:
        print(
            "FAILED:IMP-0221-probe2 attempts exceed bound "
            f"{report.max_attempts_seen} > {RATE_LIMITED_MAX_RETRIES + 1}"
        )
        return 1
    if report.max_wait_ms_seen > RATE_LIMITED_BACKOFF_CAP_MS:
        print("FAILED:IMP-0221-probe2 wait exceeded backoff cap")
        return 1
    if not report.concurrency_unchanged:
        print("FAILED:IMP-0221-probe2 429 reduced max_concurrency")
        return 1

    huge_clock = FakeClock()
    huge = QuotaAwareScheduler(
        Quota(tokens_per_window=5, window_s=1.0),
        max_concurrency=8,
        clock=huge_clock,
    ).run(["h1", "h2"], Always429Rail(huge_clock, huge=True))
    if huge.max_wait_ms_seen > RATE_LIMITED_BACKOFF_CAP_MS:
        print("FAILED:IMP-0221-probe2 huge Retry-After was not capped")
        return 1
    if huge.lost != 0 or huge.rate_limited != 2:
        print("FAILED:IMP-0221-probe2 huge Retry-After lost work")
        return 1

    ov_clock = FakeClock()
    ov = QuotaAwareScheduler(
        Quota(tokens_per_window=5, window_s=1.0),
        max_concurrency=4,
        clock=ov_clock,
    ).run(["o1", "o2"], OverloadRail(ov_clock))
    if ov.max_concurrency_start != 4 or ov.max_concurrency_end != 4:
        print("FAILED:IMP-0221-probe2 529 reduced concurrency")
        return 1
    if ov.overload != 2 or ov.lost != 0:
        print("FAILED:IMP-0221-probe2 529 was not a typed terminal")
        return 1

    unbound = unbounded_429_loop(Always429Rail(FakeClock()), tripwire=80)
    if not unbound["hit_tripwire"]:
        print("FAILED:IMP-0221-probe2 unbounded control did not hit tripwire")
        return 1

    payload = {
        "pass": True,
        "probe": "probe2-bounded-backoff",
        "unit_id": "IMP-0221",
        "perpetual_429": report.as_dict(),
        "huge_retry_after": huge.as_dict(),
        "overload_529": ov.as_dict(),
        "unbounded_control": unbound,
        "cap_ms": RATE_LIMITED_BACKOFF_CAP_MS,
        "max_retries": RATE_LIMITED_MAX_RETRIES,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        "SUCCESS:IMP-0221-probe2 bounded backoff terminated "
        f"rate_limited={report.rate_limited}/{N} max_wait_ms={report.max_wait_ms_seen}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
