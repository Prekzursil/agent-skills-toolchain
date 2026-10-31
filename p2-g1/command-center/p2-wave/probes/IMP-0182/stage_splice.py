"""IMP-0182: stage-splice fusion - graft a donor stage onto a host workflow.

The contract gate runs BEFORE any fusion object exists: a donor stage whose
declared inputs are not produced by the host's stages is refused with
fusion=None. The emit-first mutant is shipped alongside as the recorded
counterexample that keeps the fusion-is-None detector honest.
"""
from __future__ import annotations


def _host_outputs(host: dict) -> set:
    out = set()
    for st in host.get("stages") or []:
        out |= set(st.get("outputs") or [])
    return out


def splice(host: dict, donor_stage: dict) -> dict:
    trace = []
    trace.append("contract-check")
    if not set(donor_stage.get("inputs") or []) <= _host_outputs(host):
        trace.append("refuse")
        return {"status": "refused", "reason": "contract-mismatch",
                "fusion": None, "fusion_id": None, "trace": trace}
    fused = {
        "id": f"{host['id']}++{donor_stage.get('donor_id', 'wf.donor')}::stage-splice",
        "stages": list(host.get("stages") or []) + [donor_stage],
        "edges": list(host.get("edges") or []),
    }
    fused["edges"].append([host["stages"][-1]["name"], donor_stage["name"]])
    trace.append("emit")
    return {"status": "emitted", "reason": None, "fusion": fused,
            "fusion_id": fused["id"], "trace": trace}


def splice_emit_first_mutant(host: dict, donor_stage: dict) -> dict:
    """The broken operator: emits first, checks later, keeps the fusion object
    even on mismatch. Recorded so the fusion-is-None detector stays live."""
    trace = ["emit"]
    fused = {"id": "mutant-emitted-first", "stages": list(host["stages"]) + [donor_stage],
             "edges": list(host.get("edges") or [])}
    trace.append("contract-check")
    if not set(donor_stage.get("inputs") or []) <= _host_outputs(host):
        trace.append("refuse")
        return {"status": "refused", "reason": "contract-mismatch",
                "fusion": fused, "fusion_id": fused["id"], "trace": trace}
    trace.append("emit")
    return {"status": "emitted", "reason": None, "fusion": fused,
            "fusion_id": fused["id"], "trace": trace}


def host_workflow() -> dict:
    return {
        "id": "wf.host.extract-v1",
        "stages": [
            {"name": "fetch-receipts", "inputs": [], "outputs": ["receipts"]},
            {"name": "validate-receipts", "inputs": ["receipts"], "outputs": ["validated"]},
        ],
        "edges": [["fetch-receipts", "validate-receipts"]],
    }


def donor_matching() -> dict:
    return {"name": "emit-index", "donor_id": "wf.donor.extract-v2",
            "inputs": ["validated"], "outputs": ["index"]}


def donor_mismatch() -> dict:
    return {"name": "emit-index", "donor_id": "wf.donor.extract-v2",
            "inputs": ["schema-latest"], "outputs": ["index"]}
