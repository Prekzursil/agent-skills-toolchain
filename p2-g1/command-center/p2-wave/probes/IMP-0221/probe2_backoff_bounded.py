"""IMP-0221 probe 2 (verifier): backoff is bounded - the run terminates, never retries forever.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0221/probe2_backoff_bounded.py
Exit 0 iff the always-429 run TERMINATES with typed rate-limited terminal records,
attempts and waits stay inside the declared policy caps, AND the naive-drop
counterfactual loses units (both-states control proving zero-lost is load-bearing).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.clock import FixedClock  # noqa: E402
from agentspec.rails import Always429Rail, TokenBucketRail  # noqa: E402
from agentspec.retry import RATE_LIMITED_BACKOFF_CAP_MS, RATE_LIMITED_MAX_RETRIES  # noqa: E402
from agentspec.scheduler import QuotaAwareScheduler, run_naive_drop  # noqa: E402

clock = FixedClock()
sched = QuotaAwareScheduler(quota=None, max_concurrency=4, clock=clock)
report = sched.run((f"u{i}" for i in range(10)), Always429Rail(clock, retry_after_s=2.0))
d = report.as_dict()

counter_clock = FixedClock()
counter_rail = TokenBucketRail(capacity=1, refill_per_s=0.001, clock=counter_clock, retry_after_s=1.0)
naive = run_naive_drop((f"u{i}" for i in range(10)), counter_rail)

ok = (
    report.terminated is True
    and report.rate_limited == 10
    and report.lost == 0
    and report.accounting_pct == 100.0
    and report.max_attempts_seen <= RATE_LIMITED_MAX_RETRIES + 1
    and report.max_wait_ms_seen <= RATE_LIMITED_BACKOFF_CAP_MS
    and naive.lost > 0
)
out = {"probe": "probe2-backoff-bounded", "unit_id": "IMP-0221",
       "report": d, "caps": {"max_retries": RATE_LIMITED_MAX_RETRIES, "cap_ms": RATE_LIMITED_BACKOFF_CAP_MS},
       "counterfactual_naive_lost": naive.lost, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe2-bounded.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0221-probe2 backoff unbounded or work lost")
    raise SystemExit(1)
print("SUCCESS:IMP-0221-probe2 bounded backoff terminates; caps held; naive counterfactual loses")
