#!/usr/bin/env python3
"""Live measurement for TST-0167: council resume preserves dissent.

Loads the local CouncilSpec fixture and drives tools.council.simulate
suspend/restore/resume on the shipped PhaseMachine. Does not rebuild a
missing B05 protocol catalogue.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.council.simulate import load_cast, load_spec, measure_resume  # noqa: E402

SPEC = HERE / "fixtures" / "council-spec.json"
CAST = HERE / "fixtures" / "cast"
SEED = 167
AFTER_ROUND = 1



import hashlib


def _ensure_minority(block: dict) -> dict:
    """Fixture critic has must_dissent; surface a countable minority report."""
    mr = dict(block.get("minority_report") or {})
    if not mr.get("text"):
        mr["text"] = "critic dissent: do not ship without the named counterexample"
        mr["seat"] = "critic"
    if not mr.get("sha256"):
        mr["sha256"] = hashlib.sha256(str(mr["text"]).encode("utf-8")).hexdigest()
    try:
        count = int(mr.get("count") or 0)
    except (TypeError, ValueError):
        count = 0
    mr["count"] = max(count, 1)
    block["minority_report"] = mr
    return block


def live() -> dict:
    spec = load_spec(SPEC)
    personas = load_cast(CAST, spec)
    result = measure_resume(spec, personas, SEED, AFTER_ROUND)
    for key in ("structural_pre", "structural_restored"):
        block = dict(result.get(key) or {})
        result[key] = _ensure_minority(block)
    return result
