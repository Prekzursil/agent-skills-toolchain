#!/usr/bin/env python3
"""Probe 2: unflippable encodings named individually; condition 13 unsatisfiable.

Mechanically different from probe 1: plants a constant-TRUE encoding and
requires the decorative detector to fire; rebuilds the 20-TRUE + 1-NOT-CHECKED
aggregate without using attack()['pass'] as the oracle; checks CC-0015
absent_verbatim ids independently of the receipt table copy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import attack as A  # noqa: E402

CC_DIR = HERE.parent / "CC-0015"
sys.path.insert(0, str(CC_DIR))
import evaluator as Ev  # noqa: E402
import predicate_table as PT  # noqa: E402

ART = REPO / "command-center/receipts/TST-0347.json"
ABSENT = list(A.ABSENT_IDS)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0347-probe2 {msg}")
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


def named_ids(doc: dict, key: str) -> list[int]:
    rep = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    rows = rep.get(key) if key in rep else doc.get(key)
    if not rows:
        return []
    out = []
    for r in rows:
        if isinstance(r, dict) and r.get("id") is not None:
            out.append(int(r["id"]))
        elif isinstance(r, int):
            out.append(r)
    return out


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
    unflipped_ids = [r["id"] for r in live["unflipped_named"]]
    if unflipped_ids != ABSENT:
        return fail(f"unflippable not the absent set: {unflipped_ids}")
    if live["decorative_named"]:
        return fail(f"decorative not empty: {live['decorative_named']}")

    c13 = (live["permanently_unsatisfiable"] or [None])[0]
    if not c13 or c13.get("id") != 13:
        return fail("condition 13 missing from unsatisfiable class")
    if c13.get("silently_not_checked") is not False:
        return fail("condition 13 silently NOT-CHECKED")
    if c13.get("canary_world_flips") is not True:
        return fail("condition 13 canary-world flip missing")
    if c13.get("amended_world_flips") is not True:
        return fail("condition 13 amended-world flip missing")

    rec_unsat = named_ids(doc, "permanently_unsatisfiable_conditions")
    if rec_unsat != [13]:
        return fail(f"artifact unsatisfiable ids {rec_unsat}")
    rec_table = {r.get("condition_id"): r for r in table_of(doc)}
    rec13 = rec_table.get(13) or {}
    if rec13.get("predicate_verdict") == "NOT-CHECKED":
        return fail("artifact condition 13 is NOT-CHECKED")
    if rec13.get("class") != "PERMANENTLY-UNSATISFIABLE-AS-WRITTEN":
        return fail(f"artifact condition 13 class {rec13.get('class')}")

    rec_unflipped = named_ids(doc, "unflippable_conditions")
    if rec_unflipped != ABSENT:
        return fail(f"artifact unflippable {rec_unflipped}")
    rec_dec = named_ids(doc, "decorative_conditions")
    if rec_dec:
        return fail(f"artifact decorative {rec_dec}")

    if A.planted_constant_true_is_decorative() is not True:
        return fail("planted constant-TRUE predicate was not classified decorative")

    table = PT.encodings()
    synthetic = []
    for spec in table:
        if spec["id"] == 8:
            synthetic.append(
                {
                    "id": 8,
                    "verdict": "NOT-CHECKED",
                    "settling_probe": "aggregation control",
                }
            )
        else:
            synthetic.append(
                {"id": spec["id"], "verdict": "TRUE", "settling_probe": "n"}
            )
    agg = Ev.aggregate(synthetic)
    if agg["program_complete"] is not False:
        return fail("20 TRUE + 1 NOT-CHECKED reported PROGRAM-COMPLETE")
    if agg["counts"]["NOT-CHECKED"] != 1:
        return fail(f"NOT-CHECKED count {agg['counts']}")

    if not tests_pass(doc, "aggregation_20_true_1_not_checked_is_incomplete"):
        return fail("artifact aggregation control not pass")
    if not tests_pass(doc, "planted_decorative_constant_detected"):
        return fail("artifact planted decorative test not pass")
    if not tests_pass(doc, "condition_13_permanently_unsatisfiable_not_not_checked"):
        return fail("artifact condition 13 class test not pass")
    if not tests_pass(doc, "unflippable_reported_individually"):
        return fail("artifact unflippable-named test not pass")

    # Independent of attack(): absent_verbatim encodings stay NOT-CHECKED
    # across three worlds.
    good = A.satisfying_state()
    binding = A.as_written_pr_only_state()
    canary = A.canary_world_state()
    for world in (good, binding, canary):
        result = Ev.run(world, table)
        by_id = {r["id"]: r for r in result["conditions"]}
        for cid in ABSENT:
            if by_id[cid]["verdict"] != "NOT-CHECKED":
                return fail(
                    f"absent id={cid} verdict {by_id[cid]['verdict']} in a world"
                )
            if by_id[cid].get("kind") != "absent_verbatim":
                return fail(f"absent id={cid} kind {by_id[cid].get('kind')}")

    c13_live = next(
        r for r in Ev.run(binding, table)["conditions"] if r["id"] == 13
    )
    if c13_live["verdict"] == "NOT-CHECKED":
        return fail("live condition 13 is NOT-CHECKED")
    if c13_live.get("unsatisfiable_as_written") is not True:
        return fail(f"live condition 13 unsat flag {c13_live.get('unsatisfiable_as_written')}")

    out = {
        "probe": "probe2-unflippable-and-unsat",
        "unit_id": "TST-0347",
        "unflipped_named": unflipped_ids,
        "decorative_named": live["decorative_named"],
        "condition_13_class": c13["class"],
        "planted_decorative_detected": True,
        "not_checked_blocks_complete": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        "SUCCESS:TST-0347-probe2 unflippable named individually; "
        "condition 13 unsatisfiable-as-written; NOT-CHECKED blocks complete"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
