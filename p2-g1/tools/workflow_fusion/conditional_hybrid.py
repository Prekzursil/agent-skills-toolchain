"""Emit a conditional-hybrid fusion with an explicit default (IMP-0186)."""
from __future__ import annotations

from typing import Any

from .reachability import dual_reachability
from .typed_predicate import eval_pred, typed_universe


class FusionRefused(ValueError):
    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code


def analyze_conditional_hybrid(spec: dict[str, Any]):
    return dual_reachability(spec)


def route(spec_or_fusion: dict[str, Any], env: dict[str, Any]) -> str | None:
    for br in spec_or_fusion.get("branches") or []:
        pred = br.get("predicate")
        if pred is None:
            continue
        if eval_pred(pred, env):
            return str(br.get("source_id") or br.get("id"))
    return spec_or_fusion.get("default_source_id") or spec_or_fusion.get("default_branch_id")


def emit_conditional_hybrid(spec: dict[str, Any]) -> dict[str, Any]:
    proof = dual_reachability(spec)
    if proof.unreachable:
        raise FusionRefused(
            "fusion.conditional_hybrid.unreachable-branch",
            f"unreachable={list(proof.unreachable)}",
        )
    universe = typed_universe(spec.get("input_type") or {})
    branches_out = []
    default_id = None
    default_src = None
    for br in spec.get("branches") or []:
        bid = str(br.get("id"))
        witness = None
        for env in universe:
            if eval_pred(br.get("predicate") or {}, env):
                # first-match owner?
                owner = None
                for cand in spec.get("branches") or []:
                    if eval_pred(cand.get("predicate") or {}, env):
                        owner = str(cand.get("id"))
                        break
                if owner == bid:
                    witness = env
                    break
        if br.get("is_default"):
            default_id = bid
            default_src = br.get("source_id")
        branches_out.append(
            {
                "id": bid,
                "source_id": br.get("source_id"),
                "is_default": bool(br.get("is_default")),
                "predicate": br.get("predicate"),
                "reachable": witness is not None,
                "witness": witness,
            }
        )
    return {
        "id": spec.get("id"),
        "strategy": "conditional-hybrid",
        "input_type": spec.get("input_type"),
        "sources": spec.get("sources"),
        "branches": branches_out,
        "default_branch_id": default_id or "br.default",
        "default_source_id": default_src,
        "default_explicit": default_id is not None,
        "reachability_proof": {
            "universe_size": proof.universe_size,
            "cfg_reachable": list(proof.cfg_reachable),
            "bitmask_reachable": list(proof.bitmask_reachable),
            "unreachable": list(proof.unreachable),
            "unrouted_count": proof.unrouted_count,
            "agreement": proof.agreement,
        },
        "fused_workflow": {
            "id": spec.get("id"),
            "strategy": "conditional-hybrid",
            "sources": list((spec.get("sources") or {}).keys()),
            "default_branch_id": default_id or "br.default",
        },
        "lineage": {
            "operator": "conditional-hybrid",
            "sources": list((spec.get("sources") or {}).keys()),
            "unit_id": "WFA-0104",
        },
    }
