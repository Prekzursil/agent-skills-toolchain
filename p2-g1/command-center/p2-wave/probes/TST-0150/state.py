"""Fold ledger records into monitor state. Pure; never touches disk."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from records import (
    MONITOR_DIED,
    REMOTE_COMPLETED,
    RUN_STARTED,
    TERMINAL_STATUSES,
    UNIT_DISPATCHED,
    UNIT_HARVESTED,
)


@dataclass
class LedgerState:
    run_id: str | None = None
    last_seq: int = 0
    monitor_alive: bool = True
    units: dict[str, dict[str, Any]] = field(default_factory=dict)

    def in_flight_ids(self) -> list[str]:
        return sorted(
            uid
            for uid, unit in self.units.items()
            if unit.get("status") not in TERMINAL_STATUSES
        )

    def canonical(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "last_seq": self.last_seq,
            "monitor_alive": self.monitor_alive,
            "units": {uid: dict(unit) for uid, unit in sorted(self.units.items())},
            "in_flight_ids": self.in_flight_ids(),
        }


def _unit(state: LedgerState, unit_id: str) -> dict[str, Any]:
    return state.units.setdefault(
        unit_id, {"unit_id": unit_id, "status": "unknown", "receipt_hash": None, "fencing_token": None}
    )


def apply_record(state: LedgerState, rec: dict[str, Any]) -> LedgerState:
    """Apply one ledger record to *state* (RAM fold only; no disk writes)."""
    kind = rec.get("kind")
    seq = int(rec.get("seq") or 0)
    state.last_seq = max(state.last_seq, seq)
    if kind == RUN_STARTED:
        state.run_id = str(rec.get("run_id") or "")
        return state
    if kind == MONITOR_DIED:
        state.monitor_alive = False
        return state
    unit_id = rec.get("unit_id")
    if not unit_id:
        return state
    unit = _unit(state, str(unit_id))
    if kind == UNIT_DISPATCHED:
        unit["status"] = "dispatched"
        unit["fencing_token"] = rec.get("fencing_token")
    elif kind == REMOTE_COMPLETED:
        # remote completion never downgrades an already-harvested unit
        if unit.get("status") != "harvested":
            unit["status"] = "remote_completed"
        unit["receipt_hash"] = rec.get("receipt_hash")
        if rec.get("fencing_token") is not None:
            unit["fencing_token"] = rec.get("fencing_token")
    elif kind == UNIT_HARVESTED:
        unit["status"] = "harvested"
        unit["receipt_hash"] = rec.get("receipt_hash")
    return state
