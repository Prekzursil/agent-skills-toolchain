#!/usr/bin/env python3
"""Probe 2: aggregation rule is typed and declared, asserted by schema.

Mechanically different from probe 1 (runtime independence detector): this probe
validates the closed enum, refuses undeclared/invalid rules, and checks that
evidence-gated aggregation does not count uncited votes as independent mass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ensemble as E  # noqa: E402


def main() -> int:
    report = E.evaluate_schema_contract()
    print(
        json.dumps(
            {
                "probe": "probe2-typed-aggregation-schema",
                "unit_id": "IMP-0187",
                "all_four_rules_schema_valid": report["all_four_rules_schema_valid"],
                "rules": report["rules"],
                "undeclared_refused": report["undeclared_refused"],
                "invalid_rule_refused": report["invalid_rule_refused"],
                "missing_rule_schema_rejects": report["missing_rule_schema_rejects"],
                "missing_rule_schema_errors": report["missing_rule_schema_errors"][:6],
                "evidence_gated_choice": report["evidence_gated_choice"],
                "naive_count_agents_on_asymmetric": report[
                    "naive_count_agents_on_asymmetric"
                ],
                "evidence_gated_ignores_uncited_majority": report[
                    "evidence_gated_ignores_uncited_majority"
                ],
            },
            sort_keys=True,
        )
    )
    print(
        f"rules_ok={report['all_four_rules_schema_valid']} "
        f"undeclared={report['undeclared_refused']} "
        f"invalid={report['invalid_rule_refused']} "
        f"schema_rejects_missing_rule={report['missing_rule_schema_rejects']} "
        f"evidence_gated={report['evidence_gated_choice']} "
        f"naive_agents={report['naive_count_agents_on_asymmetric']}"
    )
    if not report["pass"]:
        print("FAILED:IMP-0187-probe2 typed aggregation schema")
        return 1
    named = {row["rule"] for row in report["rules"]}
    if named != E.AGGREGATION_RULES:
        print(f"FAILED:IMP-0187-probe2 rule coverage {named}")
        return 1
    print(
        "SUCCESS:IMP-0187-probe2 aggregation rule typed and declared; "
        "undeclared/invalid refused; evidence-gated ignores uncited majority"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
