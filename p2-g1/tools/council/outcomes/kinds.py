"""Closed council outcome kinds. Binary FAIL is not a kind."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

KIND_NO_DECISION = "NO-DECISION"
KIND_CONDITIONAL = "CONDITIONAL"
KIND_PROOF_OF_IMPOSSIBILITY = "PROOF-OF-IMPOSSIBILITY"
KIND_DECISION = "DECISION"

REQUIRED: dict[str, tuple[str, ...]] = {
    KIND_NO_DECISION: (
        "outcome_id",
        "kind",
        "produced_at_round",
        "participant_ids",
        "reason",
        "unresolved_questions",
        "considered_options",
        "blocking_objections",
        "stop_rule_id",
    ),
    KIND_CONDITIONAL: (
        "outcome_id",
        "kind",
        "produced_at_round",
        "participant_ids",
        "decision_text",
        "conditions",
        "if_unmet",
        "evidence_ids",
    ),
    KIND_PROOF_OF_IMPOSSIBILITY: (
        "outcome_id",
        "kind",
        "produced_at_round",
        "participant_ids",
        "claim_shown_impossible",
        "proof_sketch",
        "contradiction",
        "assumptions",
        "scope",
        "not_equivalent_to_fail",
    ),
}


class OutcomeValidationError(ValueError):
    pass


class CollapseForbidden(ValueError):
    pass


def required_fields_for(kind: str) -> tuple[str, ...]:
    if kind not in REQUIRED:
        raise OutcomeValidationError(f"unknown kind {kind}")
    return REQUIRED[kind]


def parse_outcome(raw: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise OutcomeValidationError("outcome is not an object")
    kind = str(raw.get("kind") or "")
    if kind in {"FAIL", "PASS", "SUCCESS", "FAILED"}:
        raise CollapseForbidden(f"binary alias {kind} is not a kind")
    if kind not in REQUIRED:
        raise OutcomeValidationError(f"unknown kind {kind}")
    if kind == KIND_PROOF_OF_IMPOSSIBILITY and raw.get("not_equivalent_to_fail") is False:
        raise CollapseForbidden("proof mapped to FAIL")
    if kind == KIND_CONDITIONAL and str(raw.get("if_unmet") or "") == "apply-anyway":
        raise OutcomeValidationError("conditional if_unmet=apply-anyway collapses into a decision")
    out = deepcopy(raw)
    for field in REQUIRED[kind]:
        if field not in out:
            raise OutcomeValidationError(f"missing {field}")
        val = out[field]
        if isinstance(val, str) and not val.strip():
            raise OutcomeValidationError(f"empty {field}")
        if isinstance(val, list) and not val:
            raise OutcomeValidationError(f"empty {field}")
    return out
