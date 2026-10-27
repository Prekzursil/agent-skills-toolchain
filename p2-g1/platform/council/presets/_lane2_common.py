"""Shared scaffolding for lane-2 council presets (design indices 17-32).

The JSON files in this directory are the SOURCE OF TRUTH and are hand-editable.
This module exists only so the 17 instances share one spelling of the
boilerplate that every preset needs (audit posture, injection defence, the
receipt schema path), and so the seat-count discrepancies against the design
cards are MEASURED rather than asserted.

Nothing here is required at run time to consume a preset: each emitted file is
plain JSON that validates standalone against
``platform/schema/councilspec.schema.json``.
"""

from __future__ import annotations

from typing import Any, Dict, List

SCHEMA_VERSION = "1.0.0"
RECEIPT_SCHEMA = "platform/schema/receipt.schema.json"

# Every design card's outcome vocabulary uses SHOUTY names that are not the
# schema's `outcomes.allowed` enum. This is the one mapping used by all 17 files;
# it is documented per preset in metadata.notes so an editor can see the lineage.
OUTCOME_MAP = {
    "CONSENSUS": "decision",
    "MAJORITY_WITH_DISSENT": "dissent",
    "IRREDUCIBLE_DISAGREEMENT": "irreducible_disagreement",
    "INSUFFICIENT_EVIDENCE": "no_decision",
    "CONDITIONAL_DECISION": "conditional_decision",
    "DEFER": "no_decision",
    "PROOF_OF_IMPOSSIBILITY": "proof_of_impossibility",
    "AUTHORISE": "decision",
    "DENY": "no_decision",
    "PROCEED": "decision",
    "MITIGATED": "conditional_decision",
    # Not a card token: appended by a preset whose consensus.minority_report is
    # "required", because SEM-009 rejects that combination unless the outcome is
    # also allowed. Kept explicit so the addition is visible in metadata.notes.
    "MINORITY_REPORT": "minority_report",
}

RISK_MAP = {"low": "low", "medium": "moderate", "high": "high", "critical": "critical"}


def outcomes(
    card_names: List[str], conditional_requires: List[str] | None = None
) -> Dict[str, Any]:
    """Translate a design card's outcome list into the schema enum, order-stable."""
    seen: List[str] = []
    for name in card_names:
        mapped = OUTCOME_MAP[name]
        if mapped not in seen:
            seen.append(mapped)
    block: Dict[str, Any] = {"allowed": seen}
    if conditional_requires:
        block["conditional_decision_requires"] = conditional_requires
    return block


def audit(
    *,
    retain_days: int = 90,
    owner_approval_for: List[str] | None = None,
    forbid_irreversible: bool = True,
    calibration: bool = False,
    determinism: str = "deterministic_where_possible",
) -> Dict[str, Any]:
    """Audit posture. Redaction is DENY_BY_DEFAULT everywhere - an allowlist
    redactor leaked real values on this estate, so no preset may opt into one."""
    block: Dict[str, Any] = {
        "transcript": True,
        "replay": True,
        "resume": True,
        "determinism": determinism,
        "privacy": {
            "redact_secrets": True,
            "redaction_policy": "deny_by_default",
            "pii_policy": "redact",
            "retain_days": retain_days,
        },
        "safety": {
            "forbid_irreversible_actions": forbid_irreversible,
            "owner_approval_for": owner_approval_for or ["merge", "release"],
        },
        "persistence": {"store": "both", "checkpoint_every_round": True},
    }
    if calibration:
        block["calibration"] = {"post_run": True, "score": "brier"}
    return block


def injection_defense() -> Dict[str, Any]:
    """Fetched artefacts are untrusted DATA, never instructions (AGENTS.md 9)."""
    return {
        "treat_artifacts_as_data": True,
        "strip_instructions_from_participant_output": True,
        "quarantine_untrusted_sources": True,
    }


def notes(
    *,
    card: str,
    seats_declared: int,
    roles_line: str,
    preset_label_rationale: str,
    dials: Dict[str, str],
    outcome_lineage: List[str],
    extra: str = "",
) -> str:
    """Build the in-file documentation block.

    JSON has no comments and this schema is closed at every level, so
    `metadata.notes` is the only place a per-field editing guide can live inside
    the instance itself. Each dial names its JSON pointer.
    """
    lines = [
        f"DESIGN LINEAGE: {card} in 12-COUNCIL-PROTOCOLS-AND-PRESETS.md "
        f"(seats: {seats_declared}; roles: {roles_line}).",
        f"PRESET LABEL: {preset_label_rationale}",
        "OUTCOME MAPPING (card vocabulary -> schema outcomes.allowed): "
        + ", ".join(f"{k}->{OUTCOME_MAP[k]}" for k in outcome_lineage)
        + ".",
        "EDITABLE DIALS (pointer -> what it changes):",
    ]
    lines += [f"  - {ptr} : {why}" for ptr, why in dials.items()]
    if extra:
        lines.append(extra)
    lines.append(
        "EVERY field in this file is a dial; the ones above are the ones the owner is "
        "expected to change first. See README.md in this directory for the full table."
    )
    return "\n".join(lines)
