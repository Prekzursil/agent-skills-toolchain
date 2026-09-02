#!/usr/bin/env python3
"""Blind brief builder (CNF-0005 contract, in-unit).

Hands the confirmer the claim ids, mechanism texts, and the tests.
Strips original verdict, confidence, summary, duplicate_of, and
implementer conclusion. A leak detector walks keys and text.
"""
from __future__ import annotations

import copy
import json
from typing import Any

LEAK_KEYS = frozenset(
    {
        "original_verdict",
        "confidence",
        "confidence_band",
        "conclusion",
        "implementer_conclusion",
        "summary",
        "summary_table",
        "duplicate_of",
        "disagreement_class",
        "sealed",
        "receipt_prose",
    }
)

TASK = (
    "Decide whether these two mechanism statements describe the same "
    "mechanism (equivalent) or two different mechanisms. Do not use any "
    "prior collapse decision. Return DUPLICATE or DISTINCT."
)

TESTS = [
    "the re-decider must not see the original verdict",
    "a mechanical similarity score is computed alongside the judgement",
    "where mechanical and judgement differ, mechanical is reported first",
]


def _walk_keys(obj: Any, found: list[str], path: str = "") -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            nk = str(k).lower().replace("-", "_")
            here = f"{path}{k}"
            if nk in LEAK_KEYS:
                found.append(here)
            _walk_keys(v, found, here + ".")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _walk_keys(v, found, f"{path}{i}.")


def leak_keys(brief: dict) -> list[str]:
    found: list[str] = []
    _walk_keys(brief, found)
    blob = json.dumps(brief, sort_keys=True)
    for k in LEAK_KEYS:
        needle = f'"{k}"'
        if needle in blob.lower().replace("-", "_"):
            # json.dumps keeps original key spelling; check both
            pass
    lowered = blob.lower().replace("-", "_")
    for k in LEAK_KEYS:
        if f'"{k}"' in lowered:
            tag = f"text:{k}"
            if tag not in found and k not in {p.split(".")[-1].lower().replace("-", "_") for p in found}:
                found.append(tag)
    return found


def build_brief(edge_id: str, left: dict, right: dict) -> dict:
    """Build a brief from claim records. Only id/family/mechanism pass through."""
    def side(c: dict) -> dict:
        return {
            "id": c["id"],
            "family": c.get("family"),
            "mechanism": c["mechanism"],
            "source_path": (c.get("source_lineage") or {}).get("path"),
            "source_unit": (c.get("source_lineage") or {}).get("unit_id"),
        }

    brief = {
        "edge_id": edge_id,
        "task": TASK,
        "tests": list(TESTS),
        "left": side(left),
        "right": side(right),
    }
    leaks = leak_keys(brief)
    if leaks:
        raise SystemExit(f"FAILED:CNF-0067 brief-builder leaked {leaks}")
    return brief


def inject_conclusion(brief: dict, verdict: str = "DUPLICATE") -> dict:
    """Deliberate leak control: plant an implementer conclusion in a copy."""
    planted = copy.deepcopy(brief)
    planted["original_verdict"] = verdict
    planted["implementer_conclusion"] = f"prior collapse marked this {verdict}"
    planted["confidence_band"] = "high"
    return planted
