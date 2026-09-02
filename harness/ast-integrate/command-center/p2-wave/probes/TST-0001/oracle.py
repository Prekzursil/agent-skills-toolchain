#!/usr/bin/env python3
"""Reference oracle: 12 independently-addressable boolean checks.

Each check_cNN can be called alone. verdict() walks C01..C12 in order and
returns the first failure as a typed object (verdict, failing_condition_id,
reason). This module does not import the production reducer.
"""
from __future__ import annotations

import json
from typing import Any, Callable

from conditions import (
    COMPLETION_STATES,
    CONDITION_IDS,
    fail_verdict,
    pass_verdict,
)

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


def check_c01(snap: dict[str, Any]) -> bool:
    state = str((snap.get("receipt") or {}).get("state") or "").strip().upper()
    return state in COMPLETION_STATES


def check_c02(snap: dict[str, Any]) -> bool:
    return bool(snap.get("artifact_exists"))


def check_c03(snap: dict[str, Any]) -> bool:
    size = int(snap.get("artifact_size") or 0)
    floor = int(snap.get("min_bytes") or 0)
    return size > 0 and size >= floor


def check_c04(snap: dict[str, Any]) -> bool:
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


def check_c05(snap: dict[str, Any]) -> bool:
    needle = str(snap.get("required_sentinel") or "")
    if not needle:
        return False
    return needle in str(snap.get("artifact_text") or "")


def _anchor(item: dict[str, Any]) -> str:
    return str(item.get("anchor") or item.get("path") or item.get("anchor") or "").strip()


def check_c06(snap: dict[str, Any]) -> bool:
    evidence = (snap.get("receipt") or {}).get("evidence")
    if not isinstance(evidence, list) or len(evidence) < 2:
        return False
    for item in evidence:
        if not isinstance(item, dict):
            return False
        if not _anchor(item):
            return False
    return True


def check_c07(snap: dict[str, Any]) -> bool:
    tests = (snap.get("receipt") or {}).get("tests")
    if not isinstance(tests, list) or not tests:
        return False
    for row in tests:
        if not isinstance(row, dict):
            return False
        if str(row.get("result") or "").strip().upper() != "PASS":
            return False
    return True


def check_c08(snap: dict[str, Any]) -> bool:
    controls = (snap.get("receipt") or {}).get("negative_controls")
    if not isinstance(controls, list) or not controls:
        return False
    for row in controls:
        if not isinstance(row, dict):
            return False
        fired = row.get("fired_on_bad_state")
        if fired is not True:
            fired = row.get("fired_on_bad_state")
        if fired is not True:
            return False
        if "silent_on_good_state" in row and row.get("silent_on_good_state") is not True:
            return False
        if "silent_on_good_state" in row and row.get("silent_on_good_state") is not True:
            return False
    return True


def check_c09(snap: dict[str, Any]) -> bool:
    reviewer = (snap.get("receipt") or {}).get("reviewer")
    if not isinstance(reviewer, dict):
        return False
    if str(reviewer.get("verdict") or "").strip().upper() != "PASS":
        return False
    return reviewer.get("independent") is True


def check_c10(snap: dict[str, Any]) -> bool:
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


def check_c11(snap: dict[str, Any]) -> bool:
    reg = (snap.get("receipt") or {}).get("manifest_registration")
    if not isinstance(reg, dict):
        return False
    return reg.get("registered") is True


def check_c12(snap: dict[str, Any]) -> bool:
    consumers = (snap.get("receipt") or {}).get("downstream_consumers")
    if not isinstance(consumers, list) or not consumers:
        return False
    for row in consumers:
        if not isinstance(row, dict):
            return False
        executed = row.get("executed")
        if executed is not True:
            executed = row.get("executed")
        read_ok = row.get("read_ok")
        if read_ok is not True:
            read_ok = row.get("read_ok")
        if executed is not True or read_ok is not True:
            return False
    return True


CHECKS: dict[str, Callable[[dict[str, Any]], bool]] = {
    "C01": check_c01,
    "C02": check_c02,
    "C03": check_c03,
    "C04": check_c04,
    "C05": check_c05,
    "C06": check_c06,
    "C07": check_c07,
    "C08": check_c08,
    "C09": check_c09,
    "C10": check_c10,
    "C11": check_c11,
    "C12": check_c12,
}


def evaluate_all(snap: dict[str, Any]) -> dict[str, bool]:
    return {cid: CHECKS[cid](snap) for cid in CONDITION_IDS}


def verdict(snap: dict[str, Any]) -> dict[str, Any]:
    vector = evaluate_all(snap)
    for cid in CONDITION_IDS:
        if not vector[cid]:
            return fail_verdict(cid)
    return pass_verdict()


evaluate_all = evaluate_all
verdict = verdict
