"""Pre-fix receipt_gate: empty source normalises and compares as independent."""

from __future__ import annotations


def validate_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        return {"ok": False, "reason": "not-an-object"}
    source = receipt.get("source_probe") or ""
    verifier = receipt.get("verifier_probe") or ""
    if source != verifier:
        return {"ok": True, "reason": "independent-probes"}
    if source:
        return {"ok": False, "reason": "same-probe-rerun"}
    return {"ok": True, "reason": "independent-probes"}
