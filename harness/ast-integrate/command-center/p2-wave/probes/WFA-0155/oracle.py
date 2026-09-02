"""Execution-trace equivalence oracle for the TRANSLATE route.

ORACLE-FINGERPRINT: execution-trace-equivalence-not-structural
Fidelity is demonstrated by executing source and translation on the same
case and diffing the stage/gate/stop trace.
"""
from __future__ import annotations

import copy
from typing import Any

from exec_trace import execute_foreign, execute_native


def traces_equivalent(source_trace: dict, translation_trace: dict) -> bool:
    return source_trace == translation_trace


def diff_traces(source_trace: dict, translation_trace: dict) -> dict:
    """Name the first diverging stage, gate, or stop. Empty diffs mean equal."""
    mismatches: list[dict] = []
    ss = source_trace["stages_entered"]
    ts = translation_trace["stages_entered"]
    if ss != ts:
        mismatches.append(
            {
                "axis": "stage_order",
                "source": ss,
                "translation": ts,
            }
        )
    sg = source_trace["gates"]
    tg = translation_trace["gates"]
    n = max(len(sg), len(tg))
    for i in range(n):
        a = sg[i] if i < len(sg) else None
        b = tg[i] if i < len(tg) else None
        if a != b:
            mismatches.append(
                {
                    "axis": "gate",
                    "index": i,
                    "source": a,
                    "translation": b,
                    "named_gate": (b or a or {}).get("stage"),
                    "named_field": (b or a or {}).get("field"),
                }
            )
            break
    if source_trace["stop"] != translation_trace["stop"]:
        mismatches.append(
            {
                "axis": "stop",
                "source": source_trace["stop"],
                "translation": translation_trace["stop"],
            }
        )
    return {
        "equivalent": not mismatches,
        "mismatches": mismatches,
        "source_trace": source_trace,
        "translation_trace": translation_trace,
    }


def judge(foreign: dict, native: dict, case: dict) -> dict:
    src = execute_foreign(foreign, case)
    dst = execute_native(native, case)
    report = diff_traces(src, dst)
    report["case_id"] = case.get("id")
    report["pass"] = bool(report["equivalent"])
    return report


def mutate_one_gate(native: dict, *, stage: str, field: str, new_op: str) -> dict:
    """Mutate exactly one gate in the translation (catalog both-states)."""
    mutant = copy.deepcopy(native)
    hits = 0
    for g in mutant["gates"]:
        if g["stage"] == stage and g["field"] == field:
            g["op"] = new_op
            g["mutated"] = True
            hits += 1
    if hits != 1:
        raise ValueError(f"mutate expected 1 gate {stage}.{field}, got {hits}")
    return mutant


def named_gate(mismatches: list[dict]) -> dict[str, Any] | None:
    for row in mismatches:
        if row.get("axis") == "gate":
            return {
                "stage": row.get("named_gate"),
                "field": row.get("named_field"),
                "index": row.get("index"),
            }
    return None
