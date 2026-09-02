#!/usr/bin/env python3
"""Condition-5 sentinel check keyed on semantic ROLE, not payload substring.

The catalog target for TST-0008: the sentinel is a *terminal line of the
receipt's typed `status` field*. A document that merely DESCRIBES the
token in body/notes/question does not satisfy. A different unit's token
in `status` does not satisfy, even if the expected token appears in prose.

`check_sentinel_substring` is the known-broken cousin (plain `expected in
payload`). It exists so both-states controls can show the role checker
and the substring matcher DISAGREE on mention-only fixtures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
UNIT = "TST-0008"
EXPECTED = "SUCCESS:TST-0008"
SENTINEL_LINE = re.compile(r"^SUCCESS:[A-Z]{2,5}-\d{4}$")


def load_receipt(path: Path) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        raise ValueError(f"receipt is not an object: {path}")
    return doc


def status_terminal_line(doc: dict) -> tuple[str | None, str]:
    """Read the typed status field; return (terminal_line_or_none, basis)."""
    if not isinstance(doc, dict):
        return None, "not-an-object"
    if "status" not in doc:
        return None, "status-field-absent"
    raw = doc["status"]
    if raw is None:
        return None, "status-field-null"
    if not isinstance(raw, str):
        return None, "status-field-not-string"
    normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
    terminal = normalized.split("\n")[-1].strip()
    if terminal == "":
        return "", "status-field-empty"
    return terminal, "status-terminal-line"


def check_sentinel_role(doc: dict, expected: str) -> dict:
    """USE: equality of the status field's terminal line against `expected`.

    Does not scan free text, does not dump the document, does not use
    substring membership of `expected` in the payload.
    """
    terminal, basis = status_terminal_line(doc)
    out = {
        "expected": expected,
        "method": "status-terminal-line-equality",
        "observed": terminal,
        "role_basis": basis,
    }
    if terminal is None or basis in {
        "not-an-object",
        "status-field-absent",
        "status-field-null",
        "status-field-not-string",
        "status-field-empty",
    }:
        out["satisfies"] = False
        out["reason"] = basis
        out["role"] = "absent"
        return out
    if terminal == expected:
        out["satisfies"] = True
        out["reason"] = "status-terminal-line-is-expected-sentinel"
        out["role"] = "use"
        return out
    if SENTINEL_LINE.match(terminal) and terminal != expected:
        out["satisfies"] = False
        out["reason"] = "status-terminal-line-wrong-unit"
        out["role"] = "mismatch"
        out["observed_unit"] = terminal.split(":", 1)[-1]
        out["expected_unit"] = expected.split(":", 1)[-1]
        out["mismatch"] = f"observed={terminal} expected={expected}"
        return out
    out["satisfies"] = False
    out["reason"] = "status-terminal-line-not-sentinel"
    out["role"] = "mismatch"
    return out


def check_sentinel_substring(payload: str, expected: str) -> dict:
    """Known-broken cousin: any occurrence of `expected` in free text."""
    present = expected in payload
    return {
        "expected": expected,
        "method": "substring-anywhere",
        "satisfies": present,
        "reason": (
            "sentinel-substring-present" if present else "sentinel-substring-absent"
        ),
        "role": "mention-or-use-undifferentiated",
    }


def _fixture(name: str) -> Path:
    return FIX / name


def test_sentinel_in_body_does_not_satisfy(expected: str = EXPECTED) -> dict:
    path = _fixture("body_mention.json")
    doc = load_receipt(path)
    text = path.read_text(encoding="utf-8")
    role = check_sentinel_role(doc, expected)
    sub = check_sentinel_substring(text, expected)
    ok = (
        role["satisfies"] is False
        and role["reason"] == "status-field-empty"
        and sub["satisfies"] is True
        and expected in (doc.get("body") or "")
    )
    return {
        "id": "test_sentinel_in_body_does_not_satisfy",
        "ok": ok,
        "role": role,
        "substring_cousin": sub,
        "fixture": path.name,
    }


def test_sentinel_in_status_field_satisfies(expected: str = EXPECTED) -> dict:
    path = _fixture("status_use.json")
    doc = load_receipt(path)
    role = check_sentinel_role(doc, expected)
    whole_field = doc.get("status")
    whole_equals = whole_field == expected
    ok = (
        role["satisfies"] is True
        and role["role"] == "use"
        and role["observed"] == expected
        and whole_equals is False
        and isinstance(whole_field, str)
        and "\n" in whole_field
    )
    return {
        "id": "test_sentinel_in_status_field_satisfies",
        "ok": ok,
        "role": role,
        "whole_field_equals_expected": whole_equals,
        "fixture": path.name,
        "notes": (
            "status is multiline (DELIVERED then the sentinel). Whole-field "
            "equality would miss it; the terminal line is the ROLE."
        ),
    }


def test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy(
    expected: str = EXPECTED,
) -> dict:
    path = _fixture("wrong_unit.json")
    doc = load_receipt(path)
    text = path.read_text(encoding="utf-8")
    role = check_sentinel_role(doc, expected)
    sub = check_sentinel_substring(text, expected)
    ok = (
        role["satisfies"] is False
        and role["reason"] == "status-terminal-line-wrong-unit"
        and role.get("observed_unit") == "TST-0017"
        and role.get("expected_unit") == "TST-0008"
        and expected in (doc.get("body") or "")
        and sub["satisfies"] is True
    )
    return {
        "id": "test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy",
        "ok": ok,
        "role": role,
        "substring_cousin": sub,
        "fixture": path.name,
        "notes": (
            "Body quotes the expected token so a substring matcher would "
            "pass; the typed status terminal line is SUCCESS:TST-0017."
        ),
    }


REQUIRED = (
    test_sentinel_in_body_does_not_satisfy,
    test_sentinel_in_status_field_satisfies,
    test_sentinel_of_a_DIFFERENT_unit_id_does_not_satisfy,
)


def run_required_tests(expected: str = EXPECTED) -> dict:
    rows = [fn(expected) for fn in REQUIRED]
    return {
        "expected": expected,
        "n": len(rows),
        "ok": all(r["ok"] for r in rows),
        "tests": rows,
    }
