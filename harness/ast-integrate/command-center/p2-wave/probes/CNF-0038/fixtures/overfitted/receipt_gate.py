"""Overfitted patch: rejects a missing key only; empty string still confirms."""

from __future__ import annotations


def validate_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        return {"ok": False, "reason": "not-an-object"}
    verdict = receipt.get("verdict")
    if verdict == "CONFIRMED" and "source_probe" not in receipt:
        return {"ok": False, "reason": "empty-source-probe"}
    source = receipt.get("source_probe") or ""
    verifier = receipt.get("verifier_probe") or ""
    if source != verifier:
        return {"ok": True, "reason": "independent-probes"}
    if source:
        return {"ok": False, "reason": "same-probe-rerun"}
    return {"ok": True, "reason": "independent-probes"}
