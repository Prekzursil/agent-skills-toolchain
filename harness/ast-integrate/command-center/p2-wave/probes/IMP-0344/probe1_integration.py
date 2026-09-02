#!/usr/bin/env python3
"""Probe 1: council invoked as a workflow stage; decision consumed downstream.

Invariant (spec 10727): the composed run has one scheduler and one event log.
A planted second EventLog is detected (both-states). AST sweep confirms
CouncilBridge.invoke does not construct a control plane.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO))

import scenario as S  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0344.json"


def main() -> int:
    integration = S.run_integration()
    planted = S.run_planted_second_plane()
    ast_inv = S.run_ast_invariant()
    taxonomy = S.run_out_of_taxonomy_policy()
    print(
        json.dumps(
            {
                "integration": integration,
                "planted_second_plane": planted,
                "ast_invariant": ast_inv,
                "out_of_taxonomy": taxonomy,
            },
            sort_keys=True,
            default=str,
        )[:4000]
    )
    if not integration["ok"]:
        print("FAILED:IMP-0344-probe1 integration: council stage did not compose")
        return 1
    census = integration["census"]
    if census.get("event_log_count") != 1 or census.get("scheduler_count") != 1:
        print(
            "FAILED:IMP-0344-probe1 census not single-plane "
            f"logs={census.get('event_log_count')} sched={census.get('scheduler_count')}"
        )
        return 1
    if integration.get("acted_on") != "approve":
        print(f"FAILED:IMP-0344-probe1 downstream did not consume decision: {integration.get('acted_on')}")
        return 1
    if not planted["ok"]:
        print("FAILED:IMP-0344-probe1 planted second EventLog was not detected")
        return 1
    if planted["census"].get("event_log_count") != 2:
        print(
            "FAILED:IMP-0344-probe1 planted census "
            f"event_log_count={planted['census'].get('event_log_count')} want=2"
        )
        return 1
    if not ast_inv["ok"]:
        print(f"FAILED:IMP-0344-probe1 AST hits {ast_inv['hits']}")
        return 1
    if not taxonomy["ok"]:
        print("FAILED:IMP-0344-probe1 out-of-taxonomy policy did not fail closed")
        return 1
    if not ART.is_file():
        print("FAILED:IMP-0344-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:IMP-0344-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:IMP-0344" not in ART.read_text(encoding="utf-8"):
        print("FAILED:IMP-0344-probe1 sentinel absent")
        return 1
    if doc.get("unit_id") != "IMP-0344":
        print(f"FAILED:IMP-0344-probe1 unit_id {doc.get('unit_id')}")
        return 1
    print("SUCCESS:IMP-0344-probe1 integration + single-plane invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
