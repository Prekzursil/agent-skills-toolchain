"""CNL-0111 normative boards: ethics/legal review (C15) and risk committee (C16).

These presets EXTEND the catalogued C15/C16 4-tuples reconstructed by CNL-0102
(original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent). The 4-tuple is
unchanged so this unit does not fork a name-only twin. What this unit adds,
and what the 4-tuple metric cannot see, is:

  * evidence standards (cited-instrument fail-closed vs named-residual envelope)
  * outcome type sets (permission vs exposure disposition)
  * the composition rule when the boards disagree

A preset whose only differential is its name is a mechanism-duplicate and
must be merged. C15 vs C16 already differ on protocols, roles, vote and stop.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# 4-tuple locked to CNL-0102 named_family_presets C15 / C16.
C15_PROTOCOLS = ["P14", "P19", "P56"]
C15_ROLES = ["Judge", "Reviewer", "Skeptic", "Clerk"]
C15_VOTE = "unanimity"
C15_STOP = "may_we == true OR minority_report_filed == true"

C16_PROTOCOLS = ["P39", "P40", "P43"]
C16_ROLES = ["Forecaster", "Skeptic", "Owner", "Chair"]
C16_VOTE = "supermajority"
C16_STOP = "exposure_accepted == true AND residual_risk_named == true"

LEGAL_OUTCOMES = (
    "PERMITTED",
    "PERMITTED-CONDITIONAL",
    "PROHIBITED",
    "IRREDUCIBLE-DISAGREEMENT",
)
RISK_OUTCOMES = (
    "ACCEPT",
    "MITIGATE",
    "TRANSFER",
    "AVOID",
    "PARK-UNQUANTIFIED",
)

LEGAL_EVIDENCE = {
    "question": "may_we",
    "bar": "cited-instrument-or-fail-closed",
    "accepts": [
        "statute",
        "licence-clause",
        "policy",
        "prohibited-use",
        "rights-record",
    ],
    "rejects": [
        "feels-legal",
        "owner-wants-it",
        "risk-committee-accepts-exposure",
        "unnamed-custom",
    ],
    "absence_of_permit": "PROHIBITED",
}

RISK_EVIDENCE = {
    "question": "how_exposed",
    "bar": "named-residual-plus-scenario-envelope",
    "accepts": [
        "expected-loss-envelope",
        "key-assumption-check",
        "premortem-failure-mode",
        "quality-of-information",
    ],
    "rejects": [
        "feels-acceptable",
        "legal-board-said-yes",
        "unnamed-residual",
        "owner-wants-it",
    ],
    "absence_of_quantification": "PARK-UNQUANTIFIED",
}


def _binding(protocols: list[str], roles: list[str], vote: str, stop: str) -> dict:
    return {
        "protocols": list(protocols),
        "roles": list(roles),
        "voting_method": vote,
        "stopping_expression": stop,
    }


def ethics_legal_preset() -> dict[str, Any]:
    return {
        "id": "C15",
        "name": "ethics-legal-review",
        "supersedes_or_extends": ["C15"],
        "reconstruction_basis": "CNL-0111 ethics/legal; 4-tuple locked to CNL-0102 C15",
        "question": "may_we",
        "bound_protocols": list(C15_PROTOCOLS),
        "roles": list(C15_ROLES),
        "voting_method": C15_VOTE,
        "stopping_expression": C15_STOP,
        "base_spec": "CouncilSpec/v2",
        "default_binding": _binding(C15_PROTOCOLS, C15_ROLES, C15_VOTE, C15_STOP),
        "editable_dials": ["roles", "budgets.max_rounds"],
        "non_editable_dials": ["voting_method", "stopping_expression"],
        "evidence_standard": deepcopy(LEGAL_EVIDENCE),
        "outcome_types": list(LEGAL_OUTCOMES),
        "veto_scope": "the proposed option (the act), not the whole council and not the risk committee's exposure record",
    }


def risk_committee_preset() -> dict[str, Any]:
    return {
        "id": "C16",
        "name": "risk-committee",
        "supersedes_or_extends": ["C16"],
        "reconstruction_basis": "CNL-0111 risk committee; 4-tuple locked to CNL-0102 C16",
        "question": "how_exposed",
        "bound_protocols": list(C16_PROTOCOLS),
        "roles": list(C16_ROLES),
        "voting_method": C16_VOTE,
        "stopping_expression": C16_STOP,
        "base_spec": "CouncilSpec/v2",
        "default_binding": _binding(C16_PROTOCOLS, C16_ROLES, C16_VOTE, C16_STOP),
        "editable_dials": ["roles", "budgets.max_rounds"],
        "non_editable_dials": ["voting_method", "stopping_expression"],
        "evidence_standard": deepcopy(RISK_EVIDENCE),
        "outcome_types": list(RISK_OUTCOMES),
        "veto_scope": "authorization of the act given residual exposure; cannot license a legally prohibited option",
    }


def family_presets() -> list[dict[str, Any]]:
    return [ethics_legal_preset(), risk_committee_preset()]


def as_signature_row(preset: dict) -> dict:
    """4-tuple view used by CNL-0102 distinctness (names excluded)."""
    return {
        "id": preset["id"],
        "name": preset["name"],
        "bound_protocols": list(preset["bound_protocols"]),
        "roles": list(preset["roles"]),
        "voting_method": preset["voting_method"],
        "stopping_expression": preset["stopping_expression"],
    }
