#!/usr/bin/env python3
"""Independent reviewer recount for CNL-0074.

Does not import classify_statement or brier_score from score.py.
Uses set membership for status and the expanded Brier identity
    p*p + y*y - 2*p*y
instead of (p-y)**2.
"""
from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

OK_SOURCE = {"EXTERNAL_OBSERVABLE", "OWNER_ATTESTED_OUTCOME", "AUDIT_REPLAY"}
NEED = {"observable_id", "observable_procedure", "due_at", "recorder_role"}
CLIP = 1e-15


def _read(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _resolutions(doc: dict | None) -> dict[str, dict]:
    table: dict[str, dict] = {}
    if not isinstance(doc, dict):
        return table
    for rec in doc.get("resolutions") or []:
        if isinstance(rec, dict) and isinstance(rec.get("proposition_id"), str):
            table[rec["proposition_id"]] = rec
    return table


def _expanded_brier(p: float, y: int) -> float:
    yy = float(y)
    return p * p + yy * yy - 2.0 * p * yy


def _log_score(p: float, y: int) -> float:
    q = min(1.0 - CLIP, max(CLIP, p))
    return math.log(q) if y == 1 else math.log(1.0 - q)


def _status(stmt: dict, res: dict | None, seats: set[str]) -> str:
    p = stmt.get("stated_confidence")
    if isinstance(p, bool) or not isinstance(p, (int, float)) or not (0.0 <= float(p) <= 1.0):
        return "UNSCOREABLE"
    bind = stmt.get("resolution_binding") if isinstance(stmt.get("resolution_binding"), dict) else {}
    src = str(bind.get("source_class") or "")
    if src not in OK_SOURCE:
        return "UNSCOREABLE"
    if NEED - {k for k in NEED if bind.get(k)}:
        return "UNSCOREABLE"
    if res is None:
        return "PENDING"
    if str(res.get("source_class") or "") != src:
        return "REJECTED_RESOLUTION"
    rec = str(res.get("recorder_id") or "")
    if rec and rec in seats:
        return "REJECTED_RESOLUTION"
    if res.get("proposition_id") != stmt.get("proposition_id"):
        return "REJECTED_RESOLUTION"
    if res.get("outcome") not in (0, 1):
        return "REJECTED_RESOLUTION"
    return "RESOLVED"


def recount(trajectory: dict, resolution_doc: dict | None = None) -> dict:
    seats = {str(x) for x in (trajectory.get("participants") or [])}
    res_map = _resolutions(resolution_doc)
    statements = [s for s in (trajectory.get("statements") or []) if isinstance(s, dict)]
    rows = []
    briers: list[float] = []
    logs: list[float] = []
    for stmt in statements:
        pid = stmt.get("proposition_id")
        res = res_map.get(pid) if isinstance(pid, str) else None
        status = _status(stmt, res, seats)
        p_raw = stmt.get("stated_confidence")
        p = float(p_raw) if isinstance(p_raw, (int, float)) and not isinstance(p_raw, bool) else None
        y = int(res["outcome"]) if status == "RESOLVED" else None
        brier = _expanded_brier(p, y) if status == "RESOLVED" and p is not None and y is not None else None
        lsc = _log_score(p, y) if status == "RESOLVED" and p is not None and y is not None else None
        if brier is not None:
            briers.append(brier)
        if lsc is not None:
            logs.append(lsc)
        rows.append(
            {
                "participant_id": stmt.get("participant_id"),
                "proposition_id": pid,
                "status": status,
                "stated_confidence": p,
                "outcome": y,
                "brier": brier,
            }
        )
    bag = Counter(r["status"] for r in rows)
    n_res = bag["RESOLVED"]
    return {
        "n_statements": len(rows),
        "n_resolved": n_res,
        "n_pending": bag["PENDING"],
        "n_unscoreable": bag["UNSCOREABLE"],
        "n_rejected_resolution": bag["REJECTED_RESOLUTION"],
        "mean_brier": (sum(briers) / n_res) if n_res else None,
        "mean_log_score": (sum(logs) / n_res) if n_res else None,
        "not_yet_meaningful": n_res < 10,
        "rows": rows,
        "method": "set-membership status + expanded Brier p*p+y*y-2py",
    }


def recount_paths(traj_path: Path, res_path: Path | None) -> dict:
    traj = _read(traj_path)
    res = _read(res_path) if res_path and res_path.is_file() else None
    return recount(traj, res)
