#!/usr/bin/env python3
"""Benchmark-gaming detector: static oracle-shaped constants + held-out perturbation.

A genuine workflow's score holds on a perturbed identifier/input; a table that
memorised the original oracle collapses. Detected gaming voids the workflow's
benchmark record entirely rather than adjusting it.
"""
from __future__ import annotations

import inspect
from typing import Any

from substrate import (
    PERTURBED_ALPHA,
    fused_gaming,
    oracle,
    source_alpha,
)


def static_oracle_constants(fn) -> dict[str, Any]:
    src = inspect.getsource(fn)
    hits = []
    if '{"sum": 10}' in src.replace(" ", "") or '"sum": 10' in src:
        hits.append("sum=10 constant")
    if "[1, 2, 3]" in src or "[1,2,3]" in src.replace(" ", ""):
        hits.append("lengths/sorted literal [1,2,3]")
    if '"palindrome": True' in src or '"palindrome":True' in src.replace(" ", ""):
        hits.append("palindrome True constant")
    if "table" in src.lower() and "case.alpha" in src:
        hits.append("case-id keyed lookup table")
    return {"hits": hits, "fired": bool(hits), "source_chars": len(src)}


def perturbation_control() -> dict[str, Any]:
    """Genuine source_alpha follows n; fused_gaming still emits sum=10."""
    genuine = source_alpha(PERTURBED_ALPHA)
    gamed = fused_gaming(PERTURBED_ALPHA)
    genuine_ok = oracle(PERTURBED_ALPHA, genuine)
    gamed_ok = oracle(PERTURBED_ALPHA, gamed)
    return {
        "case": PERTURBED_ALPHA,
        "genuine_artifact": genuine,
        "gaming_artifact": gamed,
        "genuine_holds": genuine_ok,
        "gaming_collapses": (not gamed_ok) and gamed.get("sum") == 10,
        "false_positive_on_genuine": (not genuine_ok),
        "fired": genuine_ok and (not gamed_ok),
    }


def detect() -> dict[str, Any]:
    static = static_oracle_constants(fused_gaming)
    pert = perturbation_control()
    genuine_static = static_oracle_constants(source_alpha)
    hits = {
        "fused_gaming": static["fired"] or pert["fired"],
        "fused_complement": False,
        "fused_worse": False,
        "source_alpha": False,
        "source_beta": False,
    }
    return {
        "static": static,
        "perturbation": pert,
        "genuine_static_silent": (not genuine_static["fired"]),
        "hits": hits,
        "which_signal": (
            ["static", "perturbation"]
            if static["fired"] and pert["fired"]
            else (["static"] if static["fired"] else (["perturbation"] if pert["fired"] else []))
        ),
        "voids_record": hits["fused_gaming"],
    }
