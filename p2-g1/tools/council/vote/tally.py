"""Motion tally with explicit abstention policies. IMP-0302."""
from __future__ import annotations

from typing import Any, Sequence


def tally_motion(
    ballots: Sequence[str],
    *,
    threshold_id: str,
    abstention_policy_id: str,
    quorum_required: int,
    seated: int,
    motion_id: str = "",
) -> dict[str, Any]:
    yes = sum(1 for b in ballots if b == "yes")
    no = sum(1 for b in ballots if b == "no")
    abstain = sum(1 for b in ballots if b == "abstain")
    present = yes + no + abstain
    if abstention_policy_id == "exclude_from_denominator":
        denom_policy = yes + no
        effective_no = no
    elif abstention_policy_id == "count_as_no":
        denom_policy = yes + no + abstain
        effective_no = no + abstain
    else:
        denom_policy = yes + no + abstain
        effective_no = no
    if present < quorum_required:
        outcome = "NO_QUORUM"
        denominator = denom_policy
    elif abstention_policy_id == "park_on_any_abstention" and abstain > 0:
        outcome = "PARKED"
        denominator = present
    else:
        if abstention_policy_id == "exclude_from_denominator":
            denominator = yes + no
            yes_count = yes
        elif abstention_policy_id == "count_as_no":
            denominator = yes + no + abstain
            yes_count = yes
        else:  # include_in_denominator
            denominator = yes + no + abstain
            yes_count = yes
        if denominator == 0:
            outcome = "REJECT"
        else:
            ratio = yes_count / denominator
            if threshold_id == "majority":
                adopt = ratio > 0.5
            elif threshold_id == "supermajority":
                adopt = ratio >= (2 / 3)
            elif threshold_id == "unanimity":
                adopt = ratio == 1
            else:
                adopt = False
            outcome = "ADOPT" if adopt else "REJECT"
    ratio = None
    if denominator:
        ratio = f"{yes}/{denominator}"
    return {
        "motion_id": motion_id,
        "outcome": outcome,
        "yes": yes,
        "no": no,
        "abstain": abstain,
        "present": present,
        "denominator": denominator,
        "threshold_id": threshold_id,
        "abstention_policy_id": abstention_policy_id,
        "policy_recorded": True,
        "quorum_required": quorum_required,
        "seated": seated,
        "effective_no": effective_no,
        "ratio": ratio,
    }


def policy_without_id(art: dict[str, Any]) -> dict[str, Any]:
    out = dict(art)
    out.pop("abstention_policy_id", None)
    out["policy_recorded"] = False
    return out


def validate_decision_artifact(art: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(art, dict):
        raise ValueError("decision artifact is not an object")
    if not art.get("abstention_policy_id"):
        raise ValueError("abstention_policy_id is required")
    if not art.get("threshold_id"):
        raise ValueError("threshold_id is required")
    if not art.get("policy_recorded"):
        raise ValueError("policy_recorded is required")
    return art
