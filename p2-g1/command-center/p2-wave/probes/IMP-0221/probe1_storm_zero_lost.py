"""IMP-0221 probe 1 (source): synthetic 429 storm degrades throughput, loses ZERO units.

Re-run: PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/IMP-0221/probe1_storm_zero_lost.py
Exit 0 iff the storm's accounting sums to 100% (completed + typed rate-limited) and
every terminal record is typed - none absent, none 'lost'.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

W = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(W / "tools" / "agentspec"))
from agentspec.clock import FixedClock  # noqa: E402
from agentspec.rails import TokenBucketRail  # noqa: E402
from agentspec.scheduler import QuotaAwareScheduler  # noqa: E402

clock = FixedClock()
sched = QuotaAwareScheduler(quota=None, max_concurrency=4, clock=clock)
rail = TokenBucketRail(capacity=3, refill_per_s=0.5, clock=clock, retry_after_s=1.0)
report = sched.run((f"u{i}" for i in range(40)), rail)
d = report.as_dict()
tally = {}
for r in report.records:
    tally[r.status] = tally.get(r.status, 0) + 1
ok = (
    report.submitted == 40
    and report.lost == 0
    and report.accounted == 40
    and report.accounting_pct == 100.0
    and "completed" in tally
    and set(tally) <= {"completed", "rate-limited", "overload", "error"}
)
out = {"probe": "probe1-429-storm-accounting", "unit_id": "IMP-0221",
       "report": d, "tally": tally, "pass": ok}
print(json.dumps(out, sort_keys=True))
RAW = Path(__file__).resolve().parent / "probe1-storm.raw.json"
RAW.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
if not ok:
    print("FAILED:IMP-0221-probe1 storm lost work or mis-accounted")
    raise SystemExit(1)
print("SUCCESS:IMP-0221-probe1 40-unit storm: 100% accounted, zero lost, all records typed")
