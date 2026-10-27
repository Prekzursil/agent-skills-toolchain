#!/usr/bin/env python3
"""TST-0180 measured layer: case-collision detector + clean emitter for manifests.

A case-insensitive parser treats "Hooks" and "hooks" as one key (last-wins);
the validator must reject such documents naming both, and the emitter must
never produce case-colliding keys.
"""
from __future__ import annotations

import json


class CaseCollisionError(Exception):
    def __init__(self, message: str, colliding: list[str] | None = None):
        super().__init__(message)
        self.colliding = colliding or []


def find_case_collisions(keys) -> list[tuple[str, str]]:
    seen: dict[str, str] = {}
    out: list[tuple[str, str]] = []
    for k in keys:
        f = k.casefold()
        if f in seen and seen[f] != k:
            out.append((seen[f], k))
        else:
            seen.setdefault(f, k)
    return out


def validate_strict(text: str) -> dict:
    doc = json.loads(text)
    if not isinstance(doc, dict):
        raise CaseCollisionError("manifest must be a JSON object")
    collisions = find_case_collisions(doc.keys())
    if collisions:
        names = ", ".join("%r vs %r" % c for c in collisions)
        raise CaseCollisionError(
            "case-insensitive key collision under a case-folding parser: " + names,
            colliding=[k for c in collisions for k in c],
        )
    return doc


def emit_safe(fields: dict) -> str:
    collisions = find_case_collisions(fields.keys())
    if collisions:
        raise CaseCollisionError("emitter refuses case-colliding keys")
    return json.dumps(fields, sort_keys=True)
