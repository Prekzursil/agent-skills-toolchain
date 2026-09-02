#!/usr/bin/env python3
"""Tests for foundry.generate / foundry.validate / foundry.scout (IMP-0193).

Runs under pytest or directly (``python3 tools/foundry/tests/test_generate.py``),
printing ``SUCCESS:foundry-generate-tests`` and exiting 0 when every case passes.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[2]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from foundry.constants import NAMED_FAILURE_11331, VIOLATION_IDS  # noqa: E402
from foundry.generate import generate_from_goal, synthesize  # noqa: E402
from foundry.scout import load_library, scout  # noqa: E402
from foundry.typed_goal import parse_typed_goal  # noqa: E402
from foundry.validate import is_valid, param_errors, validate_workflow  # noqa: E402

COVERED = (
    "Discover catalog-class workflows and record them as blueprints "
    "without executing them."
)
UNCOVERED = (
    "Compose a three-way tournament that merges execution traces and "
    "benchmarks the fused workflow."
)
INCUMBENT_ID = "wf.catalog-class.discovery-only"


def test_library_rows_are_valid_workflows() -> None:
    library = load_library()
    assert any(w["id"] == INCUMBENT_ID for w in library)
    for row in library:
        assert validate_workflow(row) == [], row["id"]


def test_covered_goal_refuses_and_returns_incumbent_unchanged() -> None:
    goal = parse_typed_goal(COVERED, goal_id="goal.catalog-class.discovery")
    result = generate_from_goal(goal)
    incumbent = next(w for w in load_library() if w["id"] == INCUMBENT_ID)
    assert result.action == "REFUSE" and result.rebuilt is False
    assert json.dumps(result.workflow, sort_keys=True) == json.dumps(incumbent, sort_keys=True)
    assert result.named_failure_avoided == NAMED_FAILURE_11331
    assert result.scout.verdict == "ADOPT" and scout(goal).adopted_id == INCUMBENT_ID


def test_uncovered_goal_builds_schema_valid_workflow() -> None:
    goal = parse_typed_goal(UNCOVERED, goal_id="goal.tournament.merge-benchmark")
    result = generate_from_goal(goal)
    assert result.action == "BUILD" and result.rebuilt is True
    assert result.workflow is not None
    assert result.workflow["id"] not in {w["id"] for w in load_library()}
    assert validate_workflow(result.workflow) == []
    assert is_valid(synthesize(goal))
    assert result.scout.verdict == "BUILD"


def test_synthesize_is_deterministic_and_chains_stages() -> None:
    goal = parse_typed_goal(UNCOVERED, goal_id="goal.tournament.merge-benchmark")
    first, second = synthesize(goal), synthesize(goal)
    assert first == second
    ids = [s["id"] for s in first["stages"]]
    assert ids[:2] == ["compose", "tournament"]
    for prev, stage in zip(first["stages"], first["stages"][1:]):
        assert stage["depends_on"] == [prev["id"]]
        assert stage["inputs"] == prev["outputs"]


def test_ungated_mutant_rebuilds_covered_goal() -> None:
    goal = parse_typed_goal(COVERED, goal_id="goal.catalog-class.discovery")
    mutant = generate_from_goal(goal, gate=False)
    assert mutant.action == "BUILD" and mutant.rebuilt is True
    assert mutant.workflow is not None and mutant.workflow["id"] != INCUMBENT_ID


def test_broken_workflow_is_rejected_with_closed_ids() -> None:
    broken = copy.deepcopy(load_library()[0])
    broken["stages"].append(copy.deepcopy(broken["stages"][0]))
    del broken["stopping"]
    errors = validate_workflow(broken)
    ids = {e["id"] for e in errors}
    assert not is_valid(broken)
    assert "WF-STAGE-DUPLICATE-ID" in ids and "WF-SCHEMA-REQUIRED-MISSING" in ids
    assert ids <= VIOLATION_IDS


def test_param_errors_cover_required_type_enum_and_undeclared() -> None:
    base = load_library()[0]
    cases = [
        ({"schema": {"repo": {"type": "string", "required": True}}, "values": {}}, "WF-PARAM-REQUIRED-MISSING"),
        ({"schema": {"repo": {"type": "string", "required": True}}, "values": {"repo": 1}}, "WF-PARAM-TYPE-MISMATCH"),
        (
            {"schema": {"mode": {"type": "string", "required": True, "enum": ["a", "b"]}}, "values": {"mode": "z"}},
            "WF-PARAM-ENUM",
        ),
        ({"schema": {"repo": {"type": "string", "required": True}}, "values": {"repo": ".", "x": 1}}, "WF-PARAM-UNDECLARED"),
    ]
    for spec, expected in cases:
        doc = copy.deepcopy(base)
        doc["params"] = spec
        assert [e["id"] for e in param_errors(doc)] == [expected], (spec, expected)


def test_static_checks_catch_unknown_dependency_and_cycle() -> None:
    doc = copy.deepcopy(load_library()[0])
    doc["stages"][0]["depends_on"] = [doc["stages"][1]["id"]]
    ids = {e["id"] for e in validate_workflow(doc)}
    assert "WF-STAGE-CYCLE" in ids
    doc = copy.deepcopy(load_library()[0])
    doc["stages"][1]["depends_on"] = ["ghost"]
    ids = {e["id"] for e in validate_workflow(doc)}
    assert "WF-STAGE-UNKNOWN-DEPENDENCY" in ids


def main() -> int:
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith("test_") and callable(obj)]
    failed = 0
    for test in tests:
        try:
            test()
            print(f"ok {test.__name__}")
        except Exception as exc:  # noqa: BLE001 - report every failing case
            failed += 1
            print(f"FAIL {test.__name__}: {exc!r}")
    if failed:
        print(f"FAILED:foundry-generate-tests {failed}/{len(tests)} failing")
        return 1
    print(f"SUCCESS:foundry-generate-tests {len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
