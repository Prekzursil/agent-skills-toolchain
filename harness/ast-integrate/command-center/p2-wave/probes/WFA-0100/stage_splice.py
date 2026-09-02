#!/usr/bin/env python3
"""Stage-splice INSERT fusion operator (WFA-0100).

Inserts a donor workflow's stage into a host pipeline at a typed insertion
point, rewires inputs and outputs, and REFUSES when the donor stage's input
type is unsatisfied at that point. No coercion.

Shipped path: type-check -> (optional refuse) -> emit.
Known-broken control: coerce_splice rewrites the donor input type to the
producer's type and emits anyway. Probe 2 uses that mutant so 'fusion is
None on unsatisfiable input' is a live detector, not a comment.

This is INSERT, not IMP-0182's replace-one-slot splice.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from ir import OPERATOR, deepcopy_workflow
from typecheck import insertion_type_check, rewire_map

REASON_UNSATISFIED_INPUT = "unsatisfied-input-type"


def _qualify(donor: dict[str, Any], stage: dict[str, Any]) -> str:
    return f"{donor.get('id')}::{stage.get('id')}"


def build_fusion(
    host: dict[str, Any],
    donor: dict[str, Any],
    insert_index: int,
    donor_index: int,
    donor_stage: dict[str, Any],
) -> dict[str, Any]:
    spliced = deepcopy(donor_stage)
    spliced_id = _qualify(donor, donor_stage)
    spliced["id"] = spliced_id
    spliced["spliced_from"] = {
        "workflow_id": donor.get("id"),
        "stage_id": donor_stage.get("id"),
        "index": donor_index,
    }
    host_stages = [deepcopy(s) for s in (host.get("stages") or [])]
    stages = host_stages[:insert_index] + [spliced] + host_stages[insert_index:]
    wires = rewire_map(host, donor_stage, insert_index, spliced_id)
    after_id = host_stages[insert_index - 1]["id"] if insert_index > 0 else None
    before_id = host_stages[insert_index]["id"] if insert_index < len(host_stages) else None
    return {
        "id": f"{host.get('id')}++{donor.get('id')}::{OPERATOR}",
        "kind": "workflow-ir",
        "operator": OPERATOR,
        "source_anchor": "command-center/p2-wave/probes/WFA-0100/stage_splice.py:build_fusion",
        "entry": deepcopy(host.get("entry") or []),
        "exit": deepcopy(host.get("exit") or []),
        "stages": stages,
        "rewire": wires,
        "lineage": {
            "operator": OPERATOR,
            "host_id": host.get("id"),
            "donor_id": donor.get("id"),
            "insert_index": insert_index,
            "donor_index": donor_index,
            "donor_stage_id": donor_stage.get("id"),
            "spliced_stage_id": spliced_id,
            "after_stage_id": after_id,
            "before_stage_id": before_id,
            "source_ids": [host.get("id"), donor.get("id")],
            "parents": [host.get("id"), donor.get("id")],
        },
        "licence": host.get("licence") or donor.get("licence"),
        "version": "splice-insert-1",
    }


def stage_splice(
    host: dict[str, Any],
    donor: dict[str, Any],
    insert_index: int,
    donor_index: int = 0,
) -> dict[str, Any]:
    """Shipped operator. Type check is the first trace event. Emit is last."""
    trace = ["type-check"]
    check = insertion_type_check(host, donor, insert_index, donor_index)
    if not check["ok"]:
        trace.append("refuse")
        return {
            "status": "refused",
            "reason": check["reason"],
            "fusion": None,
            "trace": trace,
            "type_check": check,
            "operator": OPERATOR,
            "host_id": host.get("id"),
            "donor_id": donor.get("id"),
            "insert_index": insert_index,
            "donor_index": donor_index,
        }
    donor_stage = (donor.get("stages") or [])[donor_index]
    trace.append("emit")
    fusion = build_fusion(host, donor, insert_index, donor_index, donor_stage)
    return {
        "status": "emitted",
        "reason": None,
        "fusion": fusion,
        "trace": trace,
        "type_check": check,
        "operator": OPERATOR,
        "host_id": host.get("id"),
        "donor_id": donor.get("id"),
        "insert_index": insert_index,
        "donor_index": donor_index,
        "stage_order": [s.get("id") for s in fusion["stages"]],
    }


def coerce_splice(
    host: dict[str, Any],
    donor: dict[str, Any],
    insert_index: int,
    donor_index: int = 0,
) -> dict[str, Any]:
    """Known-broken: rewrite donor input type to the producer type, then emit.

    Silent coercion. Not used by the shipped path. The independent checker
    still reports the original donor as unsatisfied.
    """
    from typecheck import producer_at

    trace = ["coerce", "emit"]
    host_stages = host.get("stages") or []
    donor_stages = donor.get("stages") or []
    if insert_index < 0 or insert_index > len(host_stages):
        return {
            "status": "refused",
            "reason": "index-error",
            "fusion": None,
            "trace": trace,
            "mutant": "coerce-input-type",
            "operator": OPERATOR,
        }
    if donor_index < 0 or donor_index >= len(donor_stages):
        return {
            "status": "refused",
            "reason": "index-error",
            "fusion": None,
            "trace": trace,
            "mutant": "coerce-input-type",
            "operator": OPERATOR,
        }
    pred = producer_at(host, insert_index)
    coerced = deepcopy_workflow(donor)
    stage = coerced["stages"][donor_index]
    want = str(pred["scalar"] or "")
    stage["input_type"] = want
    if pred["ports"]:
        stage["inputs"] = [dict(p) for p in pred["ports"]]
    else:
        stage["inputs"] = [{"name": "in", "type": want}]
    fusion = build_fusion(host, coerced, insert_index, donor_index, stage)
    return {
        "status": "emitted",
        "reason": None,
        "fusion": fusion,
        "trace": trace,
        "mutant": "coerce-input-type",
        "coerced_input_type": want,
        "original_input_type": (donor_stages[donor_index] or {}).get("input_type"),
        "operator": OPERATOR,
        "host_id": host.get("id"),
        "donor_id": donor.get("id"),
        "insert_index": insert_index,
        "donor_index": donor_index,
    }
