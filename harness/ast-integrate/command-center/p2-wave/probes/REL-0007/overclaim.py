"""Receipt honesty: NOT-CHECKED omitted, payload-dir zeros, and blind detectors fail."""
from __future__ import annotations

from typing import Any

from surfaces import REQUIRED_IDS


def payload(doc: dict[str, Any]) -> dict[str, Any]:
    """Domain fields live in report when the receipt follows receipt_core."""
    report = doc.get("report")
    if isinstance(report, dict) and (
        "enumerated" in report or report.get("kind") == "release-gate-receipt"
    ):
        return report
    return doc


def check_receipt(doc: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-an-object"
    body = payload(doc)
    enumerated = body.get("enumerated")
    if not isinstance(enumerated, list) or not enumerated:
        return False, "enumerated-missing"
    seen = []
    for i, row in enumerate(enumerated):
        if not isinstance(row, dict):
            return False, f"enumerated[{i}]-not-object"
        sid = str(row.get("id") or "")
        status = str(row.get("status") or "")
        query = str(row.get("query") or "")
        if not sid:
            return False, f"enumerated[{i}]-empty-id"
        if status not in {"CHECKED", "NOT-CHECKED"}:
            return False, f"enumerated[{i}]-bad-status:{status}"
        if len(query) < 4:
            return False, f"enumerated[{i}]-empty-query"
        if status == "NOT-CHECKED" and len(str(row.get("reason") or "")) < 12:
            return False, f"enumerated[{i}]-NOT-CHECKED-without-reason"
        seen.append(sid)
    missing = [s for s in REQUIRED_IDS if s not in seen]
    if missing:
        return False, f"omitted-surfaces:{missing}"

    nc = body.get("not_checked")
    if not isinstance(nc, list):
        return False, "not_checked-missing"
    nc_ids = {str(r.get("id")) for r in nc if isinstance(r, dict)}
    enum_nc = {str(r.get("id")) for r in enumerated if r.get("status") == "NOT-CHECKED"}
    if enum_nc - nc_ids:
        return False, f"not_checked-incomplete:{sorted(enum_nc - nc_ids)}"

    if body.get("payload_used_as_orphan_verdict") is True:
        return False, "payload-dir-used-as-orphan-verdict"

    det = body.get("detector_control") or {}
    if not isinstance(det, dict) or not det.get("found_before_zero"):
        if body.get("zero_orphans_on_checked_surfaces") is True:
            return False, "zero-without-detector-control"
        gate = str(doc.get("gate_verdict") or body.get("gate_verdict") or "")
        if gate in {"PASS", "GO"}:
            return False, "pass-without-detector-control"

    if "machine_wide_zero_orphans" in body or "machine_wide_zero_orphans" in doc:
        return False, "machine-wide-zero-covers-NOT-CHECKED"

    tests = doc.get("tests") or body.get("tests") or []
    ids = {t.get("id") for t in tests if isinstance(t, dict)}
    for need in (
        "plant-orphan-hook",
        "detector-control",
        "clean-uninstall-zero",
        "unqueryable-not-checked",
    ):
        if need not in ids:
            return False, f"required-test-missing:{need}"
        row = next(t for t in tests if t.get("id") == need)
        if row.get("result") != "PASS":
            return False, f"required-test-not-pass:{need}"

    sentinel = str(doc.get("sentinel") or "")
    if "SUCCESS:REL-0007" not in sentinel:
        return False, "sentinel-absent"
    return True, "ok"


def mutant_omit_not_checked(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json_clone(doc)
    body = payload(clone)
    body["enumerated"] = [
        r for r in (body.get("enumerated") or []) if r.get("status") != "NOT-CHECKED"
    ]
    body["not_checked"] = []
    return clone


def mutant_zero_without_detector(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json_clone(doc)
    body = payload(clone)
    body["detector_control"] = {"found_before_zero": False}
    body["zero_orphans_on_checked_surfaces"] = True
    body["gate_verdict"] = "PASS"
    return clone


def mutant_payload_as_verdict(doc: dict[str, Any]) -> dict[str, Any]:
    clone = json_clone(doc)
    body = payload(clone)
    body["payload_used_as_orphan_verdict"] = True
    body["zero_orphans_on_checked_surfaces"] = True
    return clone


def json_clone(doc: dict[str, Any]) -> dict[str, Any]:
    import json

    return json.loads(json.dumps(doc))
