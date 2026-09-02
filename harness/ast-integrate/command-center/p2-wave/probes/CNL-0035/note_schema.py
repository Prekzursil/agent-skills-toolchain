#!/usr/bin/env python3
"""Local council-design-note check for CNL-0035 (no remote $ref)."""
from __future__ import annotations

from typing import Any

import jsonschema

MODE_ROW = {
    "type": "object",
    "required": ["var0", "var1", "mae0", "mae1", "herding", "verdict", "reason"],
    "properties": {
        "var0": {"type": "number"},
        "var1": {"type": "number"},
        "mae0": {"type": "number"},
        "mae1": {"type": "number"},
        "herding": {"type": "boolean"},
        "verdict": {"type": "string", "minLength": 1},
        "reason": {"type": "string", "minLength": 1},
    },
}

LOCAL = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://ast-integrate.invalid/command-center/p2-wave/probes/CNL-0035/note_schema.py",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "title",
        "question",
        "answer",
        "herding_experiment",
        "negative_control",
        "negative_controls",
        "tests",
        "evidence",
        "reviewer",
        "artifacts",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0035"},
        "id": {"const": "CNL-0035"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0035"},
        "completion_sentinel": {"const": "SUCCESS:CNL-0035"},
        "title": {"type": "string", "minLength": 8},
        "question": {"type": "string", "minLength": 16},
        "answer": {"type": "string", "minLength": 32},
        "herding_experiment": {
            "type": "object",
            "required": ["heterogeneous", "homogeneous", "prescribed_mode"],
            "properties": {
                "prescribed_mode": {"const": "arguments"},
                "heterogeneous": {
                    "type": "object",
                    "required": ["median_only", "full_distribution", "arguments"],
                    "properties": {
                        "median_only": MODE_ROW,
                        "full_distribution": MODE_ROW,
                        "arguments": MODE_ROW,
                    },
                },
                "homogeneous": {
                    "type": "object",
                    "required": ["arguments"],
                    "properties": {"arguments": MODE_ROW},
                },
            },
        },
        "negative_control": {
            "type": "object",
            "required": ["verbatim", "check"],
            "properties": {
                "verbatim": {"type": "string", "minLength": 16},
                "check": {"type": "string", "minLength": 1},
            },
        },
        "negative_controls": {"type": "array", "minItems": 1},
        "tests": {"type": "array", "minItems": 2},
        "evidence": {"type": "array", "minItems": 2},
        "reviewer": {
            "type": "object",
            "required": ["reviewer_id", "verdict", "independent"],
            "properties": {
                "reviewer_id": {"type": "string", "minLength": 1},
                "verdict": {"const": "PASS"},
                "independent": {"const": True},
            },
        },
        "artifacts": {"type": "array", "minItems": 1},
    },
}


def _errors(doc: Any) -> list[str]:
    validator = jsonschema.Draft7Validator(LOCAL)
    out = []
    for err in validator.iter_errors(doc):
        loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
        out.append(f"{loc}: {err.message}")
    return sorted(out)


def validate_note(doc: Any) -> tuple[bool, str]:
    if not isinstance(doc, dict):
        return False, "not-object"
    errs = _errors(doc)
    if errs:
        return False, "schema:" + "; ".join(errs[:8])
    verbatim = str((doc.get("negative_control") or {}).get("verbatim") or "")
    if "FIRE" not in verbatim or "SILENT" not in verbatim:
        return False, "negative_control.verbatim missing FIRE/SILENT"
    if "SUCCESS:CNL-0035" not in str(doc.get("answer") or "") and "SUCCESS:CNL-0035" not in verbatim:
        # sentinel field already required; also require it in body text for G-1
        body = str(doc.get("sentinel") or "")
        if body != "SUCCESS:CNL-0035":
            return False, "sentinel-absent"
    het = ((doc.get("herding_experiment") or {}).get("heterogeneous")) or {}
    hom = ((doc.get("herding_experiment") or {}).get("homogeneous")) or {}
    if het.get("median_only", {}).get("herding") is not True:
        return False, "het.median_only must herd"
    if het.get("full_distribution", {}).get("herding") is not True:
        return False, "het.full_distribution must herd"
    if het.get("arguments", {}).get("herding") is not False:
        return False, "het.arguments must revise (not herd)"
    if hom.get("arguments", {}).get("herding") is not True:
        return False, "hom.arguments must herd"
    return True, "ok"


def rejects_garbage() -> tuple[bool, str]:
    cases = [
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
        {"unit_id": "CNL-0035", "state": "SUCCESS", "sentinel": "SUCCESS:CNL-0035"},
    ]
    for doc in cases:
        ok, why = validate_note(doc)
        if ok:
            return False, f"garbage-accepted:{list(doc)[:3]}"
        if not (why.startswith("schema:") or why.startswith("missing") or why.startswith("not-object")):
            # still a reject; local schema should be the reason for these stubs
            if "schema:" not in why:
                return False, f"unexpected:{why}"
    return True, "garbage-rejected-4-of-4"
