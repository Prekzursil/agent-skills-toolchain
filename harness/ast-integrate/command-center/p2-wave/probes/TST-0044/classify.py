"""Classify an adapter terminal result. EMPTY_SUCCESS is P1."""
from __future__ import annotations

from typing import Any

P1 = "P1"
CLOSED_CLASSES = frozenset(
    {
        "SUCCESS",
        "TOOL_ERROR",
        "SCHEMA_INVALID",
        "EMPTY_SUCCESS",
        "SEVERED_STREAM",
        "ADAPTER_EXIT_N",
        "TIMEOUT",
        "DEGRADED",
        "BLOCKED",
        "UNCLASSIFIED",
    }
)


def classify(terminal: Any) -> dict:
    """Map an adapter terminal object to a closed class.

    EMPTY_SUCCESS fires when status claims SUCCESS but there is no result id
    and content is missing or empty. That is the silent-pass trap.
    """
    if not isinstance(terminal, dict):
        return {
            "class": "UNCLASSIFIED",
            "severity": P1,
            "reason": f"non-object terminal {type(terminal).__name__}",
            "empty_success": False,
        }
    status = str(terminal.get("status") or "").upper()
    rid = terminal.get("id")
    content = terminal.get("content")
    fclass = str(terminal.get("failure_class") or "")
    empty_content = content in (None, [], "")

    if status == "SUCCESS" and (not rid) and empty_content:
        return {
            "class": "EMPTY_SUCCESS",
            "severity": P1,
            "reason": "SUCCESS with no id and empty content",
            "empty_success": True,
        }
    if status == "SUCCESS" and fclass in {"schema-invalid", "malformed-result"}:
        return {
            "class": "EMPTY_SUCCESS",
            "severity": P1,
            "reason": "malformed result reported as SUCCESS",
            "empty_success": True,
        }
    if status == "SUCCESS":
        if not rid:
            return {
                "class": "EMPTY_SUCCESS",
                "severity": P1,
                "reason": "SUCCESS without a result id",
                "empty_success": True,
            }
        return {
            "class": "SUCCESS",
            "severity": None,
            "reason": "explicit SUCCESS with id",
            "empty_success": False,
        }
    if status == "FAILED":
        if fclass in {"schema-invalid", "malformed-result"}:
            reason = str(terminal.get("reason") or "").strip()
            if not reason:
                return {
                    "class": "UNCLASSIFIED",
                    "severity": P1,
                    "reason": "FAILED schema-invalid with empty reason",
                    "empty_success": False,
                }
            return {
                "class": "SCHEMA_INVALID",
                "severity": None,
                "reason": reason,
                "empty_success": False,
            }
        if fclass == "tool-error":
            return {
                "class": "TOOL_ERROR",
                "severity": None,
                "reason": str(terminal.get("reason") or "tool-error"),
                "empty_success": False,
            }
        if fclass:
            mapped = fclass.upper().replace("-", "_")
            if mapped in CLOSED_CLASSES:
                return {
                    "class": mapped,
                    "severity": None,
                    "reason": str(terminal.get("reason") or fclass),
                    "empty_success": False,
                }
        return {
            "class": "UNCLASSIFIED",
            "severity": P1,
            "reason": "FAILED without a closed failure_class",
            "empty_success": False,
        }
    return {
        "class": "UNCLASSIFIED",
        "severity": P1,
        "reason": f"status={status!r} is not a terminal state",
        "empty_success": False,
    }
