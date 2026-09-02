#!/usr/bin/env python3
"""Named probe 2: polluted archives turn the gate red; mutant rule deletion silences .git."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PLUGIN = REPO / "tools" / "plugin"
sys.path.insert(0, str(PLUGIN))

import package_hygiene as ph  # noqa: E402


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0081-probe2 {msg}")
    return 1


def main() -> int:
    planted = ph.test_gate_fails_on_a_planted_dot_git()
    budget = ph.test_gate_fails_above_the_size_budget()
    extras = ph.test_gate_fails_on_transcript_log_and_credential_names()
    if not planted.get("pass"):
        return _fail(f"planted .git did not fail the gate: {planted}")
    if not budget.get("pass"):
        return _fail(f"size budget did not fail: {budget}")
    if not extras.get("pass"):
        return _fail(f"transcript/log/credential names did not fail: {extras}")
    if planted.get("gate_ok") is not False:
        return _fail("planted .git gate_ok was not False")
    if budget.get("gate_ok") is not False:
        return _fail("oversize gate_ok was not False")
    if budget.get("clean_under_budget_ok") is not True:
        return _fail("both-states: clean package was not under budget")
    if planted.get("mutant_disabled_git_rule_ok") is not True:
        return _fail("deleting the .git rule did not un-fire; detector may be vacuous")
    if extras.get("credential_body_absent_from_report") is not True:
        return _fail("credential fixture body leaked into the report")

    out = {
        "probe": "probe2-polluted-gate",
        "unit_id": "TST-0081",
        "pass": True,
        "test_gate_fails_on_a_planted_dot_git": True,
        "test_gate_fails_above_the_size_budget": True,
        "archive_not_tree": True,
        "both_states": {
            "clean_passes": True,
            "planted_git_fails": True,
            "oversize_fails": True,
            "oversize_offending_entry": budget.get("offending_entry"),
            "git_rule_mutation_unfires": True,
        },
        "path_roles_fired": extras.get("rules_fired"),
        "credential_body_absent_from_report": True,
        "size_ceiling_bytes": budget.get("size_ceiling_bytes"),
        "oversize_total_uncompressed_bytes": budget.get("total_uncompressed_bytes"),
    }
    print(json.dumps(out, indent=2, sort_keys=True))
    print(
        "planted_git=FAIL oversize=FAIL clean_under_budget=PASS "
        f"offending={budget.get('offending_entry')}"
    )
    print("SUCCESS:TST-0081-probe2 polluted gate red; git-rule mutation un-fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
