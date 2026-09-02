"""Already-satisfied snapshot: same bytes as post-fix, used as a green-at-parent control."""

from __future__ import annotations


def validate_receipt(receipt: dict) -> dict:
    if not isinstance(receipt, dict):
        return {"ok": False, "reason": "not-an-object"}
    verdict = receipt.get("verdict")
    if verdict == "CONFIRMED":
        if "source_probe" not in receipt or receipt.get("source_probe") in (None, ""):
            return {"ok": False, "reason": "empty-source-probe"}
    source = receipt.get("source_probe") or ""
    verifier = receipt.get("verifier_probe") or ""
    if source != verifier:
        return {"ok": True, "reason": "independent-probes"}
    return {"ok": False, "reason": "same-probe-rerun"}
