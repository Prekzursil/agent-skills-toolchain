"""Live monitor with a durable append-only JSONL ledger (TST-0150).

Every state transition the monitor makes is a durable ledger record BEFORE
it is applied to RAM. ``remote_complete`` appends to the same ledger without
a live monitor — that is how remote work survives a monitor death.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from records import (
    MONITOR_DIED,
    REMOTE_COMPLETED,
    RUN_STARTED,
    UNIT_DISPATCHED,
    UNIT_HARVESTED,
)
from state import LedgerState, apply_record


class MonitorDead(RuntimeError):
    """The monitor process is gone; RAM state is unreachable."""


def _append_line(ledger: Path, rec: dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=True) + "\n")


def read_records(ledger: Path) -> list[dict[str, Any]]:
    if not Path(ledger).is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in Path(ledger).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _next_seq(ledger: Path) -> int:
    records = read_records(ledger)
    return (max((int(r.get("seq") or 0) for r in records), default=0)) + 1


class LiveMonitor:
    """Monitor whose durable writes precede every RAM application."""

    def __init__(self, ledger: Path, run_id: str, unit_ids: list[str]) -> None:
        self.ledger = Path(ledger)
        self.run_id = run_id
        self.unit_ids = list(unit_ids)
        self.state = LedgerState()
        self._dead = False

    def _emit(self, rec: dict[str, Any]) -> dict[str, Any]:
        _append_line(self.ledger, rec)
        apply_record(self.state, rec)
        return rec

    def start_run(self) -> dict[str, Any]:
        return self._emit(
            {
                "kind": RUN_STARTED,
                "seq": self.state.last_seq + 1,
                "run_id": self.run_id,
                "unit_ids": self.unit_ids,
            }
        )

    def dispatch(self, unit_id: str) -> dict[str, Any]:
        seq = self.state.last_seq + 1
        return self._emit(
            {
                "kind": UNIT_DISPATCHED,
                "seq": seq,
                "run_id": self.run_id,
                "unit_id": unit_id,
                "fencing_token": seq,
            }
        )

    def harvest(self, unit_id: str, receipt_hash: str) -> dict[str, Any]:
        return self._emit(
            {
                "kind": UNIT_HARVESTED,
                "seq": self.state.last_seq + 1,
                "run_id": self.run_id,
                "unit_id": unit_id,
                "receipt_hash": receipt_hash,
            }
        )

    def snapshot(self) -> dict[str, Any]:
        if self._dead:
            raise MonitorDead("monitor process is dead; RAM snapshot unavailable")
        return self.state.canonical()

    def record_monitor_died(self) -> dict[str, Any]:
        rec = self._emit(
            {
                "kind": MONITOR_DIED,
                "seq": self.state.last_seq + 1,
                "run_id": self.run_id,
            }
        )
        self._dead = True
        return rec


def remote_complete(
    ledger: Path, run_id: str, unit_id: str, receipt_hash: str, fencing_token: int
) -> dict[str, Any]:
    """Remote worker appends its completion durably — no live monitor needed."""
    ledger = Path(ledger)
    rec = {
        "kind": REMOTE_COMPLETED,
        "seq": _next_seq(ledger),
        "run_id": run_id,
        "unit_id": unit_id,
        "receipt_hash": receipt_hash,
        "fencing_token": fencing_token,
    }
    _append_line(ledger, rec)
    return rec


__all__ = ["LiveMonitor", "MonitorDead", "read_records", "remote_complete"]
