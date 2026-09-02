#!/usr/bin/env python3
"""One forcing case per unused vocabulary value.

Plants do not pre-set `classification`. A pre-labelled plant would not
test whether the classifier can emit the value.
"""
from __future__ import annotations

from typing import Any

from classifier import UNUSED_DECLARED, classify

CONTROL_PLANE = "ast-integrate"


def plant_for(value: str) -> dict[str, Any]:
    if value == "REJECT":
        return {
            "id": "plant-REJECT",
            "does": "out-of-scope credential harvester presented as a workflow",
            "harmful": True,
            "license": "MIT",
            "runtime": CONTROL_PLANE,
            "control_plane": CONTROL_PLANE,
        }
    if value == "CLEAN-ROOM-REIMPLEMENT":
        return {
            "id": "plant-CLEAN-ROOM-REIMPLEMENT",
            "does": "useful mechanism whose source license forbids copying",
            "wanted": True,
            "license": "INCOMPATIBLE",
            "runtime": CONTROL_PLANE,
            "control_plane": CONTROL_PLANE,
        }
    if value == "TRANSLATE":
        return {
            "id": "plant-TRANSLATE",
            "does": "otherwise-adoptable workflow bound to a foreign runtime",
            "license": "MIT",
            "runtime": "foreign-control-plane",
            "control_plane": CONTROL_PLANE,
        }
    if value == "REBUILD-FROM-SPEC":
        return {
            "id": "plant-REBUILD-FROM-SPEC",
            "does": "wanted workflow whose source is non-transferable",
            "license": "MIT",
            "runtime": CONTROL_PLANE,
            "control_plane": CONTROL_PLANE,
            "spec_available": True,
            "rebuild_cheaper": True,
            "source_non_transferable": True,
        }
    if value == "COMPOSE":
        return {
            "id": "plant-COMPOSE",
            "does": "goal satisfied only by joining two existing workflows",
            "license": "MIT",
            "runtime": CONTROL_PLANE,
            "control_plane": CONTROL_PLANE,
            "compose_parts": ["wf-scout", "wf-forge"],
        }
    if value == "GENERALIZE":
        return {
            "id": "plant-GENERALIZE",
            "does": "narrow instance that should be lifted to a general form",
            "license": "MIT",
            "runtime": CONTROL_PLANE,
            "control_plane": CONTROL_PLANE,
            "generalize_from": "wf-narrow-vendor-lock-helper",
        }
    raise KeyError(f"no forcing case for {value}")


def run_plants(
    *, skip_values: frozenset[str] | set[str] = frozenset()
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value in UNUSED_DECLARED:
        rec = plant_for(value)
        if "classification" in rec:
            raise AssertionError("plant must not pre-label classification")
        emitted = classify(rec, skip_values=skip_values)
        rows.append(
            {
                "value": value,
                "candidate_id": rec["id"],
                "emitted": emitted["classification"],
                "expected": value,
                "reachable": emitted["classification"] == value,
                "rule_id": emitted["rule_id"],
            }
        )
    return rows


def blind_spots(rows: list[dict[str, Any]] | None = None) -> list[str]:
    rows = rows if rows is not None else run_plants()
    return [r["value"] for r in rows if not r["reachable"]]


run_plants = run_plants
blind_spots = blind_spots
