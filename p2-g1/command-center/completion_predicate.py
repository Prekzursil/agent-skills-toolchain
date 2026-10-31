#!/usr/bin/env python3
"""Twelve-condition completion predicate reducer (TST-0001 production subject).

``reduce(snap)`` walks C01..C12 in order and returns the first failure as
{verdict, failing_condition_id, reason}. Exit code is not a condition.
"""
from __future__ import annotations

import json
from typing import Any, Callable

CONDITION_IDS = tuple(f"C{i:02d}" for i in range(1, 13))
COMPLETION_STATES = frozenset({"SUCCESS", "COMPLETE", "PASS", "DELIVERED"})
PASS_REASON = "all 12 conditions satisfied"
REASONS = {
    "C01": "state is not a completion terminal (SUCCESS/COMPLETE/PASS/DELIVERED)",
    "C02": "expected artifact does not exist on disk",
    "C03": "artifact is empty or below min_bytes_threshold",
    "C04": "artifact does not parse against its schema",
    "C05": "required sentinel is absent from the artifact",
    "C06": "required evidence anchors are missing",
    "C07": "required tests did not run and pass",
    "C08": "negative controls or mutations did not fail as expected",
    "C09": "independent reviewer status is not PASS",
    "C10": "unresolved P0/P1 defect is attached",
    "C11": "output is not registered in the artifact manifest",
    "C12": "downstream consumers cannot read it",
}

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def _c01(snap: dict[str, Any]) -> bool:
    state = str((snap.get("receipt") or {}).get("state") or "").strip().upper()
    return state in COMPLETION_STATES


def _c02(snap: dict[str, Any]) -> bool:
    return bool(snap.get("artifact_exists"))


def _c03(snap: dict[str, Any]) -> bool:
    size = int(snap.get("artifact_size") or 0)
    floor = int(snap.get("min_bytes") or 0)
    return size > 0 and size >= floor


def _c04(snap: dict[str, Any]) -> bool:
    if not snap.get("artifact_exists"):
        return False
    text = snap.get("artifact_text") or ""
    try:
        doc = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    schema = snap.get("schema") or {}
    if jsonschema is None:
        return False
    try:
        validator = jsonschema.Draft7Validator(schema)
        return next(validator.iter_errors(doc), None) is None
    except Exception:
        return False


def _c05(snap: dict[str, Any]) -> bool:
    needle = str(snap.get("required_sentinel") or "")
    if not needle:
        return False
    return needle in str(snap.get("artifact_text") or "")


def _anchor(item: dict[str, Any]) -> str:
    return str(item.get("anchor") or item.get("path") or "").strip()


def _c06(snap: dict[str, Any]) -> bool:
    evidence = (snap.get("receipt") or {}).get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return False
    for item in evidence:
        if not isinstance(item, dict) or not _anchor(item):
            return False
    return True


def _c07(snap: dict[str, Any]) -> bool:
    tests = (snap.get("receipt") or {}).get("tests")
    if not isinstance(tests, list) or not tests:
        return False
    for row in tests:
        if not isinstance(row, dict):
            return False
        if str(row.get("result") or "").strip().upper() != "PASS":
            return False
    return True


def _c08(snap: dict[str, Any]) -> bool:
    controls = (snap.get("receipt") or {}).get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return False
    for row in controls:
        if not isinstance(row, dict):
            return False
        if row.get("fired_on_bad_state") is not True:
            return False
        if "silent_on_good_state" in row and row.get("silent_on_good_state") is not True:
            return False
    return True


def _c09(snap: dict[str, Any]) -> bool:
    reviewer = (snap.get("receipt") or {}).get("reviewer")
    if not isinstance(reviewer, dict):
        return False
    if str(reviewer.get("verdict") or "").strip().upper() != "PASS":
        return False
    return reviewer.get("independent") is True


def _c10(snap: dict[str, Any]) -> bool:
    defects = (snap.get("receipt") or {}).get("defects") or []
    if not isinstance(defects, list):
        return False
    for row in defects:
        if not isinstance(row, dict):
            continue
        sev = str(row.get("severity") or row.get("priority") or "").upper().replace(" ", "")
        if sev not in {"P0", "P1"}:
            continue
        status = str(row.get("status") or "open").strip().lower()
        if status in {"open", "unresolved", "active", ""}:
            return False
    return True


def _c11(snap: dict[str, Any]) -> bool:
    reg = (snap.get("receipt") or {}).get("manifest_registration")
    if not isinstance(reg, dict):
        return False
    return reg.get("registered") is True


def _c12(snap: dict[str, Any]) -> bool:
    consumers = (snap.get("receipt") or {}).get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return False
    for row in consumers:
        if not isinstance(row, dict):
            return False
        if row.get("executed") is not True or row.get("read_ok") is not True:
            return False
    return True


CHECKS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "C01": _c01,
    "C02": _c02,
    "C03": _c03,
    "C04": _c04,
    "C05": _c05,
    "C06": _c06,
    "C07": _c07,
    "C08": _c08,
    "C09": _c09,
    "C10": _c10,
    "C11": _c11,
    "C12": _c12,
}


def reduce(snap: dict[str, Any]) -> dict[str, Any]:
    for cid in CONDITION_IDS:
        if not CHECKS[cid](snap):
            return {
                "failing_condition_id": cid,
                "reason": REASONS[cid],
                "verdict": "FAIL",
            }
    return {
        "failing_condition_id": None,
        "reason": PASS_REASON,
        "verdict": "PASS",
    }


def judge(record: dict[str, Any], min_bytes: int = 128) -> dict[str, Any]:
    """Compatibility surface used by tools/command-center fan-in sites."""
    snap = {
        "receipt": record,
        "artifact_exists": record.get("exists") is True,
        "artifact_size": int(record.get("bytes") or 0),
        "min_bytes": min_bytes,
        "artifact_text": record.get("text") or "",
        "required_sentinel": record.get("sentinel") or "",
        "schema": record.get("schema") or {},
    }
    return reduce(snap)
