#!/usr/bin/env python3
"""Visible benchmark cases plus held-out identifier/input perturbations.

The visible slice is what a gaming workflow can memorise. The hold-out slice
keeps the same operator but changes both the case id and the operands, so a
lookup keyed on the visible id (or a copied gold artifact) collapses while a
compute-from-operands workflow continues to satisfy the strong oracle.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
FIX = HERE / "fixtures" / "workflows"

# Frozen, versioned collapse rule. Not tuned per run.
THRESHOLD_ID = "WFA-0116.perturbation-collapse.v1"
VISIBLE_PASS_MIN = 0.75
HOLDOUT_PASS_MAX = 0.25
HOLDOUT_NONCE = "holdout-k7"
A_SHIFT = 11
B_SHIFT = 3

VISIBLE_CASES: list[dict[str, Any]] = [
    {"id": "case-add-01", "op": "add", "a": 4, "b": 5},
    {"id": "case-mul-02", "op": "mul", "a": 6, "b": 7},
    {"id": "case-xor-03", "op": "xor", "a": 12, "b": 5},
    {"id": "case-cat-04", "op": "cat", "a": 3, "b": 8},
]


def perturb(case: dict[str, Any], nonce: str = HOLDOUT_NONCE) -> dict[str, Any]:
    return {
        "id": f"{case['id']}-{nonce}",
        "op": case["op"],
        "a": int(case["a"]) + A_SHIFT,
        "b": int(case["b"]) + B_SHIFT,
    }


def holdout_cases() -> list[dict[str, Any]]:
    return [perturb(c) for c in VISIBLE_CASES]


def visible_ids() -> list[str]:
    return [str(c["id"]) for c in VISIBLE_CASES]


def load_specs() -> list[dict[str, Any]]:
    specs: list[dict[str, Any]] = []
    for path in sorted(FIX.glob("*.json")):
        spec = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or not spec.get("id"):
            raise ValueError(f"invalid workflow spec {path}")
        spec = dict(spec)
        spec["_definition_path"] = str(path.relative_to(REPO))
        spec["_definition_file"] = path.name
        specs.append(spec)
    if len(specs) < 6:
        raise ValueError(f"expected >=6 workflow specs, got {len(specs)}")
    return specs
