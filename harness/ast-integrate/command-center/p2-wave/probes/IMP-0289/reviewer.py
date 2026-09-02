#!/usr/bin/env python3
"""Independent adversarial review of IMP-0289, starting from the tests.

Does not trust check_reachability for the positive walk. Rebuilds the
expected id set from the same three-council fixture the probes use, walks
the meta JSON as generic objects, then mutates the ledger with generic
dict surgery (not drop_minority_report) and confirms the author's checker
fires on that mutated state.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO))

from tools.council.topology.meta import (  # noqa: E402
    KIND_MINORITY,
    aggregate,
    check_reachability,
    three_council_fixture,
)


def expected_ids_from_fixture(councils: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for council in councils:
        for rec in council.get("minority_reports") or []:
            rid = rec.get("id")
            if isinstance(rid, str) and rid:
                ids.append(rid)
    return ids


def walk_minority_ids(node: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        oid = node.get("id")
        if node.get("kind") == KIND_MINORITY and isinstance(oid, str) and oid:
            found.add(oid)
        for value in node.values():
            found |= walk_minority_ids(value)
    elif isinstance(node, list):
        for value in node:
            found |= walk_minority_ids(value)
    return found


def generic_drop(meta: dict[str, Any], report_id: str) -> dict[str, Any]:
    mutated = copy.deepcopy(meta)
    mutated["minority_reports"] = [
        r
        for r in (mutated.get("minority_reports") or [])
        if not (isinstance(r, dict) and r.get("id") == report_id)
    ]
    index = mutated.get("minority_index")
    if isinstance(index, dict):
        index.pop(report_id, None)
    mutated["dissents"] = [
        d
        for d in (mutated.get("dissents") or [])
        if not (isinstance(d, dict) and d.get("id") == report_id)
    ]
    dindex = mutated.get("dissent_index")
    if isinstance(dindex, dict):
        dindex.pop(report_id, None)
    return mutated


def main() -> int:
    councils = three_council_fixture()
    expected = expected_ids_from_fixture(councils)
    meta = aggregate(councils)
    walked = walk_minority_ids(meta)
    missing = [i for i in expected if i not in walked]
    drop_id = expected[0]
    mutated = generic_drop(meta, drop_id)
    walked_mut = walk_minority_ids(mutated)
    author_on_mut = check_reachability(mutated, expected)
    author_on_good = check_reachability(meta, expected)
    report = {
        "reviewer_id": "IMP-0289-fixture-walk-reviewer",
        "independent": True,
        "starts_from": "three_council_fixture minority_reports ids (same as probe1/probe2)",
        "did_not_author_module": True,
        "expected_ids": expected,
        "walked_ids": sorted(walked),
        "walk_missing": missing,
        "generic_drop_id": drop_id,
        "walk_after_drop_has_id": drop_id in walked_mut,
        "author_checker_ok_on_intact": author_on_good.get("ok"),
        "author_checker_ok_on_generic_drop": author_on_mut.get("ok"),
        "author_checker_missing_on_drop": author_on_mut.get("missing_ids"),
        "meta_verdict": meta.get("meta_verdict"),
        "averaging_forbidden": meta.get("averaging_forbidden"),
    }
    print(json.dumps(report, sort_keys=True))
    if missing:
        print(f"FAILED:IMP-0289-reviewer walk missing {missing}")
        return 1
    if drop_id in walked_mut:
        print("FAILED:IMP-0289-reviewer generic drop left the id in the walk")
        return 1
    if author_on_good.get("ok") is not True:
        print("FAILED:IMP-0289-reviewer author checker fails on intact artifact")
        return 1
    if author_on_mut.get("ok") is not False or drop_id not in set(
        author_on_mut.get("missing_ids") or []
    ):
        print("FAILED:IMP-0289-reviewer author checker silent on generic drop")
        return 1
    if meta.get("meta_verdict") != "DISAGREEMENT":
        print("FAILED:IMP-0289-reviewer disagreement was averaged away")
        return 1
    print("SUCCESS:IMP-0289-reviewer independent walk PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
