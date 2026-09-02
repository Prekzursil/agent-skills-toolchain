"""Two-session dispatch: contested (one id) and control (two ids)."""
from __future__ import annotations

import json
import multiprocessing
import os
import tempfile
import time
from pathlib import Path
from typing import Any

from work_claim import (
    ALREADY_CLAIMED,
    GRANTED,
    acquire,
    atomic_write,
    declare_lease,
    note_write,
    register_session,
    utc_now,
)

HERE = Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
CONTENDED = "CNF-0031-CONTENDED"
CTRL_A = "CNF-0031-CTRL-A"
CTRL_B = "CNF-0031-CTRL-B"


def _worker(
    claims_dir: str,
    exec_dir: str,
    leases_dir: str,
    events_path: str,
    result_path: str,
    unit_id: str,
    session: dict[str, Any],
    exclusive: bool,
    barrier: Any,
) -> None:
    try:
        barrier.wait(timeout=15)
        claim = acquire(
            Path(claims_dir), unit_id, session, ttl_s=300.0, exclusive=exclusive
        )
        claim["ts"] = utc_now()
        executed = False
        receipt_name = None
        if claim.get("status") == GRANTED:
            rel = f"{unit_id}.{session['id']}.receipt.json"
            note_write(Path(leases_dir), Path(events_path), session["id"], rel)
            receipt = {
                "executed_at": utc_now(),
                "pid": os.getpid(),
                "session_id": session["id"],
                "unit_id": unit_id,
            }
            rec_path = Path(exec_dir) / f"{unit_id}.{session['id']}.{time.time_ns()}.receipt.json"
            atomic_write(rec_path, receipt)
            receipt_name = rec_path.name
            executed = True
        out = {
            "claim": claim,
            "executed": executed,
            "receipt": receipt_name,
            "session_id": session["id"],
            "unit_id": unit_id,
        }
        Path(result_path).write_text(
            json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    except Exception as exc:  # pragma: no cover - surfaces in result file
        Path(result_path).write_text(
            json.dumps({"error": f"{type(exc).__name__}: {exc}"}, sort_keys=True) + "\n",
            encoding="utf-8",
        )


def _collect(
    tmp: Path,
    assignments: list[tuple[dict[str, Any], str]],
    exclusive: bool,
) -> dict[str, Any]:
    claims = tmp / "claims"
    exec_dir = tmp / "exec"
    leases = tmp / "leases"
    sessions = tmp / "sessions"
    results = tmp / "results"
    for d in (claims, exec_dir, leases, sessions, results):
        d.mkdir(parents=True, exist_ok=True)
    events_path = tmp / "lease-events.jsonl"
    ctx = multiprocessing.get_context("fork")
    barrier = ctx.Barrier(len(assignments))
    procs: list[Any] = []
    result_paths: list[Path] = []
    registered: list[dict[str, Any]] = []
    for session, unit_id in assignments:
        registered.append(register_session(sessions, session["id"]))
        declare_lease(leases, session["id"], [f"{unit_id}.{session['id']}.receipt.json"])
        rp = results / f"{session['id']}.json"
        result_paths.append(rp)
        p = ctx.Process(
            target=_worker,
            args=(
                str(claims),
                str(exec_dir),
                str(leases),
                str(events_path),
                str(rp),
                unit_id,
                session,
                exclusive,
                barrier,
            ),
        )
        procs.append(p)
        p.start()
    for p in procs:
        p.join(timeout=20)
        if p.is_alive():
            p.terminate()
            p.join(timeout=5)
    rows: list[dict[str, Any]] = []
    for rp in result_paths:
        if not rp.is_file():
            rows.append({"error": f"missing result {rp.name}"})
            continue
        rows.append(json.loads(rp.read_text(encoding="utf-8")))
    receipts = sorted(p.name for p in exec_dir.glob("*.receipt.json"))
    by_unit: dict[str, int] = {}
    for name in receipts:
        uid = name.split(".", 1)[0]
        by_unit[uid] = by_unit.get(uid, 0) + 1
    return {
        "by_unit_receipts": by_unit,
        "receipt_count": len(receipts),
        "receipts": receipts,
        "registered_sessions": registered,
        "rows": rows,
    }


def run_contested(exclusive: bool = True) -> dict[str, Any]:
    s1 = {"id": "session-alpha"}
    s2 = {"id": "session-beta"}
    with tempfile.TemporaryDirectory(prefix="cnf0031-contested-") as raw:
        tmp = Path(raw)
        collected = _collect(tmp, [(s1, CONTENDED), (s2, CONTENDED)], exclusive=exclusive)
    rows = collected["rows"]
    executed = [r for r in rows if r.get("executed") is True]
    denied = [r for r in rows if r.get("claim", {}).get("status") == ALREADY_CLAIMED]
    errors = [r for r in rows if r.get("error")]
    winner = executed[0]["session_id"] if executed else None
    loser_row = denied[0] if denied else None
    loser_claim = (loser_row or {}).get("claim") or {}
    claim_log = []
    for r in rows:
        c = r.get("claim") or {}
        claim_log.append(
            {
                "result": c.get("result") or r.get("error") or "UNKNOWN",
                "session_id": r.get("session_id"),
                "ts": c.get("ts") or c.get("acquired_at_iso") or utc_now(),
                "unit_id": r.get("unit_id") or CONTENDED,
                "status": c.get("status"),
                "loser_response": c.get("loser_response"),
            }
        )
    receipt_for_unit = int(collected["by_unit_receipts"].get(CONTENDED, 0))
    executed_signal = len(executed)
    return {
        "claim_log": claim_log,
        "errors": errors,
        "exclusive": exclusive,
        "executed_from_returns": executed_signal,
        "execution_count": receipt_for_unit,
        "loser_response": loser_claim.get("loser_response"),
        "loser_session_id": loser_row.get("session_id") if loser_row else None,
        "loser_status": loser_claim.get("status"),
        "receipts": collected["receipts"],
        "registered_sessions": collected["registered_sessions"],
        "returns_agree_with_receipts": executed_signal == receipt_for_unit,
        "rows": rows,
        "signals_agree": executed_signal == receipt_for_unit,
        "unit_id": CONTENDED,
        "winner_session_id": winner,
    }


def run_control() -> dict[str, Any]:
    s1 = {"id": "session-alpha"}
    s2 = {"id": "session-beta"}
    with tempfile.TemporaryDirectory(prefix="cnf0031-control-") as raw:
        tmp = Path(raw)
        collected = _collect(tmp, [(s1, CTRL_A), (s2, CTRL_B)], exclusive=True)
    rows = collected["rows"]
    executed = [r for r in rows if r.get("executed") is True]
    denied = [r for r in rows if r.get("claim", {}).get("status") == ALREADY_CLAIMED]
    claim_log = []
    for r in rows:
        c = r.get("claim") or {}
        claim_log.append(
            {
                "result": c.get("result") or r.get("error") or "UNKNOWN",
                "session_id": r.get("session_id"),
                "ts": c.get("ts") or c.get("acquired_at_iso") or utc_now(),
                "unit_id": r.get("unit_id"),
                "status": c.get("status"),
            }
        )
    return {
        "claim_log": claim_log,
        "denied_count": len(denied),
        "executed_from_returns": len(executed),
        "execution_count": collected["receipt_count"],
        "receipts": collected["receipts"],
        "registered_sessions": collected["registered_sessions"],
        "rows": rows,
        "signals_agree": len(executed) == collected["receipt_count"],
        "unit_ids": [CTRL_A, CTRL_B],
    }


def fixture_catalogs() -> dict[str, Path]:
    return {
        "a": FIXTURES / "catalog-a.json",
        "b": FIXTURES / "catalog-b.json",
        "disjoint": FIXTURES / "catalog-disjoint.json",
    }
