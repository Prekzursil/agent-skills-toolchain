#!/usr/bin/env python3
"""Probe 1: 21 mutations, one per CC-0015 encoding; each satisfiable predicate flips.

Live re-run of the attack, compared to the receipt table. Condition 13 is the
unsatisfiable class and is required NOT to produce a binding-world TRUE->FALSE
flip under PR-ONLY, while its canary-world and amended-world controls MUST flip.
Absent-verbatim encodings are named unflippable, never folded into a pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack as A  # noqa: E402

ART = REPO / "command-center/receipts/TST-0347.json"
ABSENT = set(A.ABSENT_IDS)
FLIP = list(A.FLIP_IDS)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0347-probe1 {msg}")
    return 1


def table_of(doc: dict) -> list:
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    return list(rep.get("table") or doc.get("table") or [])


def tests_pass(doc: dict, test_id: str) -> bool:
    tests = doc.get("tests")
    if isinstance(tests, dict):
        row = tests.get(test_id) or {}
        return row.get("pass") is True or row.get("result") == "PASS"
    if isinstance(tests, list):
        for item in tests:
            if isinstance(item, dict) and item.get("id") == test_id:
                return item.get("result") == "PASS"
    return False


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "TST-0347":
        return fail(f"unit_id {doc.get('unit_id')}")
    text = json.dumps(doc)
    if "SUCCESS:TST-0347" not in text:
        return fail("sentinel-absent")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared:{st}")

    live = A.attack()
    if not live.get("pass"):
        return fail("live attack did not pass")
    if live["row_count"] != 21:
        return fail(f"row_count {live['row_count']}")

    by_id = {r["id"]: r for r in live["rows"]}
    if set(by_id) != set(range(1, 22)):
        return fail(f"ids {sorted(by_id)}")

    flipped = []
    for cid in range(1, 22):
        row = by_id[cid]
        if cid == 13:
            if row["baseline_verdict"] != "FALSE":
                return fail("condition 13 baseline is not FALSE under PR-ONLY")
            if row["class"] != "PERMANENTLY-UNSATISFIABLE-AS-WRITTEN":
                return fail(f"condition 13 class {row['class']}")
            if row.get("owner_decision_required") is not True:
                return fail("condition 13 missing owner_decision_required")
            if row["predicate_verdict"] == "NOT-CHECKED":
                return fail("condition 13 silently NOT-CHECKED")
            cw = row.get("canary_world") or {}
            if cw.get("flipped_true_to_false") is not True:
                return fail("condition 13 canary-world did not flip TRUE->FALSE")
            aw = row.get("amended_world") or {}
            if aw.get("flipped_true_to_false") is not True:
                return fail("condition 13 amended-world did not flip TRUE->FALSE")
            if row["flipped_true_to_false"] is not False:
                return fail("condition 13 claimed a binding-world TRUE->FALSE flip")
            continue
        if cid in ABSENT:
            if row["class"] != "UNFLIPPED-ABSENT-VERBATIM":
                return fail(f"condition {cid} class {row['class']}")
            if row["baseline_verdict"] != "NOT-CHECKED":
                return fail(f"condition {cid} baseline {row['baseline_verdict']}")
            if row["flipped_true_to_false"] is not False:
                return fail(f"condition {cid} claimed a flip")
            continue
        if row["baseline_verdict"] != "TRUE":
            return fail(f"condition {cid} baseline {row['baseline_verdict']}")
        if row["mutated_verdict"] != "FALSE":
            return fail(f"condition {cid} mutated {row['mutated_verdict']}")
        if not row["flipped_true_to_false"]:
            return fail(f"condition {cid} did not flip")
        flipped.append(cid)

    if flipped != FLIP:
        return fail(f"flipped set {flipped}")

    rec_table = {r.get("condition_id"): r for r in table_of(doc)}
    if len(rec_table) != 21:
        return fail(f"artifact table rows {len(rec_table)}")
    for cid, row in by_id.items():
        rec = rec_table.get(cid)
        if not rec:
            return fail(f"artifact missing condition {cid}")
        if rec.get("mutation_applied") != row["mutation_applied"]:
            return fail(f"artifact mutation drift on {cid}")
        if rec.get("predicate_verdict") != row["predicate_verdict"]:
            return fail(f"artifact verdict drift on {cid}")
        if rec.get("flipped_true_to_false") != row["flipped_true_to_false"]:
            return fail(f"artifact flip flag drift on {cid}")
        if rec.get("class") != row["class"]:
            return fail(f"artifact class drift on {cid}")

    if not tests_pass(doc, "twenty_one_mutations_one_per_condition"):
        return fail("artifact tests for 21 mutations not pass")
    if not tests_pass(doc, "each_satisfiable_predicate_flips_true_to_false"):
        return fail("artifact tests for satisfiable flips not pass")

    out = {
        "probe": "probe1-twenty-one-flips",
        "unit_id": "TST-0347",
        "rows": 21,
        "flipped_true_to_false": flipped,
        "unflipped_absent_verbatim": sorted(ABSENT),
        "condition_13_class": by_id[13]["class"],
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:TST-0347-probe1 13 TRUE->FALSE flips; "
        "7 absent-verbatim named; condition 13 unsatisfiable class"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
