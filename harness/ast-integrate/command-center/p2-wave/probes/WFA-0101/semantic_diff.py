"""Five-dimension structural differ used when WFA-0094's engine is absent.

Dimensions: stage (kind+contracts), role, gate, tool, stop-rule.
Aligns stages by LCS of kinds, then classifies each dimension as EQUAL,
ABSENT (in one side only), or PRESENT-BUT-DIFFERENT.
"""
from __future__ import annotations

from typing import Any

from workflow_foundry.common_core import lcs_two
from workflow_foundry.workflow_ir import Stage, Workflow, canonical_json

DIMENSIONS = ("stage", "role", "gate", "tool", "stop_rule")


def _token(stage: Stage, dim: str) -> Any:
    gate = stage.gate if isinstance(stage.gate, dict) else {}
    if dim == "stage":
        return (stage.kind, stage.in_contract, stage.out_contract)
    if dim == "role":
        return tuple(sorted(stage.roles))
    if dim == "gate":
        body = dict(gate)
        body.pop("stop_rule", None)
        return canonical_json(body)
    if dim == "tool":
        return stage.tool_class
    if dim == "stop_rule":
        return canonical_json(gate.get("stop_rule"))
    raise KeyError(dim)


def _classify(left: Any | None, right: Any | None, *, left_on: bool, right_on: bool) -> str:
    if not left_on and not right_on:
        return "EQUAL"
    if not left_on and right_on:
        return "ABSENT-IN-LEFT"
    if left_on and not right_on:
        return "ABSENT-IN-RIGHT"
    if left != right:
        return "PRESENT-BUT-DIFFERENT"
    return "EQUAL"


def diff_workflows(left: Workflow, right: Workflow) -> dict[str, Any]:
    lk = [s.kind for s in left.stages]
    rk = [s.kind for s in right.stages]
    shared = lcs_two(lk, rk)
    li = ri = 0
    rows: list[dict[str, Any]] = []
    counts = {
        "EQUAL": 0,
        "ABSENT-IN-LEFT": 0,
        "ABSENT-IN-RIGHT": 0,
        "PRESENT-BUT-DIFFERENT": 0,
    }

    def emit(lstage: Stage | None, rstage: Stage | None, reason: str) -> None:
        entry: dict[str, Any] = {
            "left_id": None if lstage is None else lstage.id,
            "right_id": None if rstage is None else rstage.id,
            "left_kind": None if lstage is None else lstage.kind,
            "right_kind": None if rstage is None else rstage.kind,
            "align": reason,
            "dimensions": {},
        }
        for dim in DIMENSIONS:
            cls = _classify(
                None if lstage is None else _token(lstage, dim),
                None if rstage is None else _token(rstage, dim),
                left_on=lstage is not None,
                right_on=rstage is not None,
            )
            entry["dimensions"][dim] = cls
            counts[cls] += 1
        rows.append(entry)

    for kind in shared:
        while li < len(left.stages) and left.stages[li].kind != kind:
            emit(left.stages[li], None, "left-only")
            li += 1
        while ri < len(right.stages) and right.stages[ri].kind != kind:
            emit(None, right.stages[ri], "right-only")
            ri += 1
        emit(left.stages[li], right.stages[ri], "aligned")
        li += 1
        ri += 1
    while li < len(left.stages):
        emit(left.stages[li], None, "left-only")
        li += 1
    while ri < len(right.stages):
        emit(None, right.stages[ri], "right-only")
        ri += 1

    empty = (
        counts["ABSENT-IN-LEFT"] == 0
        and counts["ABSENT-IN-RIGHT"] == 0
        and counts["PRESENT-BUT-DIFFERENT"] == 0
    )
    return {
        "empty": empty,
        "counts": counts,
        "rows": rows,
        "left_id": left.id,
        "right_id": right.id,
    }


def self_diff_empty(wf: Workflow) -> bool:
    return bool(diff_workflows(wf, wf)["empty"])
