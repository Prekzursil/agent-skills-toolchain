"""Shared IMP-0225 scenarios: kill the monitor, rebuild from ledger only."""
from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
LEDGER_DIR = REPO / "tools" / "event-ledger"
sys.path.insert(0, str(LEDGER_DIR))

from monitor import LiveMonitor, remote_complete  # noqa: E402
from recover import naive_recover, rebuild, recover  # noqa: E402
from state import diff_canonical  # noqa: E402

RUN_ID = "imp-0225-run"
UNITS_P1 = ["U1", "U2", "U3", "U4"]
UNITS_P2 = ["A", "B", "C", "D"]


def receipt_hash(unit_id: str, payload: str) -> str:
    return hashlib.sha256(f"{unit_id}:{payload}".encode("utf-8")).hexdigest()


def temp_ledger(prefix: str) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    return tmp / "run.jsonl"


def scenario_kill_mid_run() -> dict:
    """Probe 1: two in-flight, one harvested, one pending. Snapshot then kill."""
    ledger = temp_ledger("imp0225-p1-")
    mon = LiveMonitor(ledger, RUN_ID, UNITS_P1)
    mon.start_run()
    mon.dispatch("U1")
    mon.dispatch("U2")
    mon.harvest("U1", receipt_hash("U1", "done-before-kill"))
    mon.dispatch("U3")
    snap = mon.snapshot()
    tokens = {
        uid: snap["units"][uid]["fencing_token"]
        for uid in snap["units"]
        if snap["units"][uid]["fencing_token"] is not None
    }
    mon.kill()
    rebuilt = rebuild(ledger).canonical()
    diffs = diff_canonical(snap, rebuilt)
    empty = rebuild(ledger.parent / "missing.jsonl").canonical()
    empty_diffs = diff_canonical(snap, empty)
    truncated = ledger.parent / "truncated.jsonl"
    truncated.write_bytes(ledger.read_bytes() + b'{"kind":"unit_harvested","seq":')
    truncated_state = rebuild(truncated).canonical()
    trunc_diffs = diff_canonical(snap, truncated_state)
    return {
        "ledger": str(ledger),
        "snapshot": snap,
        "rebuilt": rebuilt,
        "diffs": diffs,
        "equal": diffs == [],
        "negative_empty_diverges": bool(empty_diffs),
        "negative_truncated_still_equal": trunc_diffs == [],
        "tokens": tokens,
        "fields_compared": sorted(snap.keys()),
    }


def scenario_outage_harvest() -> dict:
    """Probe 2: remote work finishes while monitor is dead; recover harvests it."""
    ledger = temp_ledger("imp0225-p2-")
    mon = LiveMonitor(ledger, RUN_ID, UNITS_P2)
    mon.start_run()
    da = mon.dispatch("A")
    db = mon.dispatch("B")
    mon.dispatch("C")
    mon.dispatch("D")
    mon.harvest("C", receipt_hash("C", "before-outage"))
    kill_snap = mon.snapshot()
    dispatch_at_kill = kill_snap["dispatch_count"]
    mon.record_monitor_died()
    remote_complete(
        ledger, RUN_ID, "A", receipt_hash("A", "during-outage"), da["fencing_token"]
    )
    remote_complete(
        ledger, RUN_ID, "B", receipt_hash("B", "during-outage"), db["fencing_token"]
    )
    pre_recover = ledger.parent / "pre-recover.jsonl"
    shutil.copyfile(ledger, pre_recover)
    naive = naive_recover(pre_recover).canonical()
    report = recover(ledger)
    recovered = report.state.canonical()
    again = recover(ledger)
    return {
        "ledger": str(ledger),
        "dispatch_at_kill": dispatch_at_kill,
        "dispatch_after_recover": report.dispatch_count,
        "dispatch_unchanged": report.dispatch_count == dispatch_at_kill,
        "duplicate_dispatches": report.duplicate_dispatches,
        "harvested_during_recovery": report.harvested_during_recovery,
        "completed_ids": recovered["completed_ids"],
        "in_flight_ids": recovered["in_flight_ids"],
        "a_harvested": recovered["units"]["A"]["status"] == "harvested",
        "b_harvested": recovered["units"]["B"]["status"] == "harvested",
        "c_harvested": recovered["units"]["C"]["status"] == "harvested",
        "d_still_in_flight": recovered["units"]["D"]["status"] == "dispatched"
        and "D" in recovered["in_flight_ids"],
        "failure_class": report.failure_classes,
        "idempotent_second_recover": again.harvested_during_recovery == [],
        "idempotent_dispatch": again.dispatch_count == dispatch_at_kill,
        "naive_dispatch_count": naive["dispatch_count"],
        "naive_raised_dispatch": naive["dispatch_count"] > dispatch_at_kill,
        "kill_snap": kill_snap,
        "recovered": recovered,
    }
