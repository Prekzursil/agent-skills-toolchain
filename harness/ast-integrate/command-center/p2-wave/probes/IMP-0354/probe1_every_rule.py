#!/usr/bin/env python3
"""Probe 1: every declared tie-break rule is reachable on one exact-tie fixture.

Also: the same recorded seed resolves twice identically, and listing-order
permutation does not change any declared outcome (implicit order is not a rule).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from scenario import census_policies, exact_tie_fixture  # noqa: E402
from council.vote.tiebreak import (  # noqa: E402
    DECLARED_RULES,
    permute_case,
    policy_census,
    reproduce,
    resolve,
)


def main() -> int:
    case = exact_tie_fixture()
    policies = census_policies()
    census = policy_census(case, policies)
    permuted = permute_case(case)
    rows = []
    for rule in sorted(DECLARED_RULES):
        policy = policies[rule]
        first = resolve(case, policy)
        second = resolve(case, policy)
        perm = resolve(permuted, policy)
        reproduced = reproduce(case, policy, first)
        row = {
            "rule": rule,
            "kind": first.kind,
            "winner": first.winner,
            "seed_used": first.seed_used,
            "consumable_as_completed_decision": (
                first.is_consumable_as_completed_decision()
            ),
            "twice_identical": first == second,
            "reproduced": reproduced,
            "order_invariant": first == perm,
            "census_kind": census[rule]["kind"],
        }
        rows.append(row)

    reachable = {r["rule"] for r in rows}
    chair = next(r for r in rows if r["rule"] == "chair-casting-vote")
    seniority = next(r for r in rows if r["rule"] == "seniority")
    coin = next(r for r in rows if r["rule"] == "recorded-seed-coin-flip")
    escalation = next(r for r in rows if r["rule"] == "escalation")
    none = next(r for r in rows if r["rule"] == "no-decision")

    ok = (
        reachable == set(DECLARED_RULES)
        and all(r["twice_identical"] and r["reproduced"] and r["order_invariant"] for r in rows)
        and chair["winner"] == "alpha"
        and chair["kind"] == "DECISION"
        and seniority["winner"] == "beta"
        and seniority["kind"] == "DECISION"
        and chair["winner"] != seniority["winner"]
        and coin["kind"] == "DECISION"
        and coin["winner"] in {"alpha", "beta"}
        and coin["seed_used"] == policies["recorded-seed-coin-flip"].seed
        and escalation["kind"] == "ESCALATION"
        and escalation["winner"] is None
        and not escalation["consumable_as_completed_decision"]
        and none["kind"] == "NO-DECISION"
        and none["winner"] is None
        and not none["consumable_as_completed_decision"]
    )
    payload = {
        "probe": "probe1-every-rule",
        "unit_id": "IMP-0354",
        "reachable_rules": sorted(reachable),
        "declared_rules": sorted(DECLARED_RULES),
        "rows": rows,
        "chair_vs_seniority_diverge": chair["winner"] != seniority["winner"],
        "no_decision_reachable": none["kind"] == "NO-DECISION",
        "pass": ok,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not ok:
        print("FAILED:IMP-0354-probe1 every declared rule")
        return 1
    print(
        "SUCCESS:IMP-0354-probe1 every rule exercised; seed replay identical; "
        "NO-DECISION reachable"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
