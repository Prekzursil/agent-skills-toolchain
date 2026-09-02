#!/usr/bin/env python3
"""CNL-0074 author scorer: classify confidence statements and score resolved ones.

Scoring reads only the frozen trajectory plus an optional later resolution
document. It must not open a live session directory.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

ALLOWED_SOURCES = frozenset(
    {"EXTERNAL_OBSERVABLE", "OWNER_ATTESTED_OUTCOME", "AUDIT_REPLAY"}
)
FORBIDDEN_SETTLERS = frozenset(
    {
        "LATER_COUNCIL_AGREEMENT",
        "SELF_FINAL_VOTE",
        "ELAPSED_SILENCE",
        "SELF_REPORTED_CORRECT",
        "NONE",
    }
)
REQUIRED_BINDING = (
    "observable_id",
    "observable_procedure",
    "due_at",
    "recorder_role",
)
EPS = 1e-15
MEANINGFUL_N = 10


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _p(statement: dict) -> float | None:
    raw = statement.get("stated_confidence")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        return None
    val = float(raw)
    if val < 0.0 or val > 1.0:
        return None
    return val


def _binding(statement: dict) -> dict:
    raw = statement.get("resolution_binding")
    return raw if isinstance(raw, dict) else {}


def _index_resolutions(doc: dict | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not isinstance(doc, dict):
        return out
    for item in doc.get("resolutions") or []:
        if isinstance(item, dict) and isinstance(item.get("proposition_id"), str):
            out[item["proposition_id"]] = item
    return out


def brier_score(p: float, y: int) -> float:
    return (p - y) ** 2


def log_score(p: float, y: int) -> float:
    q = min(1.0 - EPS, max(EPS, p))
    if y == 1:
        return math.log(q)
    return math.log(1.0 - q)


def classify_statement(
    statement: dict,
    resolution: dict | None,
    participants: list[str],
) -> dict:
    """Sequential classifier. Independent recount uses a different mechanism."""
    pid = statement.get("proposition_id")
    participant = statement.get("participant_id")
    p = _p(statement)
    bind = _binding(statement)
    source = str(bind.get("source_class") or "")
    row = {
        "proposition_id": pid,
        "participant_id": participant,
        "stated_confidence": p,
        "outcome": None,
        "brier": None,
        "log_score": None,
        "status": "UNSCOREABLE",
        "reason": "",
    }
    if p is None:
        row["reason"] = "stated_confidence missing or outside [0,1]"
        return row
    if source not in ALLOWED_SOURCES:
        row["reason"] = (
            "no resolvable outcome: source_class is not a named later observable "
            f"(got {source or 'missing'})"
        )
        return row
    missing = [k for k in REQUIRED_BINDING if not bind.get(k)]
    if missing:
        row["status"] = "UNSCOREABLE"
        row["reason"] = f"resolution_binding missing required fields: {missing}"
        return row
    if resolution is None:
        row["status"] = "PENDING"
        row["reason"] = "binding declared; outcome not yet recorded"
        return row
    res_source = str(resolution.get("source_class") or "")
    if res_source in FORBIDDEN_SETTLERS or res_source != source:
        row["status"] = "REJECTED_RESOLUTION"
        row["reason"] = (
            f"resolution source {res_source!r} does not settle binding {source!r}"
        )
        return row
    recorder = str(resolution.get("recorder_id") or "")
    if recorder and recorder in set(participants):
        row["status"] = "REJECTED_RESOLUTION"
        row["reason"] = "recorder_id is a session participant; cannot mark own homework"
        return row
    if resolution.get("proposition_id") != pid:
        row["status"] = "REJECTED_RESOLUTION"
        row["reason"] = "resolution proposition_id does not match statement"
        return row
    y = resolution.get("outcome")
    if y not in (0, 1):
        row["status"] = "REJECTED_RESOLUTION"
        row["reason"] = "resolution outcome is not binary 0/1"
        return row
    row["status"] = "RESOLVED"
    row["outcome"] = int(y)
    row["brier"] = brier_score(p, int(y))
    row["log_score"] = log_score(p, int(y))
    row["reason"] = "resolved against the binding's named source"
    return row


def score_run(trajectory: dict, resolution_doc: dict | None = None) -> dict:
    statements = [
        s for s in (trajectory.get("statements") or []) if isinstance(s, dict)
    ]
    participants = [str(x) for x in (trajectory.get("participants") or [])]
    res_index = _index_resolutions(resolution_doc)
    rows = []
    for stmt in statements:
        pid = stmt.get("proposition_id")
        res = res_index.get(pid) if isinstance(pid, str) else None
        rows.append(classify_statement(stmt, res, participants))
    counts = {
        "RESOLVED": 0,
        "PENDING": 0,
        "UNSCOREABLE": 0,
        "REJECTED_RESOLUTION": 0,
    }
    briers: list[float] = []
    logs: list[float] = []
    for row in rows:
        st = str(row["status"])
        counts[st] = counts.get(st, 0) + 1
        if st == "RESOLVED":
            briers.append(float(row["brier"]))
            logs.append(float(row["log_score"]))
    n_resolved = counts["RESOLVED"]
    mean_brier = (sum(briers) / n_resolved) if n_resolved else None
    mean_log = (sum(logs) / n_resolved) if n_resolved else None
    return {
        "council_run_id": trajectory.get("council_run_id"),
        "n_statements": len(rows),
        "n_resolved": n_resolved,
        "n_pending": counts["PENDING"],
        "n_unscoreable": counts["UNSCOREABLE"],
        "n_rejected_resolution": counts["REJECTED_RESOLUTION"],
        "mean_brier": mean_brier,
        "mean_log_score": mean_log,
        "calibration_population": "resolved_only",
        "not_yet_meaningful": n_resolved < MEANINGFUL_N,
        "unscoreable_counted_as_calibrated": False,
        "rows": rows,
    }


def score_paths(traj_path: Path, res_path: Path | None) -> dict:
    traj = load_json(traj_path)
    res = load_json(res_path) if res_path and res_path.is_file() else None
    return score_run(traj, res)


def fixture_dir(name: str) -> Path:
    return Path(__file__).resolve().parent / "fixtures" / name
