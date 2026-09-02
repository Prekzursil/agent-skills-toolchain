#!/usr/bin/env python3
"""Deterministic fixtures for SYN-0030 detector controls."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

SHARED_TITLE = "Shared Widget Title"


def _unit(uid: str, title: str = "ok") -> dict[str, Any]:
    return {"id": uid, "title": title}


def _artifact(aid: str, unit_id: str, title: str = "ok") -> dict[str, Any]:
    return {"id": aid, "unit_id": unit_id, "title": title, "path": f"artifacts/{aid}.json"}


def _test(tid: str, unit_id: str, claim_id: str, title: str = "ok") -> dict[str, Any]:
    return {
        "id": tid,
        "unit_id": unit_id,
        "claim_ids": [claim_id],
        "title": title,
        "status": "UNPROVEN",
    }


def _claim(cid: str, unit_id: str, title: str = "ok") -> dict[str, Any]:
    return {"id": cid, "unit_id": unit_id, "title": title, "text": f"claim {cid}"}


def consistent_fixture() -> dict[str, Any]:
    """Known-good: every id is bound in both directions of every adjacent pair."""
    return {
        "catalog": {
            "work_units": [
                _unit("U-ALPHA", "Alpha"),
                _unit("U-BETA", "Beta"),
            ]
        },
        "artifact": {
            "artifacts": [
                _artifact("A-ALPHA", "U-ALPHA", "Alpha"),
                _artifact("A-BETA", "U-BETA", "Beta"),
            ]
        },
        "test": {
            "tests": [
                _test("T-ALPHA", "U-ALPHA", "C-ALPHA", "Alpha"),
                _test("T-BETA", "U-BETA", "C-BETA", "Beta"),
            ]
        },
        "claim": {
            "claims": [
                _claim("C-ALPHA", "U-ALPHA", "Alpha"),
                _claim("C-BETA", "U-BETA", "Beta"),
            ]
        },
    }


def plant_catalog_orphan() -> dict[str, Any]:
    """Extra catalog unit with no artifact / test / claim row."""
    docs = deepcopy(consistent_fixture())
    docs["catalog"]["work_units"].append(_unit("U-PLANT-CATALOG", "Planted catalog orphan"))
    return docs


def plant_artifact_orphan() -> dict[str, Any]:
    """Extra artifact whose unit_id is not a catalog id."""
    docs = deepcopy(consistent_fixture())
    docs["artifact"]["artifacts"].append(
        _artifact("A-PLANT-ARTIFACT", "U-NOWHERE", "Planted artifact orphan")
    )
    return docs


def plant_test_orphan() -> dict[str, Any]:
    """Extra test bound to a real unit but to no existing claim."""
    docs = deepcopy(consistent_fixture())
    docs["test"]["tests"].append(
        _test("T-PLANT-TEST", "U-ALPHA", "C-NOWHERE", "Planted test orphan")
    )
    return docs


def plant_claim_orphan() -> dict[str, Any]:
    """Extra claim bound to a real unit but covered by no test."""
    docs = deepcopy(consistent_fixture())
    docs["claim"]["claims"].append(
        _claim("C-PLANT-CLAIM", "U-BETA", "Planted claim orphan")
    )
    return docs


def title_collision_fixture() -> dict[str, Any]:
    """Two units share a title; only U-KEEP has artifact/test/claim.

    An id join reports U-ORPHAN. A title join hides it.
    """
    return {
        "catalog": {
            "work_units": [
                _unit("U-KEEP", SHARED_TITLE),
                _unit("U-ORPHAN", SHARED_TITLE),
            ]
        },
        "artifact": {
            "artifacts": [_artifact("A-KEEP", "U-KEEP", SHARED_TITLE)]
        },
        "test": {
            "tests": [_test("T-KEEP", "U-KEEP", "C-KEEP", SHARED_TITLE)]
        },
        "claim": {
            "claims": [_claim("C-KEEP", "U-KEEP", SHARED_TITLE)]
        },
    }


PLANTS = {
    "catalog": {
        "builder": plant_catalog_orphan,
        "planted_id": "U-PLANT-CATALOG",
        "expected_direction": "catalog_without_artifact",
        "registry": "catalog",
    },
    "artifact": {
        "builder": plant_artifact_orphan,
        "planted_id": "A-PLANT-ARTIFACT",
        "expected_direction": "artifact_without_catalog",
        "registry": "artifact",
    },
    "test": {
        "builder": plant_test_orphan,
        "planted_id": "T-PLANT-TEST",
        "expected_direction": "test_without_claim",
        "registry": "test",
    },
    "claim": {
        "builder": plant_claim_orphan,
        "planted_id": "C-PLANT-CLAIM",
        "expected_direction": "claim_without_test",
        "registry": "claim",
    },
}
