#!/usr/bin/env python3
"""Named probe 2: both-states control on the permission-model suite.

The suite must pass the reference evaluator and fail a silent-grant mutant
(the P0). Also requires one negative case per contract rule.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from suite import run_suite  # noqa: E402


def main() -> int:
    result = run_suite()
    both = result["both_states"]
    negatives = [c for c in result["cases"] if c["kind"] == "negative"]
    positives = [c for c in result["cases"] if c["kind"] == "positive"]
    rules = result["rules"]
    per_rule_negative = {
        rule: any(
            c["rule"] == rule and c["kind"] == "negative" and c["pass"]
            for c in negatives
        )
        for rule in rules
    }
    ok = (
        result["pass"]
        and both["discriminates"]
        and both["reference_conforming"] is True
        and both["silent_grant_conforming"] is False
        and both["silent_grant"]["leaked"] is True
        and both["silent_grant"]["undeclared"] == "ALLOW"
        and both["reference"]["leaked"] is False
        and len(negatives) >= 7
        and len(positives) >= 7
        and all(per_rule_negative.values())
        and not result["failed"]
    )
    payload = {
        "pass": bool(ok),
        "probe": "probe2-both-states",
        "unit_id": "TST-0036",
        "n_positive": len(positives),
        "n_negative": len(negatives),
        "n_failed": len(result["failed"]),
        "rules": rules,
        "per_rule_negative": per_rule_negative,
        "both_states": {
            "reference_conforming": both["reference_conforming"],
            "silent_grant_conforming": both["silent_grant_conforming"],
            "discriminates": both["discriminates"],
            "silent_grant_leaked": both["silent_grant"]["leaked"],
            "reference_leaked": both["reference"]["leaked"],
        },
    }
    print(json.dumps(payload, sort_keys=True))
    if not ok:
        print("FAILED:TST-0036-probe2 both-states or per-rule negative missing")
        print(json.dumps(result["failed"], sort_keys=True))
        return 1
    print(
        "SUCCESS:TST-0036-probe2 reference conforming; silent-grant mutant "
        "fails and leaks; negative case per rule"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
