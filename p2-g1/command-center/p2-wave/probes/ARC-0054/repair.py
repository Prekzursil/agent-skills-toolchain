"""Repair path and dry-run planner for undocumented workflow stopping.

No product `plugin repair` CLI exists on this worktree. The repair path
this unit can actually execute documents a workflow stopping object
(finite bound + terminal disposition + owner-facing doc).

Healthy target → status NO-OP and zero bytes written (not SUCCESS).
Broken target → status REPAIRED and a real write.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from criteria import documented_copy, stopping_documented


def _dump(obj: Any) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=True) + "\n").encode("utf-8")


def plan_repair(workflow: dict[str, Any], rel: str = "workflow.json") -> dict[str, Any]:
    ok, why = stopping_documented(workflow)
    if ok:
        return {"status": "NO-OP", "files": [], "bytes": 0, "reason": why}
    repaired = documented_copy(workflow)
    raw = _dump(repaired)
    return {
        "status": "WOULD-REPAIR",
        "files": [rel],
        "bytes": len(raw),
        "reason": why,
    }


def apply_repair(
    workflow: dict[str, Any], rel: str = "workflow.json"
) -> tuple[dict[str, Any], dict[str, Any]]:
    ok, why = stopping_documented(workflow)
    if ok:
        return workflow, {
            "status": "NO-OP",
            "files": [],
            "bytes_written": 0,
            "reason": why,
        }
    repaired = documented_copy(workflow)
    raw = _dump(repaired)
    return repaired, {
        "status": "REPAIRED",
        "files": [rel],
        "bytes_written": len(raw),
        "reason": why,
    }


def lying_plan(_workflow: dict[str, Any]) -> dict[str, Any]:
    return {"status": "NO-OP", "files": [], "bytes": 0, "reason": "lie"}


def mislabel_success(workflow: dict[str, Any]) -> dict[str, Any]:
    ok, why = stopping_documented(workflow)
    return {
        "status": "SUCCESS",
        "files": [],
        "bytes_written": 0,
        "reason": why if ok else "would-have-repaired",
    }


def silent_repair(_workflow: dict[str, Any]) -> dict[str, Any]:
    return {"status": "", "files": [], "bytes_written": 0, "reason": "silent"}


def write_if_needed(path: Path, workflow: dict[str, Any]) -> dict[str, Any]:
    before = path.read_bytes() if path.is_file() else b""
    live = json.loads(before.decode("utf-8")) if before else workflow
    repaired, result = apply_repair(live, rel=path.name)
    if result["status"] == "NO-OP":
        return result
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = _dump(repaired)
    path.write_bytes(raw)
    result["bytes_written"] = len(raw)
    result["wrote"] = True
    return result
