"""Schema + static validation of foundry workflows (IMP-0193).

``validate_workflow`` returns a deterministic list of violation records
``{"id": <VIOLATION_ID>, "path": <json-pointer>, "message": <text>}`` drawn
from ``foundry.constants.VIOLATION_IDS``.  Three layers are applied in order:

1. the structural floor in ``schema/workflow.schema.json`` (a stdlib
   interpreter of the draft-07 subset that schema uses: type, required,
   properties, additionalProperties, items, minItems, minLength, minimum,
   enum, ``$ref`` into ``#/$defs``);
2. static stage checks: duplicate stage ids, dependencies on unknown stages,
   dependency cycles, ``stopping.max_stages`` below the stage count;
3. parameter checks: ``params.values`` against ``params.schema`` (required,
   type, enum, undeclared keys).

``is_valid`` is the boolean view; ``param_errors`` exposes layer 3 alone.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from foundry.constants import (
    V_PARAM_ENUM,
    V_PARAM_REQUIRED,
    V_PARAM_TYPE,
    V_PARAM_UNDECLARED,
    V_SCHEMA_ADDITIONAL,
    V_SCHEMA_ENUM,
    V_SCHEMA_MIN_ITEMS,
    V_SCHEMA_MIN_LENGTH,
    V_SCHEMA_MINIMUM,
    V_SCHEMA_REQUIRED,
    V_SCHEMA_TYPE,
    V_STAGE_CYCLE,
    V_STAGE_DUPLICATE_ID,
    V_STAGE_UNKNOWN_DEPENDENCY,
    V_STOPPING_MAX_STAGES,
)

HERE = Path(__file__).resolve().parent
SCHEMA_PATH = HERE / "schema" / "workflow.schema.json"

_SCHEMA_CACHE: dict[str, Any] = {}


def load_schema() -> dict[str, Any]:
    """Load (and cache) the workflow schema document."""
    if "doc" not in _SCHEMA_CACHE:
        _SCHEMA_CACHE["doc"] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return _SCHEMA_CACHE["doc"]


def _error(vid: str, path: str, message: str) -> dict[str, str]:
    return {"id": vid, "path": path or "/", "message": message}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "null":
        return value is None
    return False


def _resolve(root: Mapping[str, Any], node: Mapping[str, Any]) -> Mapping[str, Any]:
    ref = node.get("$ref")
    if not isinstance(ref, str):
        return node
    if ref == "#":
        return root
    if not ref.startswith("#/"):
        raise ValueError(f"unsupported $ref {ref!r} (only local refs)")
    target: Any = root
    for part in ref[2:].split("/"):
        if not isinstance(target, Mapping) or part not in target:
            raise ValueError(f"unresolvable $ref {ref!r}")
        target = target[part]
    return target


def _check(
    value: Any,
    node: Mapping[str, Any],
    path: str,
    root: Mapping[str, Any],
    errors: list[dict[str, str]],
) -> None:
    node = _resolve(root, node)
    declared = node.get("type")
    if declared is not None:
        types = declared if isinstance(declared, list) else [declared]
        if not any(_type_ok(value, t) for t in types):
            errors.append(_error(V_SCHEMA_TYPE, path, f"expected {'/'.join(types)}"))
            return
    if "enum" in node and value not in node["enum"]:
        errors.append(_error(V_SCHEMA_ENUM, path, f"not one of {node['enum']!r}"))
    if isinstance(value, str) and "minLength" in node and len(value) < node["minLength"]:
        errors.append(_error(V_SCHEMA_MIN_LENGTH, path, f"shorter than {node['minLength']}"))
    if (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and "minimum" in node
        and value < node["minimum"]
    ):
        errors.append(_error(V_SCHEMA_MINIMUM, path, f"below minimum {node['minimum']}"))
    if isinstance(value, dict):
        props = node.get("properties") or {}
        for key in node.get("required") or []:
            if key not in value:
                errors.append(_error(V_SCHEMA_REQUIRED, f"{path}/{key}", "required key missing"))
        extra = node.get("additionalProperties", True)
        for key in sorted(value):
            child = f"{path}/{key}"
            if key in props:
                _check(value[key], props[key], child, root, errors)
            elif extra is False:
                errors.append(_error(V_SCHEMA_ADDITIONAL, child, "undeclared key"))
            elif isinstance(extra, Mapping):
                _check(value[key], extra, child, root, errors)
    if isinstance(value, list):
        if "minItems" in node and len(value) < node["minItems"]:
            errors.append(_error(V_SCHEMA_MIN_ITEMS, path, f"fewer than {node['minItems']} items"))
        items = node.get("items")
        if isinstance(items, Mapping):
            for index, item in enumerate(value):
                _check(item, items, f"{path}/{index}", root, errors)


def schema_errors(doc: Any) -> list[dict[str, str]]:
    """Layer 1: violations of the structural floor."""
    root = load_schema()
    errors: list[dict[str, str]] = []
    _check(doc, root, "", root, errors)
    return errors


def _stage_ids(stages: list[Any]) -> list[str]:
    return [
        st["id"]
        for st in stages
        if isinstance(st, Mapping) and isinstance(st.get("id"), str)
    ]


def _has_cycle(graph: Mapping[str, list[str]]) -> list[str]:
    """Return the stage ids on the first dependency cycle found (empty = acyclic)."""
    white, grey, black = 0, 1, 2
    colour = {node: white for node in graph}

    def visit(node: str, trail: list[str]) -> list[str]:
        colour[node] = grey
        trail.append(node)
        for dep in graph.get(node, []):
            if colour.get(dep, white) == grey:
                return trail[trail.index(dep):] + [dep]
            if colour.get(dep, white) == white:
                found = visit(dep, trail)
                if found:
                    return found
        trail.pop()
        colour[node] = black
        return []

    for start in sorted(graph):
        if colour[start] == white:
            found = visit(start, [])
            if found:
                return found
    return []


def static_errors(doc: Any) -> list[dict[str, str]]:
    """Layer 2: stage-graph and stopping-rule checks (skipped when stages is not a list)."""
    errors: list[dict[str, str]] = []
    if not isinstance(doc, Mapping) or not isinstance(doc.get("stages"), list):
        return errors
    stages = doc["stages"]
    ids = _stage_ids(stages)
    seen: set[str] = set()
    duplicates: list[str] = []
    for sid in ids:
        if sid in seen and sid not in duplicates:
            duplicates.append(sid)
        seen.add(sid)
    for sid in duplicates:
        errors.append(_error(V_STAGE_DUPLICATE_ID, "/stages", f"duplicate stage id {sid!r}"))
    graph: dict[str, list[str]] = {}
    for index, stage in enumerate(stages):
        if not isinstance(stage, Mapping) or not isinstance(stage.get("id"), str):
            continue
        deps = stage.get("depends_on") or []
        if not isinstance(deps, list):
            continue
        resolved: list[str] = []
        for dep in deps:
            if dep not in seen:
                errors.append(
                    _error(
                        V_STAGE_UNKNOWN_DEPENDENCY,
                        f"/stages/{index}/depends_on",
                        f"stage {stage['id']!r} depends on unknown stage {dep!r}",
                    )
                )
            elif isinstance(dep, str):
                resolved.append(dep)
        graph.setdefault(stage["id"], []).extend(resolved)
    cycle = _has_cycle(graph)
    if cycle:
        errors.append(_error(V_STAGE_CYCLE, "/stages", "dependency cycle " + " -> ".join(cycle)))
    stopping = doc.get("stopping")
    if isinstance(stopping, Mapping):
        max_stages = stopping.get("max_stages")
        if (
            isinstance(max_stages, int)
            and not isinstance(max_stages, bool)
            and max_stages < len(stages)
        ):
            errors.append(
                _error(
                    V_STOPPING_MAX_STAGES,
                    "/stopping/max_stages",
                    f"max_stages {max_stages} below stage count {len(stages)}",
                )
            )
    return errors


def param_errors(doc: Any) -> list[dict[str, str]]:
    """Layer 3: ``params.values`` against ``params.schema``."""
    errors: list[dict[str, str]] = []
    params = doc.get("params") if isinstance(doc, Mapping) else None
    if not isinstance(params, Mapping):
        return errors
    schema = params.get("schema")
    values = params.get("values")
    if not isinstance(schema, Mapping) or not isinstance(values, Mapping):
        return errors
    for name in sorted(schema):
        spec = schema[name]
        if not isinstance(spec, Mapping):
            continue
        path = f"/params/values/{name}"
        if name not in values:
            if spec.get("required") is True:
                errors.append(_error(V_PARAM_REQUIRED, path, f"required parameter {name!r} missing"))
            continue
        value = values[name]
        expected = spec.get("type")
        if isinstance(expected, str) and not _type_ok(value, expected):
            errors.append(_error(V_PARAM_TYPE, path, f"expected {expected}, got {type(value).__name__}"))
        allowed = spec.get("enum")
        if isinstance(allowed, list) and value not in allowed:
            errors.append(_error(V_PARAM_ENUM, path, f"not one of {allowed!r}"))
    for name in sorted(values):
        if name not in schema:
            errors.append(
                _error(V_PARAM_UNDECLARED, f"/params/values/{name}", f"parameter {name!r} not declared")
            )
    return errors


def validate_workflow(doc: Any) -> list[dict[str, str]]:
    """All violations, schema floor first, then static, then parameters."""
    return schema_errors(doc) + static_errors(doc) + param_errors(doc)


def is_valid(doc: Any) -> bool:
    """True when ``validate_workflow`` reports nothing."""
    return not validate_workflow(doc)


__all__ = [
    "SCHEMA_PATH",
    "is_valid",
    "load_schema",
    "param_errors",
    "schema_errors",
    "static_errors",
    "validate_workflow",
]
