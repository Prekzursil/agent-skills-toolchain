#!/usr/bin/env python3
"""Probe 2: generated workflow passes schema + static validation with no repair.

Catalog tests_required[1]. Also rejects a broken workflow (both-states).
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from foundry.generate import generate_from_goal, synthesize  # noqa: E402
from foundry.scout import load_library  # noqa: E402
from foundry.typed_goal import parse_typed_goal  # noqa: E402
from foundry.validate import is_valid, validate_workflow  # noqa: E402

UNCOVERED = (
    "Compose a three-way tournament that merges execution traces and "
    "benchmarks the fused workflow."
)
RECEIPT = REPO / "command-center" / "receipts" / "IMP-0193.json"


def main() -> int:
    goal = parse_typed_goal(UNCOVERED, goal_id="goal.tournament.merge-benchmark")
    raw = synthesize(goal)
    raw_errors = validate_workflow(raw)
    raw_ok = not raw_errors and is_valid(raw)

    result = generate_from_goal(goal)
    generated = result.workflow
    gen_errors = validate_workflow(generated) if generated is not None else [{"id": "MISSING"}]
    gen_ok = (
        result.action == "BUILD"
        and generated is not None
        and not gen_errors
        and is_valid(generated)
    )

    broken = copy.deepcopy(load_library()[0])
    broken["stages"].append(copy.deepcopy(broken["stages"][0]))
    del broken["stopping"]
    broken_errors = validate_workflow(broken)
    broken_ids = {e["id"] for e in broken_errors}
    broken_rejected = bool(broken_errors) and not is_valid(broken)

    receipt_ok = None
    if RECEIPT.is_file() and RECEIPT.stat().st_size > 0:
        text = RECEIPT.read_text(encoding="utf-8")
        doc = json.loads(text)
        evidence = doc.get("evidence") or {}
        receipt_ok = (
            str(doc.get("state") or "").upper()
            not in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}
            and "SUCCESS:IMP-0193" in text
            and evidence.get("generated_schema_errors") == []
            and evidence.get("generated_static_valid") is True
        )

    payload = {
        "probe": "probe2-schema-static",
        "unit_id": "IMP-0193",
        "synthesize_direct_errors": raw_errors,
        "synthesize_valid_without_repair": raw_ok,
        "generate_action": result.action,
        "generate_errors": gen_errors,
        "generate_valid": gen_ok,
        "broken_error_ids": sorted(broken_ids),
        "broken_rejected": broken_rejected,
        "receipt_present": RECEIPT.is_file(),
        "receipt_ok": receipt_ok,
        "pass": raw_ok and gen_ok and broken_rejected and (receipt_ok is not False),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not raw_ok:
        print("FAILED:IMP-0193-probe2 synthesize required repair")
        return 1
    if not gen_ok:
        print("FAILED:IMP-0193-probe2 generated workflow failed validation")
        return 1
    if not broken_rejected:
        print("FAILED:IMP-0193-probe2 broken workflow was accepted")
        return 1
    if receipt_ok is False:
        print("FAILED:IMP-0193-probe2 receipt does not record schema-valid generation")
        return 1
    print(
        f"synthesize_valid={raw_ok} generate_valid={gen_ok} "
        f"broken_rejected={broken_rejected}"
    )
    print("SUCCESS:IMP-0193-probe2 generated workflow schema+static valid; broken rejected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
