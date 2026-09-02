"""Evaluate capability invocations against the A7 gate model (full vs minimum)."""
from __future__ import annotations

import copy
from typing import Any

from gate_model import load_model

FORBIDDEN = ("secret", "api key", "credential")

P0_PLUGIN = "CTL-P0-UNSIGNED-PLUGIN-FAIL-CLOSED"
P0_CANARY = "CTL-P0-CANARY-SECRET-BUNDLE-SCAN"
P0_INJECT = "CTL-P0-UNTRUSTED-SURFACE-INJECTION-ISOLATION"
A7_TEXT = "CTL-A7-PAYLOAD-TEXT-MATCH"
A7_SIGN = "CTL-A7-SIGN-EVERY-ARTIFACT"
A7_APPROVE = "CTL-A7-PER-CALL-WRITE-APPROVAL"


def _deny(control_id: str, reason: str) -> dict[str, Any]:
    return {"allow": False, "control_id": control_id, "reason": reason}


def _allow() -> dict[str, Any]:
    return {"allow": True, "control_id": None, "reason": "allow"}


def _text_hit(payload: str) -> bool:
    blob = (payload or "").lower()
    return any(token in blob for token in FORBIDDEN)


def _estate_local(inv: dict[str, Any]) -> bool:
    return (
        inv.get("session") == "owner-estate-local"
        and inv.get("authorship") == "estate-trusted"
    )


def p0_preflight(inv: dict[str, Any]) -> dict[str, Any] | None:
    """Non-negotiable P0 checks. Same in full A7 and the surviving minimum."""
    if inv.get("surface") == "plugin-install" and not inv.get("signed"):
        return _deny(P0_PLUGIN, "unsigned plugin install is fail-closed")
    if inv.get("contains_canary_secret") and inv.get("verb") in {
        "Write",
        "BundleWrite",
    }:
        return _deny(P0_CANARY, "planted canary secret in bundle")
    if inv.get("authorship") == "untrusted" and inv.get("discourse_role") == "USE":
        return _deny(P0_INJECT, "untrusted surface USE of injected instruction")
    return None


def minimum_model(full: dict[str, Any] | None = None) -> dict[str, Any]:
    model = copy.deepcopy(full if full is not None else load_model())
    choke = dict(model.get("choke_point") or {})
    choke["security_first_sets_estate_local_owner_session_exempt"] = True
    choke["require_owner_approval_for"] = []
    model["choke_point"] = choke
    inj = dict(model.get("injection_boundary") or {})
    inj["mode"] = "use-versus-mention"
    inj["match_use_versus_mention"] = True
    model["injection_boundary"] = inj
    sign = dict(model.get("artifact_signing") or {})
    sign["required_before_write"] = False
    sign["applies_to_estate_local_receipts"] = False
    model["artifact_signing"] = sign
    model["mode"] = "minimum"
    return model


def evaluate(inv: dict[str, Any], *, mode: str = "full") -> dict[str, Any]:
    hit = p0_preflight(inv)
    if hit is not None:
        return hit
    full = load_model()
    model = full if mode == "full" else minimum_model(full)
    choke = model.get("choke_point") or {}
    inj = model.get("injection_boundary") or {}
    sign = model.get("artifact_signing") or {}
    verb = str(inv.get("verb") or "")
    estate = _estate_local(inv)
    exempt = bool(choke.get("security_first_sets_estate_local_owner_session_exempt"))

    required = [str(x) for x in (choke.get("require_owner_approval_for") or [])]
    if verb in required and not inv.get("owner_approved"):
        if not (estate and exempt):
            return _deny(
                A7_APPROVE,
                "per-call owner_approval missing at the single choke point",
            )

    if (
        verb == "Write"
        and sign.get("required_before_write")
        and sign.get("applies_to_estate_local_receipts")
        and not inv.get("signed")
        and not (estate and exempt)
    ):
        return _deny(A7_SIGN, "estate-local receipt unsigned")

    text_match = str(inj.get("mode") or "") == "payload-text-match"
    if text_match and _text_hit(str(inv.get("payload") or "")):
        if verb in {"Read", "Grep", "Write", "Bash"}:
            return _deny(A7_TEXT, "payload TEXT mention fired; tool VERB ignored")
    return _allow()
