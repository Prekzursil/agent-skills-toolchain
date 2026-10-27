"""Per-agent deadline fan-out with a null-tolerant barrier (WFA-0088)."""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Any

DEADLINE_S = 0.18
BROKEN_WAIT_S = 0.45
REPAIRED_MAX_S = 0.40
N_UNITS = 6
HANG_ID = "U-HANG"
MODE_BROKEN_WAIT_ALL = "broken-wait-all"
MODE_REPAIRED = "repaired"
MODE_MEMORY_ONLY = "memory-only"
MODE_PHASE_DEADLINE = "phase-deadline"
STATUS_OK = "OK"
STATUS_RUNNING = "RUNNING"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_LOST = "LOST"


def atomic_write_json(path: Path, doc: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _unit_ids() -> list[str]:
    ids = [f"U-{i:02d}" for i in range(N_UNITS - 1)]
    ids.append(HANG_ID)
    return ids


def _payload(unit_id: str) -> dict[str, Any]:
    return {"unit_id": unit_id, "ok": True}


def _pipeline_one(
    unit_id: str,
    dest: Path | None,
    stop: threading.Event,
    self_timeout: bool,
    durable: bool,
    out: dict[str, Any],
) -> None:
    t0 = time.monotonic()
    if unit_id == HANG_ID:
        if self_timeout:
            stop.wait(timeout=DEADLINE_S)
            rec = {
                "unit_id": unit_id,
                "status": STATUS_TIMEOUT,
                "payload": None,
                "null": True,
                "reason_id": "per-agent-deadline",
                "elapsed_s": time.monotonic() - t0,
                "durable": bool(durable),
            }
        else:
            stop.wait()
            rec = {
                "unit_id": unit_id,
                "status": STATUS_RUNNING,
                "payload": None,
                "null": True,
                "elapsed_s": time.monotonic() - t0,
                "durable": False,
            }
    else:
        rec = {
            "unit_id": unit_id,
            "status": STATUS_OK,
            "payload": _payload(unit_id),
            "null": False,
            "elapsed_s": time.monotonic() - t0,
            "durable": bool(durable),
        }
    out[unit_id] = rec
    if durable and dest is not None and rec.get("status") in {STATUS_OK, STATUS_TIMEOUT}:
        try:
            atomic_write_json(dest / "units" / f"{unit_id}.json", rec)
        except OSError:
            pass


def load_unit_records(root: Path) -> list[dict[str, Any]]:
    units = Path(root) / "units"
    if not units.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for path in sorted(units.glob("*.json")):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(rec, dict):
            rows.append(rec)
    return rows


def run_cohort(
    mode: str,
    dest: Path,
    *,
    wait_limit_s: float | None = None,
    kill_after_n_ok: int | None = None,
) -> dict[str, Any]:
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    ids = _unit_ids()
    stop = threading.Event()
    out: dict[str, Any] = {}
    t0 = time.monotonic()

    if mode == MODE_BROKEN_WAIT_ALL:
        threads = [
            threading.Thread(
                target=_pipeline_one,
                args=(uid, dest, stop, False, False, out),
                daemon=True,
            )
            for uid in ids
        ]
        for th in threads:
            th.start()
        limit = float(wait_limit_s if wait_limit_s is not None else BROKEN_WAIT_S)
        time.sleep(limit)
        elapsed = time.monotonic() - t0
        records = []
        for uid in ids:
            rec = out.get(uid) or {
                "unit_id": uid,
                "status": STATUS_RUNNING,
                "payload": None,
                "elapsed_s": elapsed,
            }
            records.append(rec)
        return {
            "mode": mode,
            "n_units": N_UNITS,
            "barrier_resolved": False,
            "elapsed_s": elapsed,
            "records": records,
            "ok_ids": [],
            "timeout_ids": [],
            "null_ids": [HANG_ID],
            "null_tolerant": False,
            "per_agent_deadline": False,
            "write_as_you_go": False,
        }

    if mode == MODE_PHASE_DEADLINE:
        threads = [
            threading.Thread(
                target=_pipeline_one,
                args=(uid, dest, stop, False, False, out),
                daemon=True,
            )
            for uid in ids
        ]
        for th in threads:
            th.start()
        time.sleep(DEADLINE_S)
        elapsed = time.monotonic() - t0
        ram_ok = [uid for uid in ids if uid != HANG_ID and uid in out]
        records = []
        for uid in ids:
            rec = dict(out.get(uid) or {"unit_id": uid, "status": STATUS_RUNNING})
            rec["status"] = STATUS_LOST
            rec["payload"] = None
            records.append(rec)
        return {
            "mode": mode,
            "n_units": N_UNITS,
            "barrier_resolved": False,
            "elapsed_s": elapsed,
            "records": records,
            "ram_completed_count": len(ram_ok),
            "phase_still_running": 1,
            "ok_ids": [],
            "timeout_ids": [],
            "null_ids": [],
        }

    durable = mode == MODE_REPAIRED
    memory_only = mode == MODE_MEMORY_ONLY
    self_timeout = True
    threads = []
    write = durable and not memory_only
    ordered = [uid for uid in ids if uid != HANG_ID] + ([HANG_ID] if kill_after_n_ok is None else [])
    if kill_after_n_ok is not None:
        ordered = [uid for uid in ids if uid != HANG_ID]
    for uid in ordered:
        th = threading.Thread(
            target=_pipeline_one,
            args=(uid, dest, stop, self_timeout if uid == HANG_ID else False, write, out),
            daemon=True,
        )
        threads.append((uid, th))
        th.start()
        if kill_after_n_ok is not None:
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline:
                ok_disk = [
                    r
                    for r in load_unit_records(dest)
                    if r.get("status") == STATUS_OK
                ]
                ok_n = max(
                    ok_disk and len(ok_disk) or 0,
                    sum(1 for rec in out.values() if rec.get("status") == STATUS_OK),
                )
                if ok_n >= kill_after_n_ok:
                    stop.set()
                    for _uid, th in threads:
                        th.join(timeout=0.2)
                    elapsed = time.monotonic() - t0
                    records = list(out.values())
                    return {
                        "mode": mode,
                        "n_units": N_UNITS,
                        "interrupted": True,
                        "barrier_resolved": False,
                        "elapsed_s": elapsed,
                        "records": records,
                        "ok_ids": [r["unit_id"] for r in records if r.get("status") == STATUS_OK],
                        "timeout_ids": [
                            r["unit_id"] for r in records if r.get("status") == STATUS_TIMEOUT
                        ],
                        "null_ids": [r["unit_id"] for r in records if r.get("null")],
                        "null_tolerant": True,
                        "per_agent_deadline": True,
                        "write_as_you_go": write,
                    }
                time.sleep(0.01)

    for _uid, th in threads:
        th.join(timeout=DEADLINE_S + 0.3)
    elapsed = time.monotonic() - t0
    records = [out[uid] for uid in ids if uid in out]
    for uid in ids:
        if uid not in out:
            records.append(
                {
                    "unit_id": uid,
                    "status": STATUS_TIMEOUT if uid == HANG_ID else STATUS_RUNNING,
                    "payload": None,
                    "null": uid == HANG_ID,
                    "reason_id": "per-agent-deadline" if uid == HANG_ID else None,
                    "elapsed_s": elapsed,
                }
            )
    ok_ids = [r["unit_id"] for r in records if r.get("status") == STATUS_OK]
    timeout_ids = [r["unit_id"] for r in records if r.get("status") == STATUS_TIMEOUT]
    null_ids = [r["unit_id"] for r in records if r.get("null")]
    if durable and not memory_only:
        atomic_write_json(
            dest / "barrier.json",
            {
                "partial": True,
                "ok_ids": ok_ids,
                "timeout_ids": timeout_ids,
            },
        )
        atomic_write_json(
            dest / "partial.json",
            {"partial": True, "ok_ids": ok_ids, "timeout_ids": timeout_ids},
        )
    return {
        "mode": mode,
        "n_units": N_UNITS,
        "interrupted": False,
        "barrier_resolved": True,
        "elapsed_s": elapsed,
        "records": records,
        "ok_ids": ok_ids,
        "timeout_ids": timeout_ids,
        "null_ids": null_ids,
        "null_tolerant": True,
        "per_agent_deadline": True,
        "write_as_you_go": durable and not memory_only,
    }
