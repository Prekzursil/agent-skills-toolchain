"""IMP-0134 probe1: four fixtures yield four DISTINCT load-time param violation ids,
all inside the closed set; the valid twin loads clean; the unknown key is enforced
at LOAD time (loader raises), which is the strict-parser failure class.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools" / "agentspec"))

from agentspec.spec import (  # noqa: E402
    ParamViolationsError,
    load_workflow_checked,
    validate_params,
    workflow_from_path,
)
from agentspec.validate import VIOLATIONS  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures"
EXPECTED = {
    "missing-required": "param-required-missing",
    "type-mismatch": "param-type-mismatch",
    "out-of-enum": "param-value-not-in-enum",
    "unknown-key": "param-key-unknown",
}
VALUES = {
    "missing-required": {},
    "type-mismatch": {"retries": "many"},
    "out-of-enum": {"level": "medium"},
    "unknown-key": {"definitely_not_a_param": 1},
}


def main() -> int:
    checks = {}
    ids = []
    rows = []
    for name, expected in EXPECTED.items():
        wf = workflow_from_path(FIX / (name + ".json"))
        got = validate_params(wf.params, VALUES[name])
        rows.append({"fixture": name + ".json", "ids": got, "expected": expected})
        checks["fixture_" + name] = got == [expected]
        ids.extend(got)
    checks["four_distinct_ids"] = len(set(ids)) == 4
    checks["all_in_closed_set"] = all(i in VIOLATIONS for i in ids)

    twin = load_workflow_checked(FIX / "valid-twin.json", {"region": "eu", "level": "low"})
    checks["valid_twin_loads_clean"] = (
        len(twin.params) == 2 and validate_params(twin.params, {"region": "eu", "level": "low"}) == []
    )

    raised = None
    try:
        load_workflow_checked(FIX / "unknown-key.json", VALUES["unknown-key"])
    except ParamViolationsError as exc:
        raised = exc
    checks["load_time_enforcement_raises"] = (
        raised is not None and raised.ids == ["param-key-unknown"]
    )

    out = {
        "unit_id": "IMP-0134",
        "probe": "probe1-four-ids",
        "rows": rows,
        "distinct_ids": sorted(set(ids)),
        "closed_set_size": len(VIOLATIONS),
        "checks": checks,
        "pass": all(checks.values()),
    }
    print(json.dumps(out, indent=1))
    if all(checks.values()):
        print("SUCCESS:IMP-0134-probe1 four fixtures yield four distinct ids inside the closed set; valid twin loads clean; unknown key raises at load time")
        return 0
    print("FAILED:IMP-0134-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
