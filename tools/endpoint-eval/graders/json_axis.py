"""JSON-mode / structured-output axis (lens 08 section 2.2): three rates plus refusal-field rate.

``valid_json_rate`` (parses), ``schema_valid_rate`` (parses AND validates), ``strict_honoured``
(the endpoint really ran constrained decoding: the hub's ``structured_mode == "native"``), and
``refusal_field_rate`` (a refusal arrived as the separate ``refusal`` field rather than being
flattened into ``content``). Every rate over zero samples is 0.0: fail closed, never divide.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from graders.tool_fidelity import schema_errors

NATIVE = "native"


def _rate(hits: int, total: int) -> float:
    return hits / total if total else 0.0


def _parse(output: Any) -> tuple[bool, Any]:
    if not isinstance(output, str):
        return False, None
    try:
        return True, json.loads(output)
    except ValueError:
        return False, None


def valid_json_rate(outputs: Sequence[Any]) -> float:
    return _rate(sum(1 for output in outputs if _parse(output)[0]), len(outputs))


def schema_valid_rate(outputs: Sequence[Any], schema: Mapping[str, Any]) -> float:
    hits = 0
    for output in outputs:
        ok, value = _parse(output)
        if ok and not schema_errors(value, schema):
            hits += 1
    return _rate(hits, len(outputs))


def strict_honoured(results: Sequence[Mapping[str, Any]]) -> float:
    """Share of results whose ``structured_mode`` is ``native`` (strict schema really enforced)."""
    return _rate(
        sum(1 for result in results if result.get("structured_mode") == NATIVE),
        len(results),
    )


def refusal_of(result: Mapping[str, Any]) -> str | None:
    """The non-empty ``refusal`` field of a hub result or a raw chat-completion, else None."""
    refusal = result.get("refusal")
    if not refusal:
        choices = result.get("choices") or []
        message = choices[0].get("message", {}) if choices else {}
        refusal = message.get("refusal")
    return refusal if isinstance(refusal, str) and refusal else None


def refusal_field_rate(results: Sequence[Mapping[str, Any]]) -> float:
    return _rate(
        sum(1 for result in results if refusal_of(result) is not None), len(results)
    )
