"""Post-restart recovery: fold the durable ledger from disk in a fresh pass.

Units the remote side completed during the outage (REMOTE_COMPLETED in the
ledger but never UNIT_HARVESTED) are harvested during recovery — durably,
by appending the harvest record before applying it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from monitor import LiveMonitor, read_records
from records import MONITOR_DIED, REMOTE_COMPLETED, UNIT_DISPATCHED, UNIT_HARVESTED
from state import LedgerState, apply_record

MONITOR_DIES_MID_RUN = "monitor-dies-while-remote-work-continues"


@dataclass
class RecoveryReport:
    state: LedgerState
    dispatch_count: int = 0
    harvested_during_recovery: list[str] = field(default_factory=list)
    failure_classes: list[str] = field(default_factory=list)


def recover(ledger: Path) -> RecoveryReport:
    """Rebuild state from the ledger FILE (never from a prior RAM snapshot)."""
    ledger = Path(ledger)
    records = read_records(ledger)
    state = LedgerState()
    died_seq: int | None = None
    remote_after_death = False
    dispatch_count = 0
    for rec in records:
        apply_record(state, rec)
        if rec.get("kind") == UNIT_DISPATCHED:
            dispatch_count += 1
        elif rec.get("kind") == MONITOR_DIED:
            died_seq = int(rec.get("seq") or 0)
        elif rec.get("kind") == REMOTE_COMPLETED and died_seq is not None:
            if int(rec.get("seq") or 0) > died_seq:
                remote_after_death = True

    # Harvest remote completions the dead monitor never got to harvest.
    harvested: list[str] = []
    run_id = state.run_id or ""
    fresh = LiveMonitor(ledger, run_id, sorted(state.units))
    fresh.state = state
    for uid in sorted(state.units):
        unit = state.units[uid]
        if unit.get("status") == "remote_completed":
            fresh.harvest(uid, str(unit.get("receipt_hash") or ""))
            harvested.append(uid)

    failure_classes: list[str] = []
    if remote_after_death:
        failure_classes.append(MONITOR_DIES_MID_RUN)

    return RecoveryReport(
        state=state,
        dispatch_count=dispatch_count,
        harvested_during_recovery=harvested,
        failure_classes=failure_classes,
    )
