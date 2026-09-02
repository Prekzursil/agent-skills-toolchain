"""Structural census that WFA-0141-style plane-counting would accept.

A semantically inverted gate still has one control plane, the same stage
id set, and the same gate count. That census is therefore not a fidelity
oracle.
"""
from __future__ import annotations

from translate import NATIVE_PLANE


def structural_census(foreign: dict, native: dict) -> dict:
    task_ids = [n["id"] for n in foreign["nodes"] if n["kind"] == "task"]
    if_count = sum(1 for n in foreign["nodes"] if n["kind"] == "if")
    stage_ids = [s["id"] for s in native.get("stages") or []]
    planes = {native.get("plane")}
    stage_set_equal = set(task_ids) == set(stage_ids)
    gate_count_equal = if_count == len(native.get("gates") or [])
    one_plane = planes == {NATIVE_PLANE}
    return {
        "control_planes": sorted(p for p in planes if p),
        "control_plane_count": len(planes),
        "one_native_plane": one_plane,
        "source_task_ids": task_ids,
        "translation_stage_ids": stage_ids,
        "stage_id_set_equal": stage_set_equal,
        "source_if_count": if_count,
        "translation_gate_count": len(native.get("gates") or []),
        "gate_count_equal": gate_count_equal,
        "would_pass_wfa0141_style": bool(
            one_plane and stage_set_equal and gate_count_equal
        ),
    }
