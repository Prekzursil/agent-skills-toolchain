"""IMP-0147 probe2 (mutation): an unmigratable construct returns a typed refusal,
never a partial workflow; the shipped silent-drop mutant (skip unknown keys) makes
the refusal expectation go red, proving the refusal is load-bearing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.migrate import (  # noqa: E402
    REFUSAL_DOWNGRADE,
    REFUSAL_UNKNOWN_KEY,
    migrate,
    migrate_skip_unknown_keys,
)


def fixture_unknown_key() -> dict:
    return {
        "id": "wf-imp0147-unmigratable",
        "spec_version": 10,
        "nodes": [
            {"kind": "WorkUnit", "id": "u1", "params": {}},
            {"kind": "WorkUnit", "id": "u2", "params": {}, "mystery_payload": {"x": 1}},
        ],
    }


def main() -> int:
    checks = {}
    doc = fixture_unknown_key()
    prod = migrate(doc)
    checks["production_refuses_typed"] = (
        (not prod.ok) and prod.refusal_id == REFUSAL_UNKNOWN_KEY
    )
    checks["production_returns_no_workflow"] = prod.workflow is None

    mut = migrate_skip_unknown_keys(doc)
    checks["mutant_does_not_refuse"] = mut.ok and mut.workflow is not None
    checks["mutant_silently_dropped_key"] = all(
        "mystery_payload" not in (n or {}) for n in (mut.workflow or {}).get("nodes", [])
    )
    # both states: the refusal expectation would go RED under the mutant behaviour
    checks["refusal_expectation_red_under_mutant"] = (
        mut.refusal_id != REFUSAL_UNKNOWN_KEY
    )

    downgrade = migrate({"id": "wf", "spec_version": 11, "nodes": []}, target=6)
    checks["downgrade_refused_typed"] = (
        (not downgrade.ok) and downgrade.refusal_id == REFUSAL_DOWNGRADE
    )

    too_old = migrate({"id": "wf", "spec_version": 5, "nodes": []})
    checks["pre_phase7_refused"] = (not too_old.ok) and too_old.refusal_id is not None

    out = {
        "unit_id": "IMP-0147",
        "probe": "probe2-silent-drop",
        "production_refusal": prod.refusal_id,
        "mutant_action": mut.detail,
        "downgrade_refusal": downgrade.refusal_id,
        "too_old_refusal": too_old.refusal_id,
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0147-probe2 unmigratable construct yields typed refusal and no partial workflow; the shipped silent-drop mutant flips the refusal expectation red")
        return 0
    print("FAILED:IMP-0147-probe2")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
