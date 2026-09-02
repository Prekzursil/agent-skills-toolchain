#!/usr/bin/env python3
"""Probe 1: family census, per-record schedule/NOT-EXECUTABLE, live oracles."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from family import (  # noqa: E402
    EXPECTED_N,
    NAMED_IDS,
    NAMED_SLUGS,
    catalog_expected_n,
    catalog_named_ids,
    catalog_named_slugs,
    catalog_unit,
    family_members,
    library_on_this_tree,
    load_catalogue,
    member_ids,
    records_of,
)
from oracles import load_claim, oracle_status  # noqa: E402
from runtime import execute_schedule, turn_schedule  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0045-executable-runtime-semantics-for-the-7-engineering-review-.md"
)


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0045-probe1 {msg}")
    return 1


def main() -> int:
    if library_on_this_tree():
        return fail("library present; this probe must recount from library bytes")
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "CNL-0045":
        return fail(f"unit_id {doc.get('unit_id')}")
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    blob = json.dumps(doc)
    if "SUCCESS:CNL-0045" not in blob:
        return fail("sentinel absent")
    if doc.get("library", {}).get("on_this_tree") is True:
        return fail("artifact claims library on_this_tree")

    cat = load_catalogue()
    recs = records_of(cat)
    members = family_members(recs)
    ids = member_ids(members)
    unit = catalog_unit()
    named = catalog_named_ids(unit)
    slugs = catalog_named_slugs(unit)
    expected = catalog_expected_n(unit)

    print(f"fixture_n={len(members)} catalog_n={expected} ids={ids}")
    print(f"catalog_named={named} slugs={slugs}")
    if len(members) != EXPECTED_N or expected != EXPECTED_N:
        return fail(f"count fixture={len(members)} catalog={expected}")
    if sorted(ids) != sorted(NAMED_IDS) or named != list(NAMED_IDS):
        return fail("id set disagreement")
    if slugs != NAMED_SLUGS:
        return fail(f"slug disagreement {slugs}")
    if sorted(doc.get("family_ids") or []) != sorted(ids):
        return fail("artifact family_ids drift from fixture")

    covered = 0
    has_oracle = []
    no_oracle = []
    for rec in members:
        rid = rec["id"]
        status = oracle_status(rec)
        sched = turn_schedule(rec)
        if sched["executable"]:
            if not sched["turns"]:
                return fail(f"{rid} executable but empty turns")
            good = execute_schedule(rec, load_claim(rid, "good"))
            bad = execute_schedule(rec, load_claim(rid, "bad"))
            print(
                f"{rid} EXECUTABLE class={status['class']} "
                f"good={good.get('verdict')} bad={bad.get('verdict')}"
            )
            if good.get("verdict") != "SETTLED":
                return fail(f"{rid} good claim not SETTLED")
            if bad.get("verdict") != "UNSETTLED":
                return fail(f"{rid} bad claim not UNSETTLED")
            has_oracle.append(rid)
        else:
            if sched.get("verdict") != "NOT-EXECUTABLE":
                return fail(f"{rid} missing NOT-EXECUTABLE")
            if not sched.get("missing_element"):
                return fail(f"{rid} NOT-EXECUTABLE blank missing_element")
            run = execute_schedule(rec, {"should_not_settle": True})
            print(
                f"{rid} NOT-EXECUTABLE missing={sched['missing_element']} "
                f"run={run.get('verdict')}"
            )
            if run.get("verdict") != "NOT-EXECUTABLE":
                return fail(f"{rid} execute did not stay NOT-EXECUTABLE")
            no_oracle.append(rid)
        covered += 1

    if covered != EXPECTED_N:
        return fail(f"covered={covered}")
    art_none = [r["id"] for r in (doc.get("no_oracle") or [])]
    art_has = [r["id"] for r in (doc.get("oracles") or [])]
    if sorted(art_none) != sorted(no_oracle):
        return fail(f"artifact no_oracle {art_none} != live {no_oracle}")
    if sorted(art_has) != sorted(has_oracle):
        return fail(f"artifact oracles {art_has} != live {has_oracle}")
    for row in doc.get("records") or []:
        if row.get("id") not in NAMED_IDS:
            return fail(f"artifact extra record {row}")
        if not row.get("verdict"):
            return fail(f"artifact record missing verdict {row}")

    print(
        f"covered={covered} has_oracle={has_oracle} no_oracle={no_oracle} "
        "library_on_this_tree=False"
    )
    print("SUCCESS:CNL-0045-probe1 family oracles and schedules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
