"""Two-signal fusion capability-loss detector (WFA-0108).

Signal A — mechanism incidence matrix: the fusion's declared mechanism set
must be a superset of the union of its sources' declared sets.

Signal B — behavioural probe: every mechanism reachable in a source must be
exercisable (token produced) through the fused pipeline. A mechanism id can
sit in the incidence record while the stage that implements it is not
reachable from the fusion entry; only B sees that.

A non-empty missing set from either signal is P1. Divergence between the two
missing sets is itself a finding. A fusion that fails may not proceed to
certification — attempt_certify returns REFUSED, it does not emit a record.
"""
from __future__ import annotations

from typing import Any

from fixtures import (
    EXTRACTION_RULE,
    FAILURE_CLASS_ID,
    HANDLERS,
    NAMED_FAILURE,
    SEED_CASES,
    SEVERITY_P1,
    TOKENS,
    all_workflows,
)


def reachable_stage_ids(workflow: dict[str, Any]) -> set[str]:
    stages = workflow.get("stages") or {}
    entry = workflow.get("entry")
    seen: set[str] = set()
    stack = [entry] if entry else []
    while stack:
        sid = stack.pop()
        if not sid or sid in seen or sid not in stages:
            continue
        seen.add(sid)
        stack.extend(list((stages[sid] or {}).get("successors") or []))
    return seen


def declared_set(workflow: dict[str, Any]) -> set[str]:
    return {str(m) for m in (workflow.get("declared_mechanisms") or []) if m}


def reachable_mechanism_ids(workflow: dict[str, Any]) -> set[str]:
    stages = workflow.get("stages") or {}
    out: set[str] = set()
    for sid in reachable_stage_ids(workflow):
        mech = (stages.get(sid) or {}).get("mechanism_id")
        if mech:
            out.add(str(mech))
    return out


