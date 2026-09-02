"""A8 error-message contract: happened / means / next_action.

A failure path satisfies the contract iff the owner-visible message names
what happened, what it means, and the exact next action. A message that only
says an operation failed is a defect.
"""
from __future__ import annotations

import re
from typing import Any

REQUIRED = ("happened", "means", "next_action")
NEXT_HINT = re.compile(
    r"(python3? |--[a-z]|command-center/|tools/|create |run |pass |write |"
    r"open |invoke |mkdir |emit |measure )",
    re.I,
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def check_fields(fields: dict[str, Any]) -> tuple[bool, str]:
    if not isinstance(fields, dict):
        return False, "not-an-object"
    missing = [k for k in REQUIRED if not _norm(fields.get(k))]
    if missing:
        return False, "missing:" + ",".join(missing)
    if len(_norm(fields["happened"])) < 12:
        return False, "happened-too-short"
    if len(_norm(fields["means"])) < 12:
        return False, "means-too-short"
    next_action = _norm(fields["next_action"])
    if len(next_action) < 12:
        return False, "next-action-too-short"
    if not NEXT_HINT.search(next_action):
        return False, "next-action-not-concrete"
    return True, "ok"


def check_text(text: str) -> tuple[bool, str]:
    """Parse labeled HAPPENED/MEANS/NEXT text, or fail unstructured strings."""
    raw = str(text or "")
    labels = {
        "happened": re.search(r"HAPPENED:\s*(.+)", raw, re.I),
        "means": re.search(r"MEANS:\s*(.+)", raw, re.I),
        "next_action": re.search(r"NEXT(?:_ACTION)?:\s*(.+)", raw, re.I),
    }
    if all(labels.values()):
        fields = {k: m.group(1) for k, m in labels.items()}
        return check_fields(fields)
    return False, "unstructured-missing-labels"


def format_message(fields: dict[str, Any]) -> str:
    ok, why = check_fields(fields)
    if not ok:
        raise ValueError(f"cannot format non-conforming fields: {why}")
    return (
        f"HAPPENED: {_norm(fields['happened'])}\n"
        f"MEANS: {_norm(fields['means'])}\n"
        f"NEXT: {_norm(fields['next_action'])}"
    )
