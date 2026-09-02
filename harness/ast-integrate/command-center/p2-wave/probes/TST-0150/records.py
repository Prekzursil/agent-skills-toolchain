"""Durable ledger record kinds for the TST-0150 monitor."""
from __future__ import annotations

RUN_STARTED = "run_started"
UNIT_DISPATCHED = "unit_dispatched"
REMOTE_COMPLETED = "remote_completed"
UNIT_HARVESTED = "unit_harvested"
MONITOR_DIED = "monitor_died"

KINDS = frozenset(
    {RUN_STARTED, UNIT_DISPATCHED, REMOTE_COMPLETED, UNIT_HARVESTED, MONITOR_DIED}
)

# Unit statuses the reconciler treats as terminal in the ledger.
TERMINAL_STATUSES = frozenset({"harvested", "remote_completed", "failed"})
