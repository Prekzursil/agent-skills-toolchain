#!/usr/bin/env python3
"""Probe 1: two-level meta-workflow budget equals the sum of children.

Asserted against the immutable ledger (leaf-only). A naive sum of every
ledger row (leaves + rollups) double-counts and must NOT equal the parent.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402
from agentspec.budget import DoubleCountError  # noqa: E402

ART = Path(__file__).resolve().parents[4] / "command-center/receipts/IMP-0189.json"


def main() -> int:
    result = S.run_budget()
    parent = result.parent_budget
    child_sum = sum(result.child_budgets.values())
    leaf = result.ledger.leaf_total()
    naive = result.ledger.naive_sum_all_rows()
    print(
        json.dumps(
            {
                "probe": "probe1-budget-rollup",
                "parent_budget": parent,
                "child_budgets": result.child_budgets,
                "child_sum": child_sum,
                "leaf_total": leaf,
                "naive_sum_all_rows": naive,
                "expected_meta": S.META_BUDGET,
            },
            sort_keys=True,
        )
    )
    if parent != S.META_BUDGET:
        print(f"FAILED:IMP-0189-probe1 parent {parent} != expected {S.META_BUDGET}")
        return 1
    if parent != child_sum:
        print(f"FAILED:IMP-0189-probe1 parent {parent} != child_sum {child_sum}")
        return 1
    if parent != leaf:
        print(f"FAILED:IMP-0189-probe1 parent {parent} != leaf_total {leaf}")
        return 1
    if naive == parent:
        print("FAILED:IMP-0189-probe1 naive sum equalled parent (double-count hidden)")
        return 1
    if naive <= parent:
        print(f"FAILED:IMP-0189-probe1 naive {naive} did not exceed parent {parent}")
        return 1
    try:
        result.ledger.post_leaf("embed-a.u1", 10, parent_id="embed-a")
        print("FAILED:IMP-0189-probe1 duplicate leaf posting was accepted")
        return 1
    except DoubleCountError:
        print("duplicate_leaf_rejected=True")
    result.ledger.assert_sum_equals_children(
        "meta", tuple(result.child_budgets.keys())
    )
    print(
        f"ledger_parent={parent} child_sum={child_sum} leaf={leaf} "
        f"naive={naive} no_double_count=True"
    )

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in {
            "BLOCKED",
            "FAILED",
            "SEVERED",
            "TIMEOUT",
        }:
            print(f"FAILED:IMP-0189-probe1 self-declared {doc.get('state')}")
            return 1
        recorded = (doc.get("budget_rollup") or {}).get("parent_total")
        if recorded is not None and int(recorded) != parent:
            print(f"FAILED:IMP-0189-probe1 receipt parent drift {recorded} vs {parent}")
            return 1
        if "SUCCESS:IMP-0189" not in text:
            print("FAILED:IMP-0189-probe1 sentinel absent")
            return 1

    print("SUCCESS:IMP-0189-probe1 budget roll-up has no double count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
