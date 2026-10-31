"""IMP-0147 probe1: a spec_version=6 workflow migrates to 11 and compiles to the
same plan as a hand-written spec_version=11 twin; a mutated twin diverges (the
equality is not vacuous); the unmigrated v6 doc is unsupported.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.migrate import migrate  # noqa: E402
from agentspec.plan import compile_plan  # noqa: E402
from agentspec.validate import violation_ids, validate_workflow  # noqa: E402


def workflow(version: int) -> dict:
    return {
        "id": "wf-imp0147",
        "spec_version": version,
        "entry": "pipe",
        "nodes": [
            {"kind": "WorkUnit", "id": "u1", "params": {"model": "opus"}},
            {"kind": "WorkUnit", "id": "u2", "params": {}},
            {"kind": "WorkUnit", "id": "u3", "params": {}},
            {"kind": "FanOut", "id": "fan", "units": ["u1", "u2"]},
            {"kind": "Barrier", "id": "bar", "wait_for": ["u3"]},
            {"kind": "Pipeline", "id": "pipe", "steps": ["fan", "bar"]},
        ],
    }


def main() -> int:
    checks = {}
    old = workflow(6)
    res = migrate(old)
    checks["migration_ok"] = res.ok
    checks["steps_applied"] = list(res.steps_applied) == [6, 7, 8, 9, 10]
    checks["from_to"] = (res.from_version, res.to_version) == (6, 11)

    twin = workflow(11)
    migrated = res.workflow
    plan_migrated = compile_plan(migrated)
    plan_twin = compile_plan(twin)
    checks["migrated_equals_twin"] = plan_migrated == plan_twin
    kinds = sorted({s["kind"] for s in plan_migrated})
    checks["plan_kinds"] = kinds == ["Barrier", "FanOut", "Pipeline", "WorkUnit"]
    checks["plan_steps_six"] = len(plan_migrated) == 6

    mutant = workflow(11)
    mutant["nodes"][3]["units"] = ["u1", "uX"]
    checks["mutant_diverges"] = compile_plan(mutant) != plan_twin

    old_ids = violation_ids(validate_workflow(copy.deepcopy(old)))
    checks["old_unsupported"] = "spec-version-unsupported" in old_ids
    new_ids = violation_ids(validate_workflow(migrated))
    checks["migrated_no_spec_violation"] = "spec-version-unsupported" not in new_ids

    out = {
        "unit_id": "IMP-0147",
        "probe": "probe1-plan-equality",
        "from_version": res.from_version,
        "to_version": res.to_version,
        "steps_applied": list(res.steps_applied),
        "plan_steps": len(plan_migrated),
        "plan_kinds": kinds,
        "migrated_equals_twin": checks["migrated_equals_twin"],
        "mutant_diverges": checks["mutant_diverges"],
        "old_unsupported": checks["old_unsupported"],
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0147-probe1 migrated-old plan equals hand-written-new plan; mutant twin diverges; v6 doc unsupported pre-migration")
        return 0
    print("FAILED:IMP-0147-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
