"""IMP-0134: load-time param validation - four distinct violation ids in the closed set.

Catalog requirement: a missing required param, a type mismatch, an out-of-enum value
and an unknown param key each produce a DISTINCT violation id, and the id set stays
closed (no free-form strings). The unknown param key is the strict-parser failure
class: it is rejected, never ignored.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AGENTSPEC = ROOT / "tools" / "agentspec"
FIXTURES = ROOT / "command-center" / "p2-wave" / "probes" / "IMP-0134" / "fixtures"

if str(AGENTSPEC) not in sys.path:
    sys.path.insert(0, str(AGENTSPEC))

from agentspec.spec import (  # noqa: E402
    load_workflow_checked,
    validate_params,
    workflow_from_path,
)
from agentspec.validate import VIOLATIONS  # noqa: E402

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
    "valid-twin": {"region": "eu", "level": "low"},
}


def test_four_distinct_ids() -> None:
    seen = {}
    for name, expected_id in EXPECTED.items():
        wf = workflow_from_path(FIXTURES / (name + ".json"))
        ids = validate_params(wf.params, VALUES[name])
        assert ids == [expected_id], (name, ids, expected_id)
        seen[name] = ids[0]
    assert len(set(seen.values())) == 4, seen


def test_ids_in_closed_set() -> None:
    for vid in EXPECTED.values():
        assert vid in VIOLATIONS, vid


def test_valid_twin_loads_clean() -> None:
    wf = load_workflow_checked(FIXTURES / "valid-twin.json", VALUES["valid-twin"])
    assert validate_params(wf.params, VALUES["valid-twin"]) == []


def test_unknown_key_rejected_at_load() -> None:
    raised = None
    try:
        load_workflow_checked(FIXTURES / "unknown-key.json", VALUES["unknown-key"])
    except ValueError as exc:
        raised = exc
    assert raised is not None and "param-key-unknown" in str(raised.ids)


def run_all() -> None:
    test_four_distinct_ids()
    test_ids_in_closed_set()
    test_valid_twin_loads_clean()
    test_unknown_key_rejected_at_load()


if __name__ == "__main__":
    run_all()
    print("SUCCESS:test_param_load_ids")
