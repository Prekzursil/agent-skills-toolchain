#!/usr/bin/env python3
"""Second validator implementation for WFA-0001.

This is not python-jsonschema. It walks Draft 2020-12 keywords used by the
WFA schema pack (type, properties, required, additionalProperties, items,
minItems, minLength, minimum, const, enum, pattern, $ref, oneOf) and
returns a list of error strings. A disagreement with jsonschema on the
bundled 36 cases is a schema-portability defect.
"""
from __future__ import annotations

import re
from typing import Any


def resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref}")
    cur: Any = root
    for part in ref[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if not isinstance(cur, dict) or part not in cur:
            raise ValueError(f"unresolvable $ref {ref}")
        cur = cur[part]
    if not isinstance(cur, dict):
        raise ValueError(f"$ref {ref} did not resolve to an object schema")
    return cur


def _type_of(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _type_ok(declared: str, value: Any) -> bool:
    got = _type_of(value)
    if declared == "number":
        return got in {"integer", "number"}
    if declared == "integer":
        return got == "integer"
    return got == declared


def iter_errors(
    instance: Any,
    schema: dict[str, Any],
    root: dict[str, Any] | None = None,
    path: str = "$",
) -> list[str]:
    root = root if root is not None else schema
    errors: list[str] = []
    if "$ref" in schema:
        try:
            target = resolve_ref(root, str(schema["$ref"]))
        except ValueError as exc:
            return [f"{path}: {exc}"]
        return iter_errors(instance, target, root, path)

    if "oneOf" in schema:
        matches = []
        for i, sub in enumerate(schema["oneOf"]):
            if not isinstance(sub, dict):
                continue
            sub_errs = iter_errors(instance, sub, root, f"{path}/oneOf/{i}")
            if not sub_errs:
                matches.append(i)
        if len(matches) != 1:
            errors.append(
                f"{path}: oneOf expected 1 match, got {len(matches)} {matches}"
            )
            return errors
        return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: const mismatch want={schema['const']!r}")
    if "enum" in schema:
        options = schema["enum"]
        if not isinstance(options, list) or instance not in options:
            errors.append(f"{path}: enum mismatch")
    declared = schema.get("type")
    if isinstance(declared, str) and not _type_ok(declared, instance):
        errors.append(f"{path}: type want={declared} got={_type_of(instance)}")
        return errors
    if isinstance(declared, list):
        if not any(_type_ok(t, instance) for t in declared if isinstance(t, str)):
            errors.append(f"{path}: type want={declared} got={_type_of(instance)}")
            return errors

    if "pattern" in schema and isinstance(instance, str):
        try:
            if re.search(str(schema["pattern"]), instance) is None:
                errors.append(f"{path}: pattern mismatch")
        except re.error as exc:
            errors.append(f"{path}: bad pattern {exc}")
    if "minLength" in schema and isinstance(instance, str):
        if len(instance) < int(schema["minLength"]):
            errors.append(f"{path}: minLength")
    if "minimum" in schema and isinstance(instance, (int, float)) and not isinstance(
        instance, bool
    ):
        if instance < schema["minimum"]:
            errors.append(f"{path}: minimum")

    if isinstance(instance, dict) and (
        declared == "object"
        or "properties" in schema
        or "required" in schema
        or "additionalProperties" in schema
    ):
        required = schema.get("required") or []
        if isinstance(required, list):
            for key in required:
                if key not in instance:
                    errors.append(f"{path}: missing required {key}")
        props = schema.get("properties") if isinstance(schema.get("properties"), dict) else {}
        additional = schema.get("additionalProperties", True)
        if additional is False:
            allowed = set(props)
            for key in instance:
                if key not in allowed:
                    errors.append(f"{path}: additional property {key}")
        for key, subschema in props.items():
            if key in instance and isinstance(subschema, dict):
                errors.extend(
                    iter_errors(instance[key], subschema, root, f"{path}.{key}")
                )

    if isinstance(instance, list) and (
        declared == "array" or "items" in schema or "minItems" in schema
    ):
        if "minItems" in schema and len(instance) < int(schema["minItems"]):
            errors.append(f"{path}: minItems")
        if "maxItems" in schema and len(instance) > int(schema["maxItems"]):
            errors.append(f"{path}: maxItems")
        items = schema.get("items")
        if isinstance(items, dict):
            for i, item in enumerate(instance):
                errors.extend(iter_errors(item, items, root, f"{path}[{i}]"))
    return errors


def is_valid(instance: Any, schema: dict[str, Any], root: dict[str, Any] | None = None) -> bool:
    return not iter_errors(instance, schema, root)
