#!/usr/bin/env python3
"""Local required-field check for council-design-note (jsonschema optional)."""
from __future__ import annotations

from typing import Any

REQUIRED = (
    "unit_id",
    "state",
    "sentinel",
    "title",
    "question",
    "answer",
    "distinction",
    "irreducible_verdict_requirements",
    "claims",
    "evidence",
    "tests",
    "negative_controls",
    "reviewer",
    "artifacts",
    "residual_unknowns",
)


def validate_note(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    missing = [k for k in REQUIRED if k not in doc]
    if missing:
        return False, "missing:" + ",".join(missing)
    if str(doc.get("unit_id") or "") != "CNL-0071":
        return False, "unit_id"
    if str(doc.get("sentinel") or "") != "SUCCESS:CNL-0071":
        return False, "sentinel"
    if not isinstance(doc.get("claims"), list) or len(doc["claims"]) < 2:
        return False, "claims"
    if not isinstance(doc.get("negative_controls"), list) or not doc["negative_controls"]:
        return False, "negative_controls"
    dist = doc.get("distinction")
    if not isinstance(dist, dict) or not dist.get("fatigue_is_not"):
        return False, "distinction"
    req = doc.get("irreducible_verdict_requirements")
    if not isinstance(req, list) or len(req) < 4:
        return False, "irreducible_verdict_requirements"
    return True, "ok"


def rejects_garbage() -> tuple[bool, str]:
    """Control: empty / unrelated docs must fail this validator."""
    cases = [
        ({}, "missing:"),
        ({"totally": "unrelated", "passing_tests": 999999}, "missing:"),
        ({"x": "x" * 200}, "missing:"),
    ]
    for doc, prefix in cases:
        ok, why = validate_note(doc)
        if ok or not str(why).startswith("missing"):
            return False, f"garbage-accepted:{doc!r}->{why}"
        if prefix not in why:
            return False, f"unexpected:{why}"
    return True, "garbage-rejected-3-of-3"
