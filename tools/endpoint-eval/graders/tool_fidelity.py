"""Tool-call fidelity grader, BFCL-shaped (lens 08 section 2.1).

AST match rule (Gorilla BFCL): the function name is equal, every emitted argument is a
declared parameter, and every gold parameter's value is in its accepted-value list, where
an empty string ``""`` in the list marks the parameter optional. ``parallel`` is an
order-independent 1:1 matching of all calls; ``irrelevance`` passes only when zero calls
were emitted. ``schema-strict`` validates the emitted arguments against the tool's JSON
schema with a minimal stdlib checker (type, required, enum, additionalProperties, items).

Emitted calls may be OpenAI wire objects (``{"id", "type", "function": {"name",
"arguments": "<json string>"}}``) or the simplified ``{"name", "args": {...}}`` shape.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

Gold = Mapping[str, Any]


@dataclass(frozen=True)
class Grade:
    passed: bool
    reasons: tuple[str, ...] = ()


def _parse_arguments(raw: Any) -> tuple[dict[str, Any] | None, str | None]:
    """(argument object, None) or (None, reason) when it cannot be read as a JSON object."""
    if raw is None:
        return {}, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return None, "arguments-not-json"
    if isinstance(raw, dict):
        return raw, None
    return None, "arguments-not-object"


def _name_and_raw(call: Mapping[str, Any]) -> tuple[str, Any]:
    function = call.get("function")
    if isinstance(function, Mapping):
        return str(function.get("name", "")), function.get("arguments")
    return str(call.get("name", "")), call.get("args", call.get("arguments"))


def normalize_call(call: Mapping[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """(name, args) for a wire-shaped or simplified call; args is None when unparseable."""
    name, raw = _name_and_raw(call)
    return name, _parse_arguments(raw)[0]


def _optional_args(gold: Gold) -> set[str]:
    optional = set(gold.get("optional", ()))
    for arg, accepted in gold.get("args", {}).items():
        if "" in accepted:
            optional.add(arg)
    return optional


def _grade_one(call: Mapping[str, Any], gold: Gold) -> Grade:
    reasons: list[str] = []
    name, raw = _name_and_raw(call)
    args, problem = _parse_arguments(raw)
    if name != gold["name"]:
        reasons.append(f"name-mismatch:{name}!={gold['name']}")
    if args is None:
        reasons.append(str(problem))
        return Grade(False, tuple(reasons))
    declared = gold.get("args", {})
    optional = _optional_args(gold)
    for arg in args:
        if arg not in declared:
            reasons.append(f"undeclared-arg:{arg}")
    for arg, accepted in declared.items():
        if arg not in args:
            if arg not in optional:
                reasons.append(f"missing-arg:{arg}")
            continue
        if args[arg] not in accepted:
            reasons.append(f"value-not-accepted:{arg}")
    return Grade(not reasons, tuple(reasons))


def grade_tool_call(emitted: Sequence[Mapping[str, Any]], gold: Gold) -> Grade:
    """``simple``: exactly one call that matches the gold spec."""
    if len(emitted) != 1:
        return Grade(False, (f"call-count:{len(emitted)}",))
    return _grade_one(emitted[0], gold)


def _perfect_matching(matrix: list[list[bool]]) -> bool:
    """Backtracking search for a perfect matching in a small boolean compatibility matrix."""
    used: set[int] = set()

    def place(row: int) -> bool:
        if row == len(matrix):
            return True
        for col, ok in enumerate(matrix[row]):
            if ok and col not in used:
                used.add(col)
                if place(row + 1):
                    return True
                used.discard(col)
        return False

    return place(0)


def grade_parallel(
    emitted: Sequence[Mapping[str, Any]], golds: Sequence[Gold]
) -> Grade:
    """``parallel``: order-independent 1:1 matching of every emitted call to a gold spec."""
    if len(emitted) != len(golds):
        return Grade(False, (f"call-count:{len(emitted)}!={len(golds)}",))
    matrix = [[_grade_one(call, gold).passed for call in emitted] for gold in golds]
    if _perfect_matching(matrix):
        return Grade(True)
    return Grade(False, ("no-perfect-matching",))


def grade_irrelevance(emitted: Sequence[Mapping[str, Any]]) -> Grade:
    """``irrelevance``: the model must not call anything."""
    if emitted:
        return Grade(False, (f"false-call:{len(emitted)}",))
    return Grade(True)


_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "null": lambda v: v is None,
}


def schema_errors(value: Any, schema: Mapping[str, Any], path: str = "$") -> list[str]:
    """Minimal JSON-schema check: type, enum, required, additionalProperties=false, items."""
    errors: list[str] = []
    declared = schema.get("type")
    if declared is not None:
        types = declared if isinstance(declared, list) else [declared]
        for kind in types:
            if kind not in _TYPE_CHECKS:
                return [f"{path}: unsupported type {kind}"]
        if not any(_TYPE_CHECKS[kind](value) for kind in types):
            return [f"{path}: expected {'|'.join(types)}"]
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: not in enum")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required {key}")
        for key, item in value.items():
            if key in properties:
                errors.extend(schema_errors(item, properties[key], f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: additional property {key}")
    if isinstance(value, list) and "items" in schema:
        for index, item in enumerate(value):
            errors.extend(schema_errors(item, schema["items"], f"{path}[{index}]"))
    return errors


def grade_schema_strict(args: Any, schema: Mapping[str, Any]) -> Grade:
    """``schema-strict``: the emitted arguments (object or JSON string) validate against the schema."""
    parsed = args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
        except ValueError:
            return Grade(False, ("arguments-not-json",))
    errors = schema_errors(parsed, schema)
    return Grade(not errors, tuple(errors))
