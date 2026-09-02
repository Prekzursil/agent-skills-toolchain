"""Explanation-completeness checker.

A dial that differs from the published default MUST carry a non-empty reason.
A missing reason is a FAIL of this unit, not a warning.
"""
from __future__ import annotations

import copy

from rules import DIALS


def missing_reasons(record: dict) -> list[str]:
    errors: list[str] = []
    rows = record.get("dials") if isinstance(record, dict) else None
    if not isinstance(rows, list):
        return ["dials-absent"]
    seen: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            errors.append("dial-row-not-object")
            continue
        name = str(row.get("dial") or "")
        seen.append(name)
        if row.get("differs_from_default") is True:
            if not str(row.get("reason") or "").strip():
                errors.append(f"missing-reason:{name or '?'}")
            if not str(row.get("rule_id") or "").strip():
                errors.append(f"missing-rule_id:{name or '?'}")
    for name in DIALS:
        if name not in seen:
            errors.append(f"missing-dial:{name}")
    return errors


def complete(record: dict) -> bool:
    return not missing_reasons(record)


def plant_missing_reason(record: dict) -> dict:
    """Clone a record and strip the reason from a non-default protocol dial.

    If every dial currently matches default, force protocol off-default first
    so the planted state is the state this check is meant to reject.
    """
    planted = copy.deepcopy(record)
    rows = planted.setdefault("dials", [])
    target = None
    for row in rows:
        if isinstance(row, dict) and row.get("dial") == "protocol":
            target = row
            break
    if target is None:
        target = {
            "dial": "protocol",
            "value": "P46-architecture-review-board",
            "default": "P01-free-form-moderated-panel",
            "differs_from_default": True,
            "rule_id": "PLANTED",
            "reason": "",
        }
        rows.append(target)
    else:
        if target.get("value") == target.get("default"):
            target["value"] = "P46-architecture-review-board"
        target["differs_from_default"] = True
        target["reason"] = ""
        target["rule_id"] = target.get("rule_id") or "PLANTED"
    planted["protocol"] = target["value"]
    planted["planted_missing_reason_on"] = "protocol"
    return planted


# Probe-2 import aliases (same functions, catalog wording).
missing_reasons = missing_reasons
plant_missing_reason = plant_missing_reason
