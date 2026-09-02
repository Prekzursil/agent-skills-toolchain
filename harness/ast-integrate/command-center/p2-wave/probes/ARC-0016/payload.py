"""Locate the ARC-0016 domain payload on a receipt or a flat dossier."""
from __future__ import annotations

from typing import Any


def domain(doc: dict[str, Any]) -> dict[str, Any]:
    """Return the object that carries claims/scenario/blast_radius/evidence anchors.

    architecture-review receipts pin those fields under ``report`` because
    receipt_core sets additionalProperties false at the top level. Older flat
    REFUTATION.json files keep them at the root. Probes accept both.
    """
    if not isinstance(doc, dict):
        return {}
    rep = doc.get("report")
    if isinstance(rep, dict) and isinstance(rep.get("claims"), list):
        return rep
    return doc


def reviewer_scope_ok(doc: dict[str, Any]) -> bool:
    rev = doc.get("reviewer") if isinstance(doc.get("reviewer"), dict) else {}
    if rev.get("independent") is not True:
        return False
    if rev.get("scope_not_agreement") is True:
        return True
    body = domain(doc)
    return body.get("scope_not_agreement") is True
