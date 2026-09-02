"""Durable ledger record kinds shared by the event-ledger tools.

These match the kinds emitted by monitor.py and folded by recover.py.
"""
from __future__ import annotations

RUN_STARTED = "run_started"
UNIT_DISPATCHED = "unit_dispatched"
UNIT_HARVESTED = "unit_harvested"
REMOTE_COMPLETE = "remote_complete"
MONITOR_DIED = "monitor_died"

KINDS = frozenset(
    {RUN_STARTED, UNIT_DISPATCHED, UNIT_HARVESTED, REMOTE_COMPLETE, MONITOR_DIED}
)

TERMINAL_STATUSES = frozenset({"harvested", "remote_completed", "failed"})
