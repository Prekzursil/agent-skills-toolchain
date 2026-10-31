"""IMP-0230 six-element contract: omit any required element and registration fails.

Each one-at-a-time omission produces a distinct rejection token. A complete
blueprint never returns SILENT for any required element.
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

REQUIRED_ELEMENTS: tuple[str, ...] = (
    "typed_workflow",
    "runnable_example",
    "preset",
    "stopping_rules",
    "smoke_test",
    "capability_vector",
)

VIOLATION_ID: dict[str, str] = {
    "typed_workflow": "CONTRACT-MISSING-TYPED-WORKFLOW",
    "runnable_example": "CONTRACT-MISSING-RUNNABLE-EXAMPLE",
    "preset": "CONTRACT-MISSING-PRESET",
    "stopping_rules": "CONTRACT-MISSING-STOPPING-RULES",
    "smoke_test": "CONTRACT-MISSING-SMOKE-TEST",
    "capability_vector": "CONTRACT-MISSING-CAPABILITY-VECTOR",
}


def _empty(value: Any) -> bool:
    return value in (None, "", {}, [], ())


def element_present(blueprint: Mapping[str, Any], element: str) -> bool:
    if element not in blueprint:
        return False
    return not _empty(blueprint.get(element))


def register_blueprint(blueprint: Mapping[str, Any]) -> dict[str, Any]:
    missing: list[str] = []
    rejections: list[str] = []
    for element in REQUIRED_ELEMENTS:
        if not element_present(blueprint, element):
            missing.append(element)
            rejections.append(VIOLATION_ID[element])
    ok = not missing
    return {
        "ok": ok,
        "registered": ok,
        "id": blueprint.get("id"),
        "missing": missing,
        "rejections": rejections,
    }


def omission_failures(blueprint: Mapping[str, Any]) -> dict[str, str]:
    """Map each required element to the token that fires when that element is omitted.

    Called on a complete blueprint. Internally drops one element at a time so
    the tokens are measured, not declared. SILENT means the gate did not fire.
    """
    tokens: dict[str, str] = {}
    for element in REQUIRED_ELEMENTS:
        mutant = copy.deepcopy(dict(blueprint))
        mutant.pop(element, None)
        result = register_blueprint(mutant)
        if result["ok"]:
            tokens[element] = "SILENT"
            continue
        hit = [r for r in result["rejections"] if r == VIOLATION_ID[element]]
        tokens[element] = hit[0] if hit else (result["rejections"][0] if result["rejections"] else "SILENT")
    return tokens
