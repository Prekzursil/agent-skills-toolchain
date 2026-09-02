#!/usr/bin/env python3
"""Stage-splice fusion operator (IMP-0182).

Replace host.stages[i] with a better-performing donor stage, preserving the
surrounding contract. Neighbour input/output contracts are checked BEFORE any
fusion workflow is constructed. A mismatch is a refusal, not a coercion.

Shipped path: check -> (optional refuse) -> emit.
Known-broken control: emit_first_mutant emits a fusion object and only then
inspects contracts. Probe 1 uses that mutant as the bad state so 'fusion is
None on mismatch' is a live detector, not a comment.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from workflow_ir import (
    STRATEGY,
    canonical_bytes,
    deepcopy_workflow,
    ports,
    stage_fingerprint,
)

REASON_CONTRACT = "contract-mismatch"
REASON_NOOP = "noop-fusion"
REASON_NOT_BETTER = "not-better-performing"
REASON_INDEX = "index-error"
REASON_METRIC = "metric-mismatch"


def _cover(
    producer_outputs: list[dict[str, str]], consumer_inputs: list[dict[str, str]]
) -> tuple[bool, list[dict[str, str]]]:
    """Each consumer input needs a producer output of equal type. No coercion.

    Prefer name+type. Fall back to a unique remaining type match. Two outputs
    of the same type without a name hit are ambiguous and do not satisfy.
    """
    remaining = list(producer_outputs)
    missing: list[dict[str, str]] = []
    for need in consumer_inputs:
        hit = None
        for i, have in enumerate(remaining):
            if have["name"] == need["name"] and have["type"] == need["type"]:
                hit = i
                break
        if hit is None:
            type_hits = [i for i, have in enumerate(remaining) if have["type"] == need["type"]]
            if len(type_hits) == 1:
                hit = type_hits[0]
        if hit is None:
            missing.append(dict(need))
        else:
            remaining.pop(hit)
    return (not missing), missing


def neighbour_contracts(
    host: dict[str, Any], host_index: int, donor_stage: dict[str, Any]
) -> dict[str, Any]:
    """Pure check. Does not build a fusion object."""
    stages = host.get("stages") or []
    n = len(stages)
    if host_index < 0 or host_index >= n:
        return {
            "ok": False,
            "reason": REASON_INDEX,
            "host_index": host_index,
            "stage_count": n,
        }
    if host_index == 0:
        pred_ports = ports(host, "entry") if host.get("entry") else []
        pred_id = "entry"
    else:
        pred_ports = ports(stages[host_index - 1], "outputs")
        pred_id = stages[host_index - 1].get("id")
    donor_in = ports(donor_stage, "inputs")
    in_ok, in_missing = _cover(pred_ports, donor_in)

    if host_index == n - 1:
        succ_in = ports(host, "exit") if host.get("exit") else []
        succ_id = "exit"
    else:
        succ_in = ports(stages[host_index + 1], "inputs")
        succ_id = stages[host_index + 1].get("id")
    donor_out = ports(donor_stage, "outputs")
    out_ok, out_missing = _cover(donor_out, succ_in)

    ok = bool(in_ok and out_ok)
    return {
        "ok": ok,
        "reason": None if ok else REASON_CONTRACT,
        "host_index": host_index,
        "predecessor_id": pred_id,
        "successor_id": succ_id,
        "donor_stage_id": donor_stage.get("id"),
        "input_cover_ok": in_ok,
        "output_cover_ok": out_ok,
        "missing_inputs": in_missing,
        "missing_outputs": out_missing,
        "checked_before_emit": True,
    }


def _score_of(stage: dict[str, Any]) -> tuple[str | None, float | None]:
    perf = stage.get("performance") or {}
    metric = perf.get("metric")
    score = perf.get("score")
    if metric is None or not isinstance(score, (int, float)):
        return (str(metric) if metric is not None else None, None)
    return str(metric), float(score)


def _preconditions(
    host: dict[str, Any],
    donor: dict[str, Any],
    host_index: int,
    donor_index: int,
) -> dict[str, Any]:
    host_stages = host.get("stages") or []
    donor_stages = donor.get("stages") or []
    if host_index < 0 or host_index >= len(host_stages):
        return {"ok": False, "reason": REASON_INDEX, "where": "host_index"}
    if donor_index < 0 or donor_index >= len(donor_stages):
        return {"ok": False, "reason": REASON_INDEX, "where": "donor_index"}
    host_stage = host_stages[host_index]
    donor_stage = donor_stages[donor_index]
    contracts = neighbour_contracts(host, host_index, donor_stage)
    if not contracts["ok"]:
        return {"ok": False, "reason": contracts["reason"], "contracts": contracts}

    if stage_fingerprint(host_stage) == stage_fingerprint(donor_stage):
        return {
            "ok": False,
            "reason": REASON_NOOP,
            "contracts": contracts,
            "note": "donor stage is structurally identical to the host slot",
        }

    h_metric, h_score = _score_of(host_stage)
    d_metric, d_score = _score_of(donor_stage)
    if h_metric is None or d_metric is None or h_score is None or d_score is None:
        return {
            "ok": False,
            "reason": REASON_METRIC,
            "contracts": contracts,
            "host_metric": h_metric,
            "donor_metric": d_metric,
        }
    if h_metric != d_metric:
        return {
            "ok": False,
            "reason": REASON_METRIC,
            "contracts": contracts,
            "host_metric": h_metric,
            "donor_metric": d_metric,
        }
    if not (d_score > h_score):
        return {
            "ok": False,
            "reason": REASON_NOT_BETTER,
            "contracts": contracts,
            "host_score": h_score,
            "donor_score": d_score,
            "metric": h_metric,
        }
    return {
        "ok": True,
        "reason": None,
        "contracts": contracts,
        "host_score": h_score,
        "donor_score": d_score,
        "metric": h_metric,
        "host_stage": host_stage,
        "donor_stage": donor_stage,
    }


def _build_fusion(
    host: dict[str, Any],
    donor: dict[str, Any],
    host_index: int,
    donor_index: int,
    donor_stage: dict[str, Any],
) -> dict[str, Any]:
    stages = [deepcopy(s) for s in (host.get("stages") or [])]
    spliced = deepcopy(donor_stage)
    spliced["id"] = f"{donor.get('id')}::{donor_stage.get('id')}"
    spliced["spliced_from"] = {
        "workflow_id": donor.get("id"),
        "stage_id": donor_stage.get("id"),
        "index": donor_index,
    }
    stages[host_index] = spliced
    return {
        "id": f"{host.get('id')}++{donor.get('id')}::{STRATEGY}",
        "strategy": STRATEGY,
        "entry": deepcopy(host.get("entry") or []),
        "exit": deepcopy(host.get("exit") or []),
        "stages": stages,
        "lineage": {
            "strategy": STRATEGY,
            "host_id": host.get("id"),
            "donor_id": donor.get("id"),
            "host_stage_id": (host.get("stages") or [])[host_index].get("id"),
            "donor_stage_id": donor_stage.get("id"),
            "host_index": host_index,
            "donor_index": donor_index,
            "parents": [host.get("id"), donor.get("id")],
        },
        "licence": host.get("licence") or donor.get("licence"),
        "version": "splice-1",
    }


def stage_splice(
    host: dict[str, Any],
    donor: dict[str, Any],
    host_index: int,
    donor_index: int,
) -> dict[str, Any]:
    """Shipped operator. Contract check is the first trace event. Emit is last."""
    trace = ["contract-check"]
    pre = _preconditions(host, donor, host_index, donor_index)
    if not pre["ok"]:
        trace.append("refuse")
        return {
            "status": "refused",
            "reason": pre["reason"],
            "fusion": None,
            "trace": trace,
            "preconditions": {k: v for k, v in pre.items() if k not in {"host_stage", "donor_stage"}},
            "strategy": STRATEGY,
            "host_id": host.get("id"),
            "donor_id": donor.get("id"),
            "host_index": host_index,
            "donor_index": donor_index,
        }
    trace.append("emit")
    fusion = _build_fusion(host, donor, host_index, donor_index, pre["donor_stage"])
    return {
        "status": "emitted",
        "reason": None,
        "fusion": fusion,
        "trace": trace,
        "preconditions": {k: v for k, v in pre.items() if k not in {"host_stage", "donor_stage"}},
        "strategy": STRATEGY,
        "host_id": host.get("id"),
        "donor_id": donor.get("id"),
        "host_index": host_index,
        "donor_index": donor_index,
        "fusion_bytes": len(canonical_bytes(fusion)),
    }


def emit_first_mutant(
    host: dict[str, Any],
    donor: dict[str, Any],
    host_index: int,
    donor_index: int,
) -> dict[str, Any]:
    """Known-broken: constructs a fusion object, then checks contracts.

    On a mismatch this still carries a fusion workflow, which is the silent
    coercion the spec forbids. Not used by the shipped path.
    """
    trace = ["emit"]
    host_stages = host.get("stages") or []
    donor_stages = donor.get("stages") or []
    fusion = None
    if 0 <= host_index < len(host_stages) and 0 <= donor_index < len(donor_stages):
        fusion = _build_fusion(host, donor, host_index, donor_index, donor_stages[donor_index])
    trace.append("contract-check")
    pre = _preconditions(deepcopy_workflow(host), deepcopy_workflow(donor), host_index, donor_index)
    if not pre["ok"]:
        trace.append("refuse")
        return {
            "status": "refused",
            "reason": pre["reason"],
            "fusion": fusion,
            "trace": trace,
            "preconditions": {k: v for k, v in pre.items() if k not in {"host_stage", "donor_stage"}},
            "strategy": STRATEGY,
            "mutant": "emit-first",
        }
    return {
        "status": "emitted",
        "reason": None,
        "fusion": fusion,
        "trace": trace,
        "preconditions": {k: v for k, v in pre.items() if k not in {"host_stage", "donor_stage"}},
        "strategy": STRATEGY,
        "mutant": "emit-first",
    }
