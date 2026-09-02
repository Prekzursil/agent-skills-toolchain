"""Shared probe paths for IMP-0221."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS_AGENTSPEC = REPO / "tools" / "agentspec"
if str(TOOLS_AGENTSPEC) not in sys.path:
    sys.path.insert(0, str(TOOLS_AGENTSPEC))

OUT_REL = "command-center/receipts/IMP-0221.json"
OUT = REPO / OUT_REL
SENTINEL = "SUCCESS:IMP-0221"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def load_receipt() -> dict:
    if not OUT.is_file() or OUT.stat().st_size <= 0:
        raise SystemExit("FAILED:IMP-0221 receipt missing")
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise SystemExit("FAILED:IMP-0221 receipt is not an object")
    text = json.dumps(doc)
    if SENTINEL not in text:
        raise SystemExit("FAILED:IMP-0221 sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        raise SystemExit(f"FAILED:IMP-0221 self-declared:{st}")
    if str(doc.get("unit_id") or "") != "IMP-0221":
        raise SystemExit("FAILED:IMP-0221 unit_id mismatch")
    return doc


N_STORM = 40
DECLARED_QUOTA = 20.0
DECLARED_WINDOW_S = 1.0
RAIL_CAPACITY = 2.0
RAIL_REFILL_PER_S = 2.0
MAX_CONCURRENCY = 8


def run_accounting_pair():
    """Optimistic declared quota vs a tighter provider bucket.

    Declared quota 20/s against a 2-token bucket produces 429s. Quota-aware
    admission still accounts 100%; naive drop loses units; elapsed exceeds a
    healthy rail.
    """
    from agentspec.clock import FakeClock
    from agentspec.quota import Quota
    from agentspec.rails import HealthyRail, TokenBucketRail
    from agentspec.scheduler import QuotaAwareScheduler, run_naive_drop

    units = [f"u{i:03d}" for i in range(N_STORM)]
    healthy_clock = FakeClock()
    healthy = QuotaAwareScheduler(
        Quota(tokens_per_window=DECLARED_QUOTA, window_s=DECLARED_WINDOW_S),
        max_concurrency=MAX_CONCURRENCY,
        clock=healthy_clock,
    ).run(units, HealthyRail(healthy_clock))
    storm_clock = FakeClock()
    storm = QuotaAwareScheduler(
        Quota(tokens_per_window=DECLARED_QUOTA, window_s=DECLARED_WINDOW_S),
        max_concurrency=MAX_CONCURRENCY,
        clock=storm_clock,
    ).run(
        units,
        TokenBucketRail(
            capacity=RAIL_CAPACITY,
            refill_per_s=RAIL_REFILL_PER_S,
            clock=storm_clock,
            retry_after_s=1.0,
        ),
    )
    naive = run_naive_drop(
        units,
        TokenBucketRail(
            capacity=RAIL_CAPACITY,
            refill_per_s=RAIL_REFILL_PER_S,
            clock=FakeClock(),
            retry_after_s=1.0,
        ),
    )
    return units, healthy, storm, naive
