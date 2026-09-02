"""Research blueprint required-element contract."""
from __future__ import annotations

from typing import Any

REQUIRED_ELEMENTS = (
    ("workflow", "E-WORKFLOW"),
    ("declared_parameters", "E-PARAMS"),
    ("stopping_rules", "E-STOP"),
    ("example", "E-EXAMPLE"),
    ("tier", "E-TIER"),
    ("id", "E-ID"),
)


def register(blueprint: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(blueprint, dict):
        return {"ok": False, "code": "E-TYPE"}
    for key, code in REQUIRED_ELEMENTS:
        if key not in blueprint:
            return {"ok": False, "code": code}
    return {"ok": True, "code": "OK"}
