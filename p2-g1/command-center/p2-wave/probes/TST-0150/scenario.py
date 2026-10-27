"""TST-0150 scenarios: kill the monitor, keep remote work, restart from ledger.

The remote job list is a second file. Reconciliation after restart reads
the ledger and the job list from disk in a fresh fold — not from RAM.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LEDGER_DIR = REPO / "tools" / "event-ledger"

sys.path[:] = [p for p in sys.path if p not in ("", ".", str(REPO))]
if str(LEDGER_DIR) not in sys.path:
    sys.path.insert(0, str(LEDGER_DIR))
# Probe-local modules (monitor, records, state, recover) must win the path
# race over the event-ledger's IMP-0225 modules of the same names.
if str(HERE) in sys.path:
    sys.path.remove(str(HERE))
sys.path.insert(0, str(HERE))

from monitor import LiveMonitor, MonitorDead, remote_complete  # noqa: E402
from records import REMOTE_COMPLETED, UNIT_HARVESTED  # noqa: E402
from recover import recover  # noqa: E402
from remote_jobs import RemoteRuntime, load_jobs  # noqa: E402
from state import apply_record  # noqa: E402

from reconcile import reconcile  # noqa: E402

RUN_ID = "tst-0150-run"
UNITS = ["A", "B", "C", "D"]


def receipt_hash(unit_id: str, payload: str) -> str:
    return hashlib.sha256(f"{unit_id}:{payload}".encode("utf-8")).hexdigest()


def file_sig(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    return {
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "name": path.name,
    }


def _tmp_pair(prefix: str) -> tuple[Path, Path, Path]:
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    return tmp, tmp / "run.jsonl", tmp / "remote-jobs.json"


def _cleanup(tmp: Path) -> None:
    shutil.rmtree(tmp, ignore_errors=True)


def canonical(result: dict[str, Any]) -> dict[str, Any]:
    """Path-free view so a second shell can compare fingerprints."""
    rec = result.get("reconcile") or {}
    ram = result.get("ram_trust_reconcile") or {}
    return {
        "kind": result.get("kind"),
        "unknown_count": rec.get("unknown_count"),
        "unknown_finished_ids": rec.get("unknown_finished_ids"),
        "recovered_finished_ids": rec.get("recovered_finished_ids"),
        "remote_finished_ids": rec.get("remote_finished_ids"),
        "pass": rec.get("pass"),
        "signals_independent": result.get("signals_independent"),
        "ram_trust_unknown_count": ram.get("unknown_count"),
        "ram_trust_would_pass": ram.get("pass"),
        "monitor_dead_after_kill": result.get("monitor_dead_after_kill"),
        "ledger_terminal": result.get("ledger_terminal"),
        "in_flight_ids": result.get("in_flight_ids"),
    }


class MemoryOnlyMonitor:
    """Durable dispatch; terminal state exists only in the live process."""

    def __init__(self, ledger: Path, run_id: str, unit_ids: list[str]) -> None:
        self.live = LiveMonitor(ledger, run_id, unit_ids)

    def start_run(self) -> dict[str, Any]:
        return self.live.start_run()

    def dispatch(self, unit_id: str) -> dict[str, Any]:
        return self.live.dispatch(unit_id)

    def durable_harvest(self, unit_id: str, rh: str) -> dict[str, Any]:
        return self.live.harvest(unit_id, rh)

    def ram_remote_complete(self, unit_id: str, rh: str, token: int) -> dict[str, Any]:
        rec = {
            "kind": REMOTE_COMPLETED,
            "seq": self.live.state.last_seq + 1,
            "run_id": self.live.run_id,
            "unit_id": unit_id,
            "receipt_hash": rh,
            "fencing_token": token,
        }
        apply_record(self.live.state, rec)
        return rec

    def ram_harvest(self, unit_id: str, rh: str) -> dict[str, Any]:
        rec = {
            "kind": UNIT_HARVESTED,
            "seq": self.live.state.last_seq + 1,
            "run_id": self.live.run_id,
            "unit_id": unit_id,
            "receipt_hash": rh,
        }
        apply_record(self.live.state, rec)
        return rec

    def snapshot(self) -> dict[str, Any]:
        return self.live.snapshot()

    def record_monitor_died(self) -> dict[str, Any]:
        return self.live.record_monitor_died()


def _independence(ledger: Path, jobs: Path) -> dict[str, Any]:
    a, b = file_sig(ledger), file_sig(jobs)
    ledger_text = ledger.read_text(encoding="utf-8") if ledger.is_file() else ""
    jobs_doc = load_jobs(jobs)
    return {
        "ledger_path_name": ledger.name,
        "jobs_path_name": jobs.name,
        "same_inode_path": str(ledger.resolve()) == str(jobs.resolve()),
        "sha_equal": a["sha256"] == b["sha256"],
        "ledger_is_jsonl_kind": '"kind"' in ledger_text,
        "jobs_is_object": isinstance(jobs_doc.get("jobs"), dict),
        "independent": (
            str(ledger.resolve()) != str(jobs.resolve())
            and a["sha256"] != b["sha256"]
            and '"kind"' in ledger_text
            and isinstance(jobs_doc.get("jobs"), dict)
        ),
        "ledger": a,
        "jobs": b,
    }


def _post_restart(
    ledger: Path,
    jobs: Path,
    *,
    ram_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report = recover(ledger)
    recovered = report.state.canonical()
    jobs_doc = load_jobs(jobs)
    disk = reconcile(recovered, jobs_doc)
    ram_trust = reconcile(ram_snapshot, jobs_doc) if ram_snapshot is not None else None
    units = recovered.get("units") or {}
    ledger_terminal = {
        uid: (units[uid] or {}).get("status")
        for uid in sorted(units)
        if (units[uid] or {}).get("status") in {"harvested", "remote_completed", "failed"}
    }
    return {
        "recover_dispatch_count": report.dispatch_count,
        "harvested_during_recovery": report.harvested_during_recovery,
        "recovered": recovered,
        "jobs_doc": jobs_doc,
        "reconcile": disk,
        "ram_trust_reconcile": ram_trust,
        "signals_independent": _independence(ledger, jobs),
        "ledger_terminal": ledger_terminal,
        "in_flight_ids": recovered.get("in_flight_ids"),
        "failure_classes": report.failure_classes,
    }


def scenario_kill_restart() -> dict[str, Any]:
    """Kill monitor while A,B finish remotely; restart from ledger + job list."""
    tmp, ledger, jobs = _tmp_pair("tst0150-kill-")
    try:
        remote = RemoteRuntime(jobs)
        mon = LiveMonitor(ledger, RUN_ID, UNITS)
        mon.start_run()
        tokens: dict[str, int] = {}
        for uid in UNITS:
            rec = mon.dispatch(uid)
            tokens[uid] = int(rec["fencing_token"])
            remote.mark_running(uid, tokens[uid])
        rh_c = receipt_hash("C", "before-kill")
        mon.harvest("C", rh_c)
        remote.finish("C", rh_c, fencing_token=tokens["C"])
        ram_snapshot = mon.snapshot()
        mon.record_monitor_died()
        dead = False
        try:
            mon.snapshot()
        except MonitorDead:
            dead = True
        rh_a = receipt_hash("A", "during-outage")
        rh_b = receipt_hash("B", "during-outage")
        remote_complete(ledger, RUN_ID, "A", rh_a, tokens["A"])
        remote.finish("A", rh_a, fencing_token=tokens["A"])
        remote_complete(ledger, RUN_ID, "B", rh_b, tokens["B"])
        remote.finish("B", rh_b, fencing_token=tokens["B"])
        post = _post_restart(ledger, jobs, ram_snapshot=ram_snapshot)
        post.update(
            {
                "kind": "kill-restart",
                "monitor_dead_after_kill": dead,
                "tokens": tokens,
            }
        )
        return post
    finally:
        _cleanup(tmp)


def scenario_uninterrupted() -> dict[str, Any]:
    """Both-states control: no kill; harvest live; still zero UNKNOWNs."""
    tmp, ledger, jobs = _tmp_pair("tst0150-live-")
    try:
        remote = RemoteRuntime(jobs)
        mon = LiveMonitor(ledger, RUN_ID, UNITS)
        mon.start_run()
        tokens: dict[str, int] = {}
        for uid in UNITS:
            rec = mon.dispatch(uid)
            tokens[uid] = int(rec["fencing_token"])
            remote.mark_running(uid, tokens[uid])
        for uid, payload in (("A", "live"), ("B", "live"), ("C", "live")):
            rh = receipt_hash(uid, payload)
            remote_complete(ledger, RUN_ID, uid, rh, tokens[uid])
            remote.finish(uid, rh, fencing_token=tokens[uid])
            mon.harvest(uid, rh)
        ram_snapshot = mon.snapshot()
        post = _post_restart(ledger, jobs, ram_snapshot=ram_snapshot)
        post.update(
            {
                "kind": "uninterrupted",
                "monitor_dead_after_kill": False,
                "monitor_alive": ram_snapshot.get("monitor_alive"),
            }
        )
        return post
    finally:
        _cleanup(tmp)


def scenario_memory_only() -> dict[str, Any]:
    """Negative control: A,B finish only in RAM; C is durable; D stays running."""
    tmp, ledger, jobs = _tmp_pair("tst0150-ram-")
    try:
        remote = RemoteRuntime(jobs)
        mon = MemoryOnlyMonitor(ledger, RUN_ID, UNITS)
        mon.start_run()
        tokens: dict[str, int] = {}
        for uid in UNITS:
            rec = mon.dispatch(uid)
            tokens[uid] = int(rec["fencing_token"])
            remote.mark_running(uid, tokens[uid])
        rh_c = receipt_hash("C", "durable")
        mon.durable_harvest("C", rh_c)
        remote.finish("C", rh_c, fencing_token=tokens["C"])
        rh_a = receipt_hash("A", "ram-only")
        rh_b = receipt_hash("B", "ram-only")
        mon.ram_remote_complete("A", rh_a, tokens["A"])
        mon.ram_harvest("A", rh_a)
        remote.finish("A", rh_a, fencing_token=tokens["A"])
        mon.ram_remote_complete("B", rh_b, tokens["B"])
        mon.ram_harvest("B", rh_b)
        remote.finish("B", rh_b, fencing_token=tokens["B"])
        ram_snapshot = mon.snapshot()
        mon.record_monitor_died()
        dead = False
        try:
            mon.snapshot()
        except MonitorDead:
            dead = True
        post = _post_restart(ledger, jobs, ram_snapshot=ram_snapshot)
        post.update(
            {
                "kind": "memory-only",
                "monitor_dead_after_kill": dead,
                "ram_terminal_before_kill": {
                    uid: ram_snapshot["units"][uid]["status"]
                    for uid in ("A", "B", "C")
                },
            }
        )
        return post
    finally:
        _cleanup(tmp)


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else ""
    if mode == "--canonical-kill":
        print(json.dumps(canonical(scenario_kill_restart()), sort_keys=True))
        return 0
    if mode == "--canonical-uninterrupted":
        print(json.dumps(canonical(scenario_uninterrupted()), sort_keys=True))
        return 0
    if mode == "--canonical-memory":
        print(json.dumps(canonical(scenario_memory_only()), sort_keys=True))
        return 0
    print("usage: scenario.py --canonical-kill|--canonical-uninterrupted|--canonical-memory")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
