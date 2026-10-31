"""Codex MCP cancel recovery: reclaim by thread id or record ABANDONED (TST-0135)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RUNNING = "running"
RECLAIMED = "RECLAIMED"
ABANDONED = "ABANDONED"
UNKNOWN = "UNKNOWN"


@dataclass
class ThreadRecord:
    thread_id: str
    state: str = RUNNING
    owner: str | None = "owner"
    named_outcome: str | None = None
    abandoned_record: bool = False
    success: bool = False


@dataclass
class Ledger:
    path: str
    present: bool = True
    rows: dict[str, ThreadRecord] = field(default_factory=dict)


class RecoveryRuntime:
    def __init__(self) -> None:
        self.threads: dict[str, ThreadRecord] = {}
        self.ledger = Ledger(path="codex-mcp-ledger.json")

    def start(self, thread_id: str) -> ThreadRecord:
        rec = ThreadRecord(thread_id=thread_id, state=RUNNING, owner="owner")
        self.threads[thread_id] = rec
        return rec

    def cancel_and_reclaim(self, thread_id: str) -> ThreadRecord:
        rec = self.threads.setdefault(thread_id, ThreadRecord(thread_id=thread_id))
        rec.state = "idle"
        rec.owner = "owner"
        rec.named_outcome = RECLAIMED
        rec.abandoned_record = False
        rec.success = True
        return rec

    def cancel_and_abandon(self, thread_id: str) -> ThreadRecord:
        rec = self.threads.setdefault(thread_id, ThreadRecord(thread_id=thread_id))
        rec.state = "abandoned"
        rec.owner = None
        rec.named_outcome = ABANDONED
        rec.abandoned_record = True
        rec.success = False
        self.ledger.rows[thread_id] = rec
        return rec

    def uncancelled_complete(self, thread_id: str) -> ThreadRecord:
        rec = self.threads.setdefault(thread_id, ThreadRecord(thread_id=thread_id))
        rec.state = "idle"
        rec.owner = "owner"
        rec.named_outcome = "COMPLETED"
        rec.abandoned_record = False
        rec.success = True
        return rec

    def orphans(self) -> list[ThreadRecord]:
        return [
            t
            for t in self.threads.values()
            if t.state == RUNNING and not t.owner
        ]


def classify_missing_ledger(*, ledger_present: bool, mutant_success: bool) -> dict[str, Any]:
    if ledger_present:
        return {
            "named_outcome": "COMPLETED",
            "state": "SUCCESS",
            "success": True,
            "present": True,
        }
    if mutant_success:
        return {
            "named_outcome": "SUCCESS",
            "state": "SUCCESS",
            "success": True,
        }
    return {
        "named_outcome": UNKNOWN,
        "state": UNKNOWN,
        "success": False,
    }


__all__ = [
    "ABANDONED",
    "Ledger",
    "RECLAIMED",
    "RUNNING",
    "RecoveryRuntime",
    "ThreadRecord",
    "UNKNOWN",
    "classify_missing_ledger",
]
