#!/usr/bin/env python3
"""Independent type-satisfaction checker at a typed insertion point.

This module does not emit fusions. WFA-0100 evidence B requires a checker
separate from the splice operator: if the operator's only signal is 'I
emitted', type coercion is invisible. Exact type strings; no subtype, no
alias, no case-fold.
"""
from __future__ import annotations

from typing import Any

from ir import ports, stage_scalar_in, stage_scalar_out

REASON_INDEX = "index-error"
REASON_UNSATISFIED_INPUT = "unsatisfied-input-type"
REASON_UNSATISFIED_OUTPUT = "unsatisfied-output-type"
REASON_EMPTY = "empty-stage"


def cover(
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


def producer_at(host: dict[str, Any], insert_index: int) -> dict[str, Any]:
    stages = host.get("stages") or []
    if insert_index <= 0:
        return {
            "id": "entry",
            "kind": "entry",
            "ports": ports(host, "entry"),
            "scalar": str(host.get("entry_type") or "") or (
                ports(host, "entry")[0]["type"] if ports(host, "entry") else None
            ),
        }
    pred = stages[insert_index - 1]
    return {
        "id": pred.get("id"),
        "kind": "stage",
        "ports": ports(pred, "outputs"),
        "scalar": stage_scalar_out(pred),
    }


def consumer_after(host: dict[str, Any], insert_index: int) -> dict[str, Any] | None:
    stages = host.get("stages") or []
    if insert_index >= len(stages):
        exit_ports = ports(host, "exit")
        if not exit_ports and not host.get("exit_type"):
            return None
        return {
            "id": "exit",
            "kind": "exit",
            "ports": exit_ports,
            "scalar": str(host.get("exit_type") or "") or (
                exit_ports[0]["type"] if exit_ports else None
            ),
        }
    succ = stages[insert_index]
    return {
        "id": succ.get("id"),
        "kind": "stage",
        "ports": ports(succ, "inputs"),
        "scalar": stage_scalar_in(succ),
    }


def insertion_type_check(
    host: dict[str, Any],
    donor: dict[str, Any],
    insert_index: int,
    donor_index: int,
) -> dict[str, Any]:
    """Pure check. Does not build a fusion object."""
    host_stages = host.get("stages") or []
    donor_stages = donor.get("stages") or []
    n = len(host_stages)
    if insert_index < 0 or insert_index > n:
        return {
            "ok": False,
            "reason": REASON_INDEX,
            "insert_index": insert_index,
            "host_stage_count": n,
            "checked_before_emit": True,
        }
    if donor_index < 0 or donor_index >= len(donor_stages):
        return {
            "ok": False,
            "reason": REASON_INDEX,
            "where": "donor_index",
            "donor_index": donor_index,
            "checked_before_emit": True,
        }
    donor_stage = donor_stages[donor_index]
    donor_in = ports(donor_stage, "inputs")
    donor_out = ports(donor_stage, "outputs")
    if not donor_in:
        return {
            "ok": False,
            "reason": REASON_EMPTY,
            "insert_index": insert_index,
            "checked_before_emit": True,
        }

    pred = producer_at(host, insert_index)
    in_ok, in_missing = cover(pred["ports"], donor_in)

    succ = consumer_after(host, insert_index)
    out_ok, out_missing = True, []
    successor_id = None
    if succ is not None and succ["ports"]:
        successor_id = succ["id"]
        out_ok, out_missing = cover(donor_out, succ["ports"])

    ok = bool(in_ok and out_ok)
    reason = None
    if not in_ok:
        reason = REASON_UNSATISFIED_INPUT
    elif not out_ok:
        reason = REASON_UNSATISFIED_OUTPUT
    return {
        "ok": ok,
        "reason": reason,
        "insert_index": insert_index,
        "donor_index": donor_index,
        "donor_stage_id": donor_stage.get("id"),
        "predecessor_id": pred["id"],
        "successor_id": successor_id,
        "producer_type": pred["scalar"],
        "donor_input_type": stage_scalar_in(donor_stage),
        "donor_output_type": stage_scalar_out(donor_stage),
        "successor_input_type": succ["scalar"] if succ else None,
        "input_cover_ok": in_ok,
        "output_cover_ok": out_ok,
        "missing_inputs": in_missing,
        "missing_outputs": out_missing,
        "producer_ports": pred["ports"],
        "donor_input_ports": donor_in,
        "donor_output_ports": donor_out,
        "checked_before_emit": True,
        "coercion": False,
    }


def rewire_map(
    host: dict[str, Any],
    donor_stage: dict[str, Any],
    insert_index: int,
    spliced_id: str,
) -> dict[str, Any]:
    """Name the wires the operator will install. Uses the same cover rules."""
    pred = producer_at(host, insert_index)
    succ = consumer_after(host, insert_index)
    donor_in = ports(donor_stage, "inputs")
    donor_out = ports(donor_stage, "outputs")
    inputs: list[dict[str, str]] = []
    remaining = list(pred["ports"])
    for need in donor_in:
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
            continue
        have = remaining.pop(hit)
        inputs.append(
            {
                "consumer_stage": spliced_id,
                "consumer_port": need["name"],
                "producer_stage": str(pred["id"]),
                "producer_port": have["name"],
                "type": need["type"],
            }
        )
    outputs: list[dict[str, str]] = []
    if succ is not None:
        remaining_out = list(donor_out)
        for need in succ["ports"]:
            hit = None
            for i, have in enumerate(remaining_out):
                if have["name"] == need["name"] and have["type"] == need["type"]:
                    hit = i
                    break
            if hit is None:
                type_hits = [i for i, have in enumerate(remaining_out) if have["type"] == need["type"]]
                if len(type_hits) == 1:
                    hit = type_hits[0]
            if hit is None:
                continue
            have = remaining_out.pop(hit)
            outputs.append(
                {
                    "producer_stage": spliced_id,
                    "producer_port": have["name"],
                    "consumer_stage": str(succ["id"]),
                    "consumer_port": need["name"],
                    "type": need["type"],
                }
            )
    return {"inputs": inputs, "outputs": outputs}
