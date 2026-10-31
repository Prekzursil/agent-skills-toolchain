"""Receipt decoding, parsing and content checks — the raw material of the AND-gate.

Kept separate from :mod:`agentspec.oracle` so each function is single-purpose and each failure
mode maps to exactly one taxonomy reason.

EVERY string this module raises reaches ``error.root_cause`` on the wire through
:func:`agentspec.oracle.observe`, so none of them may carry a runtime-specific rendering. That
is why the diagnostics below name no interpreter-specific cause, no ``json`` module message and
no ``type(x).__name__``: measured, those produced ``not valid UTF-8 (invalid start byte)`` /
``Expecting value: line 1 column 1 (char 0)`` / ``list`` on Python against ``invalid
continuation`` / ``Unexpected token`` / ``array`` on JS for the SAME receipt bytes.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agentspec import wire
from agentspec.spec import ReceiptSpec

_BOM = "﻿"


class ReceiptUnparseable(ValueError):
    """The receipt bytes are not decodable / not the declared shape."""

    reason = "receipt-unparseable"


def decode(raw: bytes) -> str:
    """Decode receipt bytes as UTF-8, tolerating a BOM, refusing anything else.

    A BOM is tolerated because Windows writers emit one and it is not a content defect.
    Invalid UTF-8 IS a content defect and must not be silently replaced — a lossy decode
    would turn a corrupt receipt into a plausible-looking one.

    The message deliberately does NOT name WHICH UTF-8 rule was broken. ``UnicodeDecodeError``
    reports ``invalid start byte`` / ``invalid continuation byte`` / ``unexpected end``, and a
    JS ``TextDecoder`` reports none of them, so quoting the Python reason made the JS mirror
    hardcode a cause it had not measured.
    """
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ReceiptUnparseable("receipt-unparseable: not valid UTF-8") from exc
    return text.removeprefix(_BOM)


def parse_json_object(text: str) -> Mapping[str, Any]:
    """Parse ``text`` as a JSON OBJECT. An array or scalar has no field to validate.

    ``parse_constant`` is load-bearing, not decoration: stock ``json.loads`` ACCEPTS the bare
    ``NaN`` / ``Infinity`` / ``-Infinity`` literals that ``json.dumps`` itself emits, while
    ``JSON.parse`` rejects them. Measured end to end: a receipt written by
    ``json.dumps({"summary": float("nan")})`` was a full six-clause SUCCESS on the Python
    oracle and ``severed-stream`` on the JS one. Rejecting matches ``JSON.parse`` and matches
    :mod:`agentspec.canonical` R14, which had already made the same call for the canonical
    decoder — the two Python code paths were disagreeing with each other as well.
    """
    try:
        payload = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ReceiptUnparseable("receipt-unparseable: invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ReceiptUnparseable(
            "receipt-unparseable: top level must be an object, got "
            f"{wire.json_type_name(payload)}"
        )
    return payload


def missing_fields(payload: Mapping[str, Any], spec: ReceiptSpec) -> tuple[str, ...]:
    """Required keys that are absent, ``null``, or blank whitespace — sorted.

    ``0`` / ``False`` / ``[]`` are PRESENT: a falsy-but-real value is a work product. Only
    ``None`` and an all-blank string count as missing, where "blank" is
    :data:`agentspec.wire.BLANK_CHARS` and NOT ``str.strip()`` — the two differ on six code
    points and that difference alone flipped the ``receipt-schema`` clause between runtimes.
    """
    missing = [
        field
        for field in spec.required_fields
        if field not in payload or _is_blank(payload[field])
    ]
    return wire.sorted_wire(missing)


def present_markers(text: str, spec: ReceiptSpec) -> tuple[str, ...]:
    """Forbidden markers found in ``text``, case-insensitively for ASCII — sorted.

    These are the "not actually finished" phrases. Their absence is the AND-gate's content
    clause, without which the gate reduces to "exit 0 and non-empty" on a text receipt.

    The fold is ASCII-only (:func:`agentspec.wire.fold_ascii_case`). Full Unicode lowercasing
    disagreed across the two runtimes on 28 code points because each reads its own Unicode
    tables, so a non-ASCII marker is matched EXACTLY. Disclosed narrowing, deterministic
    contract.
    """
    lowered = wire.fold_ascii_case(text)
    return wire.sorted_wire(
        m for m in spec.forbidden_markers if wire.fold_ascii_case(m) in lowered
    )


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    return isinstance(value, str) and wire.is_blank(value)


def _reject_constant(name: str) -> Any:
    """``NaN``/``Infinity``/``-Infinity`` are not JSON, and ``JSON.parse`` says so too."""
    raise ReceiptUnparseable(f"receipt-unparseable: invalid JSON literal {name}")
