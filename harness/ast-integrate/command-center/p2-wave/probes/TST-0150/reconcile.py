"""Reconcile durable ledger state against the remote runtime job list.

UNKNOWN is reserved for units the remote side considers finished whose
terminal state is missing from the ledger after restart. In-flight remote
work is not UNKNOWN-finished.
"""
from __future__ import annotations

from typing import Any

from remote_jobs import TERMINAL as REMOTE_TERMINAL

LEDGER_TERMINAL = frozenset({"harvested", "remote_completed", "failed"})


def finished_remote_jobs(jobs_doc: dict[str, Any]) -> list[dict[str, Any]]:
    jobs = jobs_doc.get("jobs") or {}
    out: list[dict[str, Any]] = []
    for uid in sorted(jobs):
        row = jobs[uid]
        if not isinstance(row, dict):
            continue
        if row.get("status") in REMOTE_TERMINAL:
            out.append(dict(row))
    return out


def reconcile(ledger_state: dict[str, Any], jobs_doc: dict[str, Any]) -> dict[str, Any]:
    """Compare post-restart ledger fold vs remote jobs loaded from disk."""
    units = ledger_state.get("units") or {}
    recovered: list[str] = []
    unknown: list[dict[str, Any]] = []
    for job in finished_remote_jobs(jobs_doc):
        uid = str(job["unit_id"])
        unit = units.get(uid)
        ledger_status = unit.get("status") if isinstance(unit, dict) else "ABSENT"
        if ledger_status in LEDGER_TERMINAL:
            recovered.append(uid)
            continue
        unknown.append(
            {
                "unit_id": uid,
                "remote_status": job.get("status"),
                "ledger_status": ledger_status,
                "reason": "remote-finished-not-in-durable-ledger",
            }
        )
    unknown_ids = [u["unit_id"] for u in unknown]
    return {
        "unknown_finished": unknown,
        "unknown_finished_ids": unknown_ids,
        "unknown_count": len(unknown),
        "recovered_finished_ids": recovered,
        "remote_finished_ids": [str(j["unit_id"]) for j in finished_remote_jobs(jobs_doc)],
        "pass": len(unknown) == 0,
    }
