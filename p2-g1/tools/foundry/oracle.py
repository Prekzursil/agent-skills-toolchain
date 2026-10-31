"""Shared runtime-receipt oracle for typed foundry workflows."""
from __future__ import annotations

from typing import Any


def check_runtime_receipt(
    receipt: dict[str, Any],
    *,
    expected_workflow_id: str,
    min_stages: int = 1,
) -> dict[str, Any]:
    errors: list[str] = []
    wf = receipt.get("workflow") if isinstance(receipt.get("workflow"), dict) else {}
    if receipt.get("bespoke_script") is not False:
        errors.append("bespoke_script")
    if wf.get("id") != expected_workflow_id:
        errors.append("workflow_id")
    stages = wf.get("stages") or receipt.get("trace") or []
    if not isinstance(stages, list) or len(stages) < min_stages:
        errors.append("min_stages")
    engine = receipt.get("engine")
    if not engine:
        errors.append("engine")
    return {
        "ok": not errors,
        "errors": errors,
        "workflow_id": wf.get("id"),
        "engine": engine,
        "n_stages": len(stages) if isinstance(stages, list) else 0,
    }
