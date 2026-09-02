"""Executable mapper controls: known-present COVERED and CLAIMED-NOT-PROVEN.

These fixtures prove the mapper's status rules. They are not authored as
Phase-16 regression tests for the 48 spec classes (that is IMP-0384).
"""
from __future__ import annotations

from mapper import CLAIMED, COVERED, UNCOVERED, map_classes

KNOWN_CLASS = {
    "id": "FC-11324",
    "spec_line": 11324,
    "name": "detector silent in both broken and fixed states",
    "gloss_status": "CONTROL",
    "needles": ["fc-11324", ":11324", "detector silent in both broken and fixed states"],
}

UNPROVEN_CLASS = {
    "id": "FC-11325",
    "spec_line": 11325,
    "name": "mutation survives the test suite",
    "gloss_status": "CONTROL",
    "needles": ["fc-11325", ":11325", "mutation survives the test suite"],
}


def detector(payload: dict) -> bool:
    """Return True when healthy. Mutation sets silent=True and must make this fail."""
    return payload.get("silent") is not True


def run_both_states() -> dict:
    good = detector({"silent": False})
    broken = detector({"silent": True})
    fired = good is True and broken is False
    return {
        "good_passes": good is True,
        "broken_fails": broken is False,
        "fired": fired,
    }


def known_present_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    both = run_both_states()
    tests = [
        {
            "id": "SYN-0047-known-present-detector",
            "path": "command-center/p2-wave/probes/SYN-0047/controls.py",
            "kind": "planted-control",
            "covers": ["FC-11324"],
            "text": "FC-11324 detector silent in both broken and fixed states",
            "has_mutation_record": True,
        }
    ]
    mutations = [
        {
            "test_id": "SYN-0047-known-present-detector",
            "mutation_id": "plant-silent-true",
            "result": "FIRED" if both["fired"] else "SURVIVED",
            "broken_fails": both["broken_fails"],
            "good_passes": both["good_passes"],
            "source": "controls.run_both_states",
        }
    ]
    return [KNOWN_CLASS], tests, mutations


def claimed_unproven_inputs() -> tuple[list[dict], list[dict], list[dict]]:
    tests = [
        {
            "id": "SYN-0047-unproven-mention",
            "path": "command-center/p2-wave/probes/SYN-0047/controls.py",
            "kind": "planted-control",
            "covers": ["FC-11325"],
            "text": "FC-11325 mutation survives the test suite",
            "has_mutation_record": False,
        }
    ]
    return [UNPROVEN_CLASS], tests, []


def assert_known_present() -> dict:
    classes, tests, mutations = known_present_inputs()
    rows = map_classes(classes, tests, mutations, [])
    row = rows[0]
    ok = row["status"] == COVERED and row["test_id"] == "SYN-0047-known-present-detector"
    if not ok:
        raise AssertionError(f"known-present expected COVERED, got {row}")
    return {"pass": True, "status": row["status"], "test_id": row["test_id"], "row": row}


def assert_claimed_not_proven() -> dict:
    classes, tests, mutations = claimed_unproven_inputs()
    rows = map_classes(classes, tests, mutations, [])
    row = rows[0]
    ok = row["status"] == CLAIMED and row["status"] != COVERED and row["status"] != UNCOVERED
    if not ok:
        raise AssertionError(f"unproven mention expected CLAIMED-NOT-PROVEN, got {row}")
    # Negative: the same mention must not be treated as COVERED
    if row["status"] == COVERED:
        raise AssertionError("unproven test was counted COVERED")
    return {"pass": True, "status": row["status"], "test_id": row["test_id"], "row": row}
