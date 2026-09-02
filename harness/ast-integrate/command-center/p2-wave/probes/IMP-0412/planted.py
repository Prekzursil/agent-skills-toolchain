#!/usr/bin/env python3
"""Planted controls required by IMP-0412 tests_required.

Injected into a copy of the catalog, never written back to WORK-UNIT-CATALOG.json.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

REWORD_TARGET = (
    "Write a fingerprint of the normalised work unit target-text together with "
    "its input-set so the same mechanism, dispatched twice under different "
    "identifiers, is caught at claim-time. Precise question: when applied to "
    "the assembled 2048 unit catalogue, how many pairs collide; is every "
    "collision a genuine duplicate or a false-positive?"
)

DISTINCT_A_TARGET = (
    "Implement a fingerprint over the normalized work-unit target text plus "
    "its input set so duplicate dispatch is caught at claim time."
)

DISTINCT_B_TARGET = (
    "Implement a merger that assembles catalog slices into one work-unit "
    "catalog and refuses duplicate ids and unfilled index gaps."
)

DISTINCT_INPUTS = [
    "command-center/WORK-UNIT-CATALOG.json",
    "command-center/catalog-slices/*.json",
]

EXACT_ID = "PLANT-EXACT-0412"
REWORD_ID = "PLANT-REWORD-0412"
DISTINCT_A_ID = "PLANT-DIST-A"
DISTINCT_B_ID = "PLANT-DIST-B"


def _copy_unit(unit: Mapping[str, Any], new_id: str, **overrides: Any) -> dict[str, Any]:
    cloned = deepcopy(dict(unit))
    cloned["id"] = new_id
    cloned.update(overrides)
    return cloned


def donor_from_catalog(units: Sequence[Mapping[str, Any]], donor_id: str = "IMP-0412") -> dict[str, Any]:
    for unit in units:
        if unit.get("id") == donor_id:
            return deepcopy(dict(unit))
    raise KeyError(f"donor {donor_id} missing from catalog")


def inject_duplicates(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One exact clone and one reworded clone of IMP-0412."""
    donor = donor_from_catalog(units)
    exact = _copy_unit(donor, EXACT_ID)
    reword = _copy_unit(donor, REWORD_ID, question_or_target=REWORD_TARGET)
    return [deepcopy(dict(u)) for u in units] + [exact, reword]


def inject_distinct(units: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Two genuinely different mechanisms that share catalog vocabulary and inputs."""
    a = {
        "id": DISTINCT_A_ID,
        "title": "Planted distinct A: duplicate fingerprint",
        "question_or_target": DISTINCT_A_TARGET,
        "inputs": list(DISTINCT_INPUTS),
    }
    b = {
        "id": DISTINCT_B_ID,
        "title": "Planted distinct B: slice merger",
        "question_or_target": DISTINCT_B_TARGET,
        "inputs": list(DISTINCT_INPUTS),
    }
    return [deepcopy(dict(u)) for u in units] + [a, b]


def ghost_claim(units: Sequence[Mapping[str, Any]], ghost_id: str = "IMP-GHOST-0412") -> dict[str, Any]:
    """A second dispatch of IMP-0412 under a different id, for claim-time check."""
    return _copy_unit(donor_from_catalog(units), ghost_id)
