#!/usr/bin/env python3
"""Execute a workflow spec against one case. Dispatch is by definition shape."""
from __future__ import annotations

from typing import Any


def compute_from_operands(case: dict[str, Any]) -> dict[str, Any]:
    """Genuine solver: uses a, b, op only. Never reads case id."""
    op = str(case["op"])
    left = int(case["a"])
    right = int(case["b"])
    if op == "add":
        value: int | str = left + right
    elif op == "mul":
        value = left * right
    elif op == "xor":
        value = left ^ right
    elif op == "cat":
        value = f"{left}:{right}"
    else:
        raise ValueError(f"unknown op {op!r}")
    return {"result": value}


def _copy_table(table: dict[str, Any] | None, case_id: str) -> dict[str, Any] | None:
    if not isinstance(table, dict):
        return None
    hit = table.get(case_id)
    if isinstance(hit, dict):
        return dict(hit)
    if hit is None:
        return None
    return {"result": hit}


def run(spec: dict[str, Any], case: dict[str, Any]) -> dict[str, Any] | None:
    ep = str(spec.get("entrypoint") or "")
    if ep == "omit_artifact":
        return None
    if ep == "compute_from_operands" or spec.get("uses_inputs"):
        return compute_from_operands(case)
    cid = str(case["id"])
    for key in ("lookup", "oracle_answers", "test_mode_answers"):
        copied = _copy_table(spec.get(key) if isinstance(spec.get(key), dict) else None, cid)
        if copied is not None:
            return copied
        if isinstance(spec.get(key), dict) and key in spec:
            return {"result": f"miss:{key}"}
    if spec.get("test_mode") is True:
        return {"result": "test-mode-miss"}
    if spec.get("exploit_weak_oracle") is True or spec.get("constant_result") is not None:
        return {"result": spec.get("constant_result", 0)}
    return None
