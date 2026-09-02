"""Adopt / adapt / merge (stage-splice) / compose / build. Contract mismatch is a refusal."""
from __future__ import annotations

from typing import Any

from ir import UNIT, clone, fingerprint


def _lineage(operator: str, source_ids: list[str], note: str = "") -> dict[str, Any]:
    body: dict[str, Any] = {
        "operator": operator,
        "unit": UNIT,
        "source_ids": source_ids,
    }
    if note:
        body["note"] = note
    return body


def adopt(wf: dict[str, Any], source_id: str) -> dict[str, Any]:
    out = clone(wf)
    out["lineage"] = _lineage("ADOPT", [source_id], "scout incumbent reused as-is")
    return out


def adapt(wf: dict[str, Any], goal: str, source_id: str) -> dict[str, Any]:
    out = clone(wf)
    out["goal"] = goal
    out["id"] = f"{wf.get('id', 'wf')}.adapted"
    last = out["stages"][-1]
    gate = {
        "id": "adapt-gate",
        "kind": "gate",
        "inputs": list(last["outputs"]),
        "outputs": list(last["outputs"]),
        "tool": "contract-gate",
        "capability": "validate-schema",
        "timeout_seconds": 10,
    }
    existing = {s["id"] for s in out["stages"]}
    if gate["id"] in existing:
        gate["id"] = "adapt-gate-2"
    out["stages"] = list(out.get("stages") or []) + [gate]
    if isinstance(out.get("stopping"), dict):
        stop = dict(out["stopping"])
        stop["on_error"] = stop.get("on_error") or "halt"
        stop["max_stages"] = max(int(stop.get("max_stages") or 0), len(out["stages"]))
        out["stopping"] = stop
    out["lineage"] = _lineage("ADAPT", [source_id], "goal retarget plus contract-preserving gate")
    return out


def splice_replace(
    parent: dict[str, Any], slot_id: str, donor_stage: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Replace one stage. Neighbour contracts must match BEFORE the fusion is emitted."""
    parent = clone(parent)
    donor = clone(donor_stage)
    target = None
    idx = None
    for i, st in enumerate(parent.get("stages") or []):
        if st.get("id") == slot_id:
            target = st
            idx = i
            break
    if target is None or idx is None:
        return None, {
            "error_code": "UNKNOWN_SLOT",
            "message": f"parent has no stage {slot_id!r}",
        }
    if set(donor.get("inputs") or []) != set(target.get("inputs") or []) or set(
        donor.get("outputs") or []
    ) != set(target.get("outputs") or []):
        return None, {
            "error_code": "CONTRACT_MISMATCH",
            "message": (
                f"donor stage {donor.get('id')!r} io "
                f"{donor.get('inputs')}->{donor.get('outputs')} does not match "
                f"slot {slot_id!r} {target.get('inputs')}->{target.get('outputs')}"
            ),
            "slot_id": slot_id,
            "donor_id": donor.get("id"),
        }
    ids = {s["id"] for s in parent["stages"] if s["id"] != slot_id}
    if donor.get("id") in ids:
        donor["id"] = f"{donor['id']}.spliced"
    parent["stages"][idx] = donor
    parent["id"] = f"{parent.get('id', 'wf')}.spliced"
    parent["lineage"] = _lineage(
        "MERGE",
        [str(parent.get("id")), str(donor.get("id"))],
        f"stage-splice replaced {slot_id} with {donor.get('id')}",
    )
    return parent, None


def try_splice(
    parent: dict[str, Any], donor: dict[str, Any]
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """Find one contract-compatible replacement whose kind/id differs (not a no-op copy)."""
    for slot in parent.get("stages") or []:
        for cand in donor.get("stages") or []:
            if set(cand.get("inputs") or []) != set(slot.get("inputs") or []):
                continue
            if set(cand.get("outputs") or []) != set(slot.get("outputs") or []):
                continue
            if cand.get("kind") == slot.get("kind") and cand.get("id") == slot.get("id"):
                continue
            if cand.get("kind") == slot.get("kind") and cand.get("tool") == slot.get("tool"):
                continue
            merged, err = splice_replace(parent, slot["id"], cand)
            if err:
                return None, err
            if fingerprint(merged) in {fingerprint(parent), fingerprint(donor)}:
                continue
            return merged, None
    return None, {
        "error_code": "NO_SPLICE_CANDIDATE",
        "message": "no contract-compatible differing stage to splice",
    }


def compose(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Sequential composition: barrier consumes left terminal outputs, feeds right initials."""
    left = clone(left)
    right = clone(right)
    prefix = "L."
    suffix = "R."
    l_stages = []
    for st in left["stages"]:
        s = clone(st)
        s["id"] = prefix + s["id"]
        l_stages.append(s)
    last_outs = list(l_stages[-1]["outputs"])
    r_initial = list(right.get("initial_inputs") or [])
    barrier_outs = list(r_initial) if r_initial else ["compose.barrier.json"]
    barrier = {
        "id": "compose-barrier",
        "kind": "compose",
        "inputs": last_outs,
        "outputs": barrier_outs,
        "tool": "compose",
        "capability": "transform-json",
        "timeout_seconds": 15,
    }
    r_stages = []
    for st in right["stages"]:
        s = clone(st)
        s["id"] = suffix + s["id"]
        r_stages.append(s)
    stages = l_stages + [barrier] + r_stages
    initial = list(left.get("initial_inputs") or [])
    out = {
        "id": f"{left.get('id', 'a')}+{right.get('id', 'b')}",
        "kind": "workflow",
        "goal": f"compose({left.get('goal', '')} | {right.get('goal', '')})",
        "stages": stages,
        "stopping": {
            "max_stages": len(stages),
            "on_error": "halt",
        },
        "initial_inputs": initial,
        "lineage": _lineage(
            "COMPOSE",
            [str(left.get("id")), str(right.get("id"))],
            "sequential compose with explicit barrier",
        ),
    }
    return out


def build(goal: str) -> dict[str, Any]:
    return {
        "id": "wf.built.from-goal",
        "kind": "workflow",
        "goal": goal,
        "stages": [
            {
                "id": "plan",
                "kind": "transform",
                "inputs": ["goal"],
                "outputs": ["plan.json"],
                "tool": "json-transform",
                "capability": "transform-json",
                "timeout_seconds": 30,
            },
            {
                "id": "emit",
                "kind": "emit",
                "inputs": ["plan.json"],
                "outputs": ["workflow.json"],
                "tool": "receipt-emit",
                "capability": "write-local",
                "timeout_seconds": 30,
            },
        ],
        "stopping": {"max_stages": 2, "on_error": "halt"},
        "initial_inputs": ["goal"],
        "lineage": _lineage("BUILD", [], "synthesized from goal; not copied from scout"),
    }
