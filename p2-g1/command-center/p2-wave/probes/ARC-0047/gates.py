"""Executable security-gate models for ARC-0047 fail-open classes.

FIRE (True) means the gate alarmed / blocked / failed closed.
PASS (False) means the gate was silent / allowed / skipped.
"""
from __future__ import annotations

from typing import Any

FIRE = True
PASS = False

FORBIDDEN_VERB = "Bash"
FORBIDDEN_TEXT = "Bash"


def text_payload_guard(event: dict[str, Any], forbidden: str = FORBIDDEN_TEXT) -> bool:
    """Match forbidden pattern in payload TEXT. Fail-open on structured use."""
    text = str(event.get("payload_text") or "")
    return FIRE if forbidden.lower() in text.lower() else PASS


def tool_verb_guard(event: dict[str, Any], forbidden: str = FORBIDDEN_VERB) -> bool:
    """Match the tool VERB field only. Mention in payload is not use."""
    verb = str((event.get("tool") or {}).get("verb") or "")
    return FIRE if verb == forbidden else PASS


def completeness_require(event: dict[str, Any], default_on: bool = False) -> bool:
    """Completeness check. default_on=False is the CI fail-open (require off)."""
    flag = event.get("require_flag")
    if flag is None:
        flag = default_on
    if not flag:
        return PASS
    present = bool(event.get("artifact_present"))
    return PASS if present else FIRE


def silent_detector(_event: dict[str, Any]) -> bool:
    """Always silent. Measures nothing."""
    return PASS


def absent_normalizes_to_pass(event: dict[str, Any]) -> bool:
    """Missing input → PASS (fail-open). Present bad input → FIRE."""
    if event.get("input_present") is False or event.get("input") is None:
        return PASS
    return FIRE if event.get("is_bad") else PASS


def absent_fail_closed(event: dict[str, Any]) -> bool:
    """Missing input → FIRE (fail-closed). Present bad → FIRE. Present good → PASS."""
    if event.get("input_present") is False or event.get("input") is None:
        return FIRE
    return FIRE if event.get("is_bad") else PASS


def except_pass_gate(event: dict[str, Any]) -> bool:
    """Evaluator exception returns PASS. Author list must not include this."""
    try:
        if event.get("raise_eval_error"):
            raise RuntimeError("gate-eval-error")
        return tool_verb_guard(event)
    except Exception:
        return PASS
