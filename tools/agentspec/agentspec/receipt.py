"""Receipt decoding, parsing and content checks — the raw material of the AND-gate.

Kept separate from :mod:`agentspec.oracle` so each function is single-purpose and each failure
mode maps to exactly one taxonomy reason.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agentspec.spec import ReceiptSpec


class ReceiptUnparseable(ValueError):
    """The receipt bytes are not decodable / not the declared shape."""

    reason = "receipt-unparseable"


def decode(raw: bytes) -> str:
    """Decode receipt bytes as UTF-8, tolerating a BOM, refusing anything else.

    A BOM is tolerated because Windows writers emit one and it is not a content defect.
    Invalid UTF-8 IS a content defect and must not be silently replaced — a lossy decode
    would turn a corrupt receipt into a plausible-looking one.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReceiptUnparseable(
            f"receipt-unparseable: not valid UTF-8 ({exc.reason})"
        ) from exc
    return text.removeprefix("﻿")


def parse_json_object(text: str) -> Mapping[str, Any]:
    """Parse ``text`` as a JSON OBJECT. An array or scalar has no field to validate."""
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ReceiptUnparseable(f"receipt-unparseable: invalid JSON ({exc})") from exc
    if not isinstance(payload, dict):
        raise ReceiptUnparseable(
            f"receipt-unparseable: top level must be an object, got {type(payload).__name__}"
        )
    return payload


def missing_fields(payload: Mapping[str, Any], spec: ReceiptSpec) -> tuple[str, ...]:
    """Required keys that are absent, ``null``, or blank whitespace — sorted.

    ``0`` / ``False`` / ``[]`` are PRESENT: a falsy-but-real value is a work product. Only
    ``None`` and an all-whitespace string count as missing.
    """
    missing = [
        field
        for field in spec.required_fields
        if field not in payload or _is_blank(payload[field])
    ]
    return tuple(sorted(missing))


def present_markers(text: str, spec: ReceiptSpec) -> tuple[str, ...]:
    """Forbidden markers found in ``text``, case-insensitively — sorted.

    These are the "not actually finished" phrases. Their absence is the AND-gate's content
    clause, without which the gate reduces to "exit 0 and non-empty" on a text receipt.
    """
    lowered = text.lower()
    return tuple(sorted(m for m in spec.forbidden_markers if m.lower() in lowered))


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and not value.strip()
