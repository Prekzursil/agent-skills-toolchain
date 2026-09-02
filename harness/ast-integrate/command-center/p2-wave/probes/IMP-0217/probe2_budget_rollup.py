#!/usr/bin/env python3
"""Named probe 2: parent budget equals the sum of child budgets, no double count.

Signal 1: after the colliding-internal-id fixture, the immutable ledger's
leaf-spend total equals sib.left(7) + sib.right(7) = 14, and the parent
roll-up amount matches that sum.

Signal 2 (mutation): counting roll-up lines as spend inflates the parent
total (14 leaf + 7 + 7 + 14 roll-ups). Production must stay exact; the
mutant must go red.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_fixture  # noqa: E402

ART = REPO / "command-center" / "receipts" / "IMP-0217.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0217-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0217" not in text:
        print("FAILED:IMP-0217-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0217":
        print("FAILED:IMP-0217-probe2 unit_id", doc.get("unit_id"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0217-p2-") as tmp:
        result, fixture = run_fixture(Path(tmp) / "named", namespacing=True)
        mutant, _ = run_fixture(
            Path(tmp) / "mutant",
            namespacing=True,
            count_rollups_as_spend=True,
        )

    expected_parent = int(fixture["expected"]["parent_budget"])
    expected_children = dict(fixture["expected"]["child_budgets"])
    assertion = result.rollup_assertion()
    child_budgets = dict(result.child_budgets)

    if child_budgets != expected_children:
        print(f"FAILED:IMP-0217-probe2 child_budgets={child_budgets} want={expected_children}")
        return 1
    if result.parent_budget != expected_parent:
        print(f"FAILED:IMP-0217-probe2 parent_budget={result.parent_budget} want={expected_parent}")
        return 1
    if not assertion["exact"] or not assertion["rollup_matches"]:
        print(f"FAILED:IMP-0217-probe2 rollup assertion {assertion}")
        return 1
    if not assertion["naive_would_double_count"]:
        print("FAILED:IMP-0217-probe2 naive total did not diverge from leaf total")
        return 1
    if assertion["parent_spend_total"] != sum(expected_children.values()):
        print("FAILED:IMP-0217-probe2 parent != sum(children)")
        return 1
    if len(result.ledger.spends()) != 2:
        print(f"FAILED:IMP-0217-probe2 leaf spends={len(result.ledger.spends())} want=2")
        return 1
    if mutant.parent_budget == result.parent_budget:
        print(
            "FAILED:IMP-0217-probe2 double-count mutant did not inflate parent "
            f"named={result.parent_budget} mutant={mutant.parent_budget}"
        )
        return 1
    if mutant.parent_budget == expected_parent:
        print("FAILED:IMP-0217-probe2 mutant parent still exact")
        return 1
    if mutant.parent_budget <= result.parent_budget:
        print(
            f"FAILED:IMP-0217-probe2 mutant {mutant.parent_budget} "
            f"not greater than named {result.parent_budget}"
        )
        return 1

    print(
        f"parent_budget={result.parent_budget} child_budgets={child_budgets} "
        f"child_sum={assertion['child_sum']}"
    )
    print(
        f"leaf_spends={assertion['leaf_spend_count']} "
        f"rollups={assertion['rollup_count']} "
        f"naive_including_rollups={assertion['naive_including_rollups']}"
    )
    print(
        f"mutant_parent_budget={mutant.parent_budget} "
        "double_count_mutant_goes_red=true"
    )
    print("SUCCESS:IMP-0217-probe2 budget-rollup-no-double-count")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
