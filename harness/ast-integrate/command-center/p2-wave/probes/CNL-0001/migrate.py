#!/usr/bin/env python3
"""v1 charter <-> v2 charter round-trip. Only `stopping` changes shape."""
from __future__ import annotations

import json
from copy import deepcopy

from fixtures import SHAPE_CHANGE_PROPERTY


def canonical(doc: dict) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def migrate_v1_to_v2(charter: dict) -> dict:
    out = deepcopy(charter)
    stopping = out.get(SHAPE_CHANGE_PROPERTY)
    if not isinstance(stopping, str) or not stopping:
        raise ValueError("v1 stopping must be a non-empty string to migrate")
    out[SHAPE_CHANGE_PROPERTY] = {"mode": "expression", "expression": stopping}
    return out


def migrate_v2_to_v1(charter: dict) -> dict:
    out = deepcopy(charter)
    stopping = out.get(SHAPE_CHANGE_PROPERTY)
    if not isinstance(stopping, dict) or stopping.get("mode") != "expression":
        raise ValueError("v2 charter stopping must be {mode:expression, expression}")
    expr = stopping.get("expression")
    if not isinstance(expr, str) or not expr:
        raise ValueError("v2 expression missing")
    out[SHAPE_CHANGE_PROPERTY] = expr
    return out


def round_trip(charter_v1: dict) -> dict:
    v2 = migrate_v1_to_v2(charter_v1)
    back = migrate_v2_to_v1(v2)
    return {
        "byte_identical": canonical(charter_v1) == canonical(back),
        "v1_canonical": canonical(charter_v1),
        "back_canonical": canonical(back),
        "v2": v2,
        "back": back,
    }


def refuse_unwrap_caps(stopping: dict) -> dict:
    """Negative control: catalogue caps stopping must NOT unwrap to a v1 string."""
    fake = {"stopping": deepcopy(stopping)}
    try:
        migrate_v2_to_v1(fake)
        return {"refused": False, "reason": "unwrap-accepted-caps"}
    except ValueError as exc:
        return {"refused": True, "reason": str(exc)}
