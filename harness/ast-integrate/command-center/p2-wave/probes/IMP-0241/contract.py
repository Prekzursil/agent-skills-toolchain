#!/usr/bin/env python3
"""Blueprint authoring contract consumed by IMP-0241 (IMP-0230 six elements).

A blueprint that omits any required element cannot be registered. Each
omission produces a distinct rejection id.
"""
from __future__ import annotations

from typing import Any, Callable

REQUIRED_ELEMENTS: tuple[str, ...] = (
    "workflow",
    "example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)

REJECTION_IDS: dict[str, str] = {
    "workflow": "CONTRACT-MISSING-WORKFLOW",
    "example": "CONTRACT-MISSING-EXAMPLE",
    "preset": "CONTRACT-MISSING-PRESET",
    "stopping_rules": "CONTRACT-MISSING-STOPPING-RULES",
    "smoke_test": "CONTRACT-MISSING-SMOKE-TEST",
    "capability_vector": "CONTRACT-MISSING-CAPABILITY-VECTOR",
}


def _present_workflow(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    stages = value.get("stages")
    return (
        bool(value.get("id"))
        and value.get("kind") == "workflow_blueprint"
        and isinstance(stages, list)
        and len(stages) >= 1
        and isinstance(value.get("stopping"), dict)
    )


def _present_example(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("id")) and "input" in value


def _present_preset(value: Any) -> bool:
    return isinstance(value, dict) and bool(value.get("id")) and isinstance(value.get("bindings"), dict)


def _present_stopping(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    return "max_stages" in value and "on_error" in value and "documented" in value


def _present_smoke(value: Any) -> bool:
    return callable(value) or (
        isinstance(value, dict) and callable(value.get("callable"))
    )


def _present_caps(value: Any) -> bool:
    return isinstance(value, (list, tuple)) and len(value) >= 1 and all(
        isinstance(x, str) and x for x in value
    )


_CHECKERS: dict[str, Callable[[Any], bool]] = {
    "workflow": _present_workflow,
    "example": _present_example,
    "preset": _present_preset,
    "stopping_rules": _present_stopping,
    "smoke_test": _present_smoke,
    "capability_vector": _present_caps,
}


def register(blueprint: dict[str, Any]) -> dict[str, Any]:
    """Register a blueprint or return a distinct rejection per omitted element."""
    missing: list[str] = []
    rejections: list[str] = []
    for element in REQUIRED_ELEMENTS:
        checker = _CHECKERS[element]
        if not checker(blueprint.get(element)):
            missing.append(element)
            rejections.append(REJECTION_IDS[element])
    if missing:
        return {
            "ok": False,
            "registered": False,
            "missing": missing,
            "rejections": rejections,
            "id": blueprint.get("id"),
        }
    caps = list(blueprint["capability_vector"])
    return {
        "ok": True,
        "registered": True,
        "id": blueprint["workflow"]["id"],
        "name": blueprint.get("name"),
        "capability_vector": caps,
        "missing": [],
        "rejections": [],
    }


def omission_matrix(blueprint: dict[str, Any]) -> list[dict[str, Any]]:
    """Drop each required element one at a time; expect 6 distinct rejection ids."""
    rows: list[dict[str, Any]] = []
    for element in REQUIRED_ELEMENTS:
        mutant = dict(blueprint)
        mutant[element] = None
        result = register(mutant)
        rows.append(
            {
                "omitted": element,
                "rejection": (result.get("rejections") or [None])[0],
                "ok": result.get("ok"),
            }
        )
    return rows
