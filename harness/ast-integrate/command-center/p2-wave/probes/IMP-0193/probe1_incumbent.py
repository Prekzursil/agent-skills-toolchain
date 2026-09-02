#!/usr/bin/env python3
"""Probe 1: covered goal returns the incumbent; uncovered goal generates.

Catalog tests_required[0]: covered goal returns the incumbent
(both-states: uncovered goal generates).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.constants import NAMED_FAILURE_11331  # noqa: E402
from foundry.generate import generate_from_goal  # noqa: E402
from foundry.scout import load_library  # noqa: E402
from foundry.typed_goal import parse_typed_goal  # noqa: E402

COVERED = (
    "Discover catalog-class workflows and record them as blueprints "
    "without executing them."
)
UNCOVERED = (
    "Compose a three-way tournament that merges execution traces and "
    "benchmarks the fused workflow."
)
INCUMBENT_ID = "wf.catalog-class.discovery-only"
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0193.json"


def main() -> int:
    library = load_library()
    incumbent = next(w for w in library if w["id"] == INCUMBENT_ID)

    covered_goal = parse_typed_goal(COVERED, goal_id="goal.catalog-class.discovery")
    covered = generate_from_goal(covered_goal)
    covered_ok = (
        covered.action == "REFUSE"
        and covered.rebuilt is False
        and covered.workflow is not None
        and covered.workflow["id"] == INCUMBENT_ID
        and json.dumps(covered.workflow, sort_keys=True)
        == json.dumps(incumbent, sort_keys=True)
        and covered.named_failure_avoided == NAMED_FAILURE_11331
        and covered.scout.verdict == "ADOPT"
    )

    uncovered_goal = parse_typed_goal(
        UNCOVERED, goal_id="goal.tournament.merge-benchmark"
    )
    uncovered = generate_from_goal(uncovered_goal)
    library_ids = {w["id"] for w in library}
    uncovered_ok = (
        uncovered.action == "BUILD"
        and uncovered.rebuilt is True
        and uncovered.workflow is not None
        and uncovered.workflow["id"] not in library_ids
        and uncovered.scout.verdict == "BUILD"
    )

    mutant = generate_from_goal(covered_goal, gate=False)
    mutant_rebuilds = (
        mutant.action == "BUILD"
        and mutant.rebuilt is True
        and mutant.workflow is not None
        and mutant.workflow["id"] != INCUMBENT_ID
    )

    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        evidence = doc.get("evidence") or {}
        receipt_ok = (
            str(doc.get("state") or "").upper()
            not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and "SUCCESS:IMP-0193" in text
            and evidence.get("covered_action") == "REFUSE"
            and evidence.get("covered_workflow_id") == INCUMBENT_ID
            and evidence.get("uncovered_action") == "BUILD"
        )

    payload = {
        "probe": "probe1-incumbent",
        "unit_id": "IMP-0193",
        "covered_action": covered.action,
        "covered_workflow_id": None
        if covered.workflow is None
        else covered.workflow["id"],
        "covered_rebuilt": covered.rebuilt,
        "covered_ok": covered_ok,
        "uncovered_action": uncovered.action,
        "uncovered_workflow_id": None
        if uncovered.workflow is None
        else uncovered.workflow["id"],
        "uncovered_rebuilt": uncovered.rebuilt,
        "uncovered_ok": uncovered_ok,
        "mutant_rebuilds_when_ungated": mutant_rebuilds,
        "named_failure": NAMED_FAILURE_11331,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": covered_ok
        and uncovered_ok
        and mutant_rebuilds
        and (receipt_ok is not False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not covered_ok:
        print("FAILED:IMP-0193-probe1 covered goal did not return incumbent")
        return 1
    if not uncovered_ok:
        print("FAILED:IMP-0193-probe1 uncovered goal did not generate")
        return 1
    if not mutant_rebuilds:
        print("FAILED:IMP-0193-probe1 ungated mutant did not rebuild (vacuous gate)")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0193-probe1 receipt does not record both states")
        return 1
    print(
        f"covered={covered.action}:{payload['covered_workflow_id']} "
        f"uncovered={uncovered.action}:{payload['uncovered_workflow_id']} "
        f"mutant_rebuilds={mutant_rebuilds}"
    )
    print("SUCCESS:IMP-0193-probe1 covered returns incumbent; uncovered generates")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