def incidence_cells(workflows: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    cells = []
    for aid, wf in sorted(workflows.items()):
        declared = declared_set(wf)
        for mech in sorted(TOKENS):
            cells.append(
                {
                    "artifact_id": aid,
                    "mechanism_id": mech,
                    "present": mech in declared,
                    "extraction_rule": EXTRACTION_RULE,
                    "reachable": mech in reachable_mechanism_ids(wf),
                }
            )
    return cells


def signal_a_matrix(
    fusion: dict[str, Any], sources: list[dict[str, Any]]
) -> dict[str, Any]:
    required: set[str] = set()
    per_source = []
    for src in sources:
        sset = declared_set(src)
        required |= sset
        per_source.append({"source_id": src["id"], "declared": sorted(sset)})
    have = declared_set(fusion)
    missing = sorted(required - have)
    return {
        "signal": "A-incidence-matrix-superset",
        "required_union": sorted(required),
        "fusion_declared": sorted(have),
        "missing": missing,
        "is_superset": required <= have,
        "pass": not missing,
        "per_source": per_source,
        "method": "set-difference over definition-derived incidence cells",
    }


def exercise(workflow: dict[str, Any], mechanism_id: str) -> dict[str, Any]:
    """Run the seed case through reachable stages; succeed only if the
    distinctive token for mechanism_id is produced by a reachable handler."""
    token = TOKENS[mechanism_id]
    case = dict(SEED_CASES.get(mechanism_id) or {})
    stages = workflow.get("stages") or {}
    reached_mechs: list[str] = []
    for sid in _bfs_order(workflow):
        mech = (stages.get(sid) or {}).get("mechanism_id")
        if not mech:
            continue
        handler = HANDLERS.get(str(mech))
        if handler is None:
            continue
        case = handler(case)
        reached_mechs.append(str(mech))
    marks = list(case.get("marks") or [])
    return {
        "workflow_id": workflow.get("id"),
        "mechanism_id": mechanism_id,
        "reached": mechanism_id in reached_mechs,
        "token": token,
        "token_present": token in marks,
        "marks": marks,
        "reachable_mechanisms": sorted(set(reached_mechs)),
        "pass": token in marks and mechanism_id in reached_mechs,
    }


def _bfs_order(workflow: dict[str, Any]) -> list[str]:
    stages = workflow.get("stages") or {}
    entry = workflow.get("entry")
    out: list[str] = []
    seen: set[str] = set()
    queue = [entry] if entry else []
    while queue:
        sid = queue.pop(0)
        if not sid or sid in seen or sid not in stages:
            continue
        seen.add(sid)
        out.append(sid)
        queue.extend(list((stages[sid] or {}).get("successors") or []))
    return out


def signal_b_behaviour(
    fusion: dict[str, Any], sources: list[dict[str, Any]]
) -> dict[str, Any]:
    traces = []
    missing: list[str] = []
    required: set[str] = set()
    for src in sources:
        for mech in sorted(reachable_mechanism_ids(src)):
            required.add(mech)
            src_run = exercise(src, mech)
            fus_run = exercise(fusion, mech)
            ok = bool(src_run["pass"] and fus_run["pass"])
            row = {
                "source_id": src["id"],
                "mechanism_id": mech,
                "source_token_present": src_run["token_present"],
                "fusion_token_present": fus_run["token_present"],
                "source_reached": src_run["reached"],
                "fusion_reached": fus_run["reached"],
                "pass": ok,
            }
            traces.append(row)
            if src_run["pass"] and not fus_run["pass"] and mech not in missing:
                missing.append(mech)
    return {
        "signal": "B-behavioural-reachability",
        "required_from_sources": sorted(required),
        "missing": missing,
        "pass": not missing,
        "traces": traces,
        "method": "exercise each source-reachable mechanism against the fused pipeline; token must appear",
    }


def _divergence(a_missing: list[str], b_missing: list[str]) -> dict[str, Any]:
    a_set, b_set = set(a_missing), set(b_missing)
    only_a = sorted(a_set - b_set)
    only_b = sorted(b_set - a_set)
    present = bool(only_a or only_b)
    return {
        "present": present,
        "signal_a_missing": list(a_missing),
        "signal_b_missing": list(b_missing),
        "only_in_matrix": only_a,
        "only_in_behaviour": only_b,
        "note": (
            "Divergence is itself a finding: a mechanism id can be present in "
            "the incidence record while the behaviour it names is not reachable, "
            "or reachable while omitted from the record."
            if present
            else "Signals agree on the missing set."
        ),
    }


def detect_fusion(
    fusion: dict[str, Any], sources: list[dict[str, Any]], *, spec: dict[str, Any] | None = None
) -> dict[str, Any]:
    a = signal_a_matrix(fusion, sources)
    b = signal_b_behaviour(fusion, sources)
    div = _divergence(a["missing"], b["missing"])
    lost = sorted(set(a["missing"]) | set(b["missing"]))
    failed = (not a["pass"]) or (not b["pass"]) or div["present"]
    may = not failed
    return {
        "fusion_id": fusion.get("id"),
        "source_ids": [s["id"] for s in sources],
        "kind": (spec or {}).get("kind"),
        "named_failure_class": NAMED_FAILURE,
        "failure_class_id": FAILURE_CLASS_ID,
        "signal_a": a,
        "signal_b": b,
        "divergence": div,
        "lost_capabilities": lost,
        "detector_fired": failed,
        "severity": SEVERITY_P1 if failed else None,
        "may_proceed_to_certification": may,
        "reason": (
            None
            if may
            else (
                f"{SEVERITY_P1}: {NAMED_FAILURE}: lost={lost} divergence={div['present']}"
            )
        ),
    }


def attempt_certify(verdict: dict[str, Any]) -> dict[str, Any]:
    """P1 gate: a fusion failing this detector does not receive a certification record."""
    if verdict.get("may_proceed_to_certification"):
        return {
            "status": "ADMITTED",
            "fusion_id": verdict.get("fusion_id"),
            "certification_record": {
                "fusion_id": verdict.get("fusion_id"),
                "capability_loss_gate": "PASS",
            },
        }
    return {
        "status": "REFUSED",
        "fusion_id": verdict.get("fusion_id"),
        "reason": verdict.get("reason") or f"{SEVERITY_P1}: {NAMED_FAILURE}",
        "severity": SEVERITY_P1,
        "certification_record": None,
        "named_failure_class": NAMED_FAILURE,
    }


def scan_corpus(fusion_specs: list[dict[str, Any]]) -> dict[str, Any]:
    workflows = all_workflows()
    verdicts = []
    for spec in fusion_specs:
        fusion = spec["workflow"]
        sources = [workflows[sid] for sid in spec["source_ids"]]
        verdicts.append(detect_fusion(fusion, sources, spec=spec))
    cells = incidence_cells(workflows)
    refused = [
        attempt_certify(v)
        for v in verdicts
        if not v["may_proceed_to_certification"]
    ]
    admitted = [
        attempt_certify(v) for v in verdicts if v["may_proceed_to_certification"]
    ]
    return {
        "incidence_matrix": {
            "mechanism_ids": sorted(TOKENS),
            "artifact_ids": sorted(workflows),
            "extraction_rule": EXTRACTION_RULE,
            "cells": cells,
        },
        "verdicts": verdicts,
        "certification_gate": {
            "rule": (
                "capability loss is P1: a fusion failing this detector may not "
                "proceed to certification; attempt_certify returns REFUSED "
                "and emits no certification record"
            ),
            "admitted": admitted,
            "refused": refused,
        },
    }
