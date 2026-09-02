"""Composition rule: permission gate dominates action-authorization.

Legal board outcomes and risk-committee outcomes are different types.
They are not commensurable votes. Risk ACCEPT does not license a
PROHIBITED act. Legal PERMITTED does not force the owner to accept
unnamed residual.

Both boards always run so a disagreement is a recorded pair, not a skip.
"""
from __future__ import annotations

from typing import Any

PERMISSION_OK = frozenset({"PERMITTED", "PERMITTED-CONDITIONAL"})
EXPOSURE_OK = frozenset({"ACCEPT", "MITIGATE", "TRANSFER"})

NEGATIVE_VERBATIM = (
    "The check REJECTS a composer that authorizes action when the legal "
    "board outcome is PROHIBITED and the risk committee outcome is ACCEPT "
    "(risk-accept-overrides-legal-no). It is SILENT on the honest composer, "
    "which records both outcomes and sets action_authorized=false."
)


def action_authorized(legal: dict[str, Any], risk: dict[str, Any]) -> bool:
    """Honest composer. Legal PROHIBITED / hung never authorizes."""
    legal_out = str(legal.get("outcome") or "")
    risk_out = str(risk.get("outcome") or "")
    if legal_out not in PERMISSION_OK:
        return False
    if legal_out == "PERMITTED-CONDITIONAL" and not legal.get("conditions"):
        return False
    if risk_out not in EXPOSURE_OK:
        return False
    if not risk.get("residual_risk_named"):
        return False
    if risk_out == "MITIGATE" and not risk.get("mitigations"):
        return False
    if risk_out == "TRANSFER" and not risk.get("transfer_instrument"):
        return False
    return True


def compose(legal: dict[str, Any], risk: dict[str, Any]) -> dict[str, Any]:
    authorized = action_authorized(legal, risk)
    conflict = (
        str(legal.get("outcome") or "") == "PROHIBITED"
        and str(risk.get("outcome") or "") == "ACCEPT"
    )
    return {
        "legal_outcome": legal.get("outcome"),
        "risk_outcome": risk.get("outcome"),
        "action_authorized": authorized,
        "conflict_legal_no_risk_accept": conflict,
        "rule": (
            "action_authorized := (legal in {PERMITTED, PERMITTED-CONDITIONAL}) "
            "AND (risk in {ACCEPT, MITIGATE, TRANSFER} with residual named). "
            "Legal PROHIBITED or IRREDUCIBLE-DISAGREEMENT vetoes the option; "
            "the risk record is preserved and is not an override. Override "
            "path is re-scope the option and re-run both boards, not overlay "
            "risk ACCEPT on a legal NO."
        ),
        "preserved_legal": dict(legal),
        "preserved_risk": dict(risk),
    }


def mutant_risk_overrides_legal(legal: dict[str, Any], risk: dict[str, Any]) -> bool:
    """Planted-bad composer: exposure ACCEPT licenses the act."""
    if str(risk.get("outcome") or "") == "ACCEPT" and risk.get("residual_risk_named"):
        return True
    return action_authorized(legal, risk)


def check_composer(
    claimed_authorized: bool, legal: dict[str, Any], risk: dict[str, Any]
) -> str:
    """FIRE on the state the check is meant to reject; SILENT on honest."""
    honest = action_authorized(legal, risk)
    if claimed_authorized != honest:
        return "FIRE"
    return "SILENT"
