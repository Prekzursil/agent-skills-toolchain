#!/usr/bin/env python3
"""Probe 1: table-driven falsifier — one FALSE per condition 1-10."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "platform" / "lib"
sys.path.insert(0, str(LIB))
sys.path.insert(0, str(HERE))

import completion_predicate as cp  # noqa: E402
from scenario import gold_tree, mutant_tree  # noqa: E402


def _eval(root: Path, receipt: dict) -> cp.Verdict:
    return cp.evaluate(receipt, repo=root, schema_path="artifact.schema.json")


def main() -> int:
    rows = []
    fail = False

    with tempfile.TemporaryDirectory(prefix="cc0003-gold-") as tmp:
        gold_root = Path(tmp)
        gold_receipt = gold_tree(gold_root)
        gold = _eval(gold_root, gold_receipt)
        gold_ok = gold.verdict == cp.COMPLETE and not gold.failing_condition_ids
        print(
            f"gold verdict={gold.verdict} failing={gold.failing_condition_ids} "
            f"not_checked={gold.not_checked_ids}"
        )
        if not gold_ok:
            fail = True
            print("FAILED:CC-0003-probe1 gold did not COMPLETE")
            print(json.dumps(gold.as_dict(), indent=2)[:4000])
        rows.append(
            {
                "case": "gold",
                "verdict": gold.verdict,
                "complete": gold_ok,
            }
        )

    for n in range(1, 11):
        with tempfile.TemporaryDirectory(prefix=f"cc0003-c{n}-") as tmp:
            root = Path(tmp)
            receipt = mutant_tree(root, n)
            verdict = _eval(root, receipt)
            target = next((c for c in verdict.conditions if c.n == n), None)
            right_reason = (
                target is not None
                and target.outcome == cp.FALSE
                and verdict.verdict == cp.INCOMPLETE
                and n in verdict.failing_condition_ids
            )
            print(
                f"cond {n:>2} mutation={receipt.get('_mutation')!r} "
                f"verdict={verdict.verdict} target={target.outcome if target else None} "
                f"failing={verdict.failing_condition_ids} "
                f"ptr={target.evidence_pointer if target else None}"
            )
            if not right_reason:
                fail = True
                print(
                    f"FAILED:CC-0003-probe1 condition {n} did not return FALSE "
                    f"with INCOMPLETE (got outcome={target.outcome if target else None} "
                    f"verdict={verdict.verdict} failing={verdict.failing_condition_ids})"
                )
            rows.append(
                {
                    "condition": n,
                    "text": cp.CONDITION_TEXT[n],
                    "mutation": receipt.get("_mutation"),
                    "outcome": target.outcome if target else None,
                    "basis": target.basis if target else None,
                    "evidence_pointer": target.evidence_pointer if target else None,
                    "verdict": verdict.verdict,
                    "failing_condition_ids": verdict.failing_condition_ids,
                    "right_reason": right_reason,
                }
            )

    false_count = sum(1 for r in rows if r.get("right_reason"))
    print(
        json.dumps(
            {
                "probe": "probe1-table",
                "unit_id": "CC-0003",
                "gold_complete": rows[0].get("complete"),
                "falsifying_cases": false_count,
                "want": 10,
                "rows": rows[1:],
            },
            indent=2,
        )
    )
    if fail or false_count != 10:
        print(f"FAILED:CC-0003-probe1 table-driven {false_count}/10")
        return 1
    print("SUCCESS:CC-0003-probe1 table-driven 10/10 FALSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
