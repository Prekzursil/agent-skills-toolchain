#!/usr/bin/env python3
"""IMP-0147 probe 1: migrated pre-Phase-7 plan equals hand-written current twin."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.migrate import migrate  # noqa: E402
from agentspec.plan import compile_plan  # noqa: E402
from agentspec.spec import CURRENT_SPEC_VERSION, SPEC_VERSION_PRE_PHASE7  # noqa: E402
from agentspec.validate import VIOLATION_SPEC_VERSION_UNSUPPORTED, validate_workflow  # noqa: E402

HERE = Path(__file__).resolve().parent
OLD = HERE / "fixtures" / "old-pre-phase7.json"
TWIN = HERE / "fixtures" / "new-twin.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    old = _load(OLD)
    twin = _load(TWIN)
    if old.get("spec_version") != SPEC_VERSION_PRE_PHASE7:
        print(f"FAILED:IMP-0147-probe1 old spec_version={old.get('spec_version')}")
        return 1
    if twin.get("spec_version") != CURRENT_SPEC_VERSION:
        print(f"FAILED:IMP-0147-probe1 twin spec_version={twin.get('spec_version')}")
        return 1

    old_violations = [v.id for v in validate_workflow(old)]
    if VIOLATION_SPEC_VERSION_UNSUPPORTED not in old_violations:
        print(f"FAILED:IMP-0147-probe1 old workflow was executable without migrate: {old_violations}")
        return 1

    result = migrate(old)
    if not result.ok or result.workflow is None:
        print(f"FAILED:IMP-0147-probe1 migrate refused: {result.refusal_id} {result.detail}")
        return 1
    migrated = result.workflow
    if migrated.get("spec_version") != CURRENT_SPEC_VERSION:
        print(f"FAILED:IMP-0147-probe1 migrated spec_version={migrated.get('spec_version')}")
        return 1
    if result.steps_applied != tuple(range(SPEC_VERSION_PRE_PHASE7, CURRENT_SPEC_VERSION)):
        print(f"FAILED:IMP-0147-probe1 steps_applied={result.steps_applied}")
        return 1

    after = validate_workflow(migrated)
    if after:
        print(f"FAILED:IMP-0147-probe1 migrated still invalid: {[v.id for v in after]}")
        return 1

    plan_migrated = compile_plan(migrated)
    plan_twin = compile_plan(twin)
    if not plan_migrated or not plan_twin:
        print("FAILED:IMP-0147-probe1 empty plan (vacuous equality)")
        return 1
    kinds = {step.get("kind") for step in plan_migrated}
    if not {"WorkUnit", "FanOut", "Barrier", "Pipeline"} <= kinds:
        print(f"FAILED:IMP-0147-probe1 plan kinds too thin: {sorted(kinds)}")
        return 1
    if plan_migrated != plan_twin:
        print("FAILED:IMP-0147-probe1 plan mismatch")
        print(json.dumps({"migrated": plan_migrated, "twin": plan_twin}, indent=2, sort_keys=True))
        return 1

    # Sanity: equality is not tautological — a mutated twin diverges.
    mutated = json.loads(json.dumps(twin))
    for node in mutated["nodes"]:
        if node.get("id") == "unit-b":
            node["id"] = "unit-b-mutated"
            break
    mutated["nodes"][3]["units"] = ["unit-b-mutated", "unit-c"]
    if compile_plan(mutated) == plan_migrated:
        print("FAILED:IMP-0147-probe1 plan equality is vacuous (mutant still matches)")
        return 1

    payload = {
        "probe": "probe1-plan-equality",
        "unit_id": "IMP-0147",
        "pass": True,
        "from_version": result.from_version,
        "to_version": result.to_version,
        "steps_applied": list(result.steps_applied),
        "plan_steps": len(plan_migrated),
        "plan_kinds": sorted(kinds),
        "old_unsupported": True,
        "migrated_equals_twin": True,
        "mutant_diverges": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print("SUCCESS:IMP-0147-probe1 migrated-old plan equals hand-written-new plan")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
