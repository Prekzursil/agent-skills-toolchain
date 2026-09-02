#!/usr/bin/env python3
"""Probe 2: independent recount, both-states, negative control, overclaim, schema."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import both_states, coverage_findings, negative_control  # noqa: E402
from family import (  # noqa: E402
    EXPECTED_N,
    NAMED_IDS,
    catalog_expected_n,
    catalog_named_ids,
    catalog_unit,
    family_members,
    load_catalogue,
    member_ids,
    records_of,
)
from oracles import oracle_status  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0045-executable-runtime-semantics-for-the-7-engineering-review-.md"
)
SCHEMA = HERE / "council-design-note.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0045-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("design note missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator(schema).validate(doc)

    garbage = [
        {"totally": "unrelated", "passing_tests": 999999},
        {"x": "a" * 2000},
        {"unit_id": "CNL-0045"},
    ]
    for i, g in enumerate(garbage):
        errs = list(jsonschema.Draft7Validator(schema).iter_errors(g))
        print(f"garbage[{i}] rejected={len(errs) > 0} nerr={len(errs)}")
        if not errs:
            return fail(f"schema accepted garbage[{i}]")

    unit = catalog_unit()
    named = catalog_named_ids(unit)
    expected = catalog_expected_n(unit)
    recs = records_of(load_catalogue())
    members = family_members(recs)
    ids = member_ids(members)
    print(f"recount fixture_n={len(ids)} catalog_n={expected} named={named}")
    if len(ids) != expected or expected != EXPECTED_N:
        return fail("number disagreement fixture vs catalog expected n")
    if sorted(ids) != sorted(named) or named != list(NAMED_IDS):
        return fail("id-set disagreement fixture vs catalog regex")
    if int(doc.get("family_count") or 0) != len(ids):
        return fail("author family_count disagrees with recount")

    ctrl = both_states(recs)
    print(
        f"both_states silent_on_good={ctrl['silent_on_good']} "
        f"fires_on_bad={ctrl['fires_on_bad']} bad_kinds={ctrl['bad_kinds']}"
    )
    print(f"verbatim_good={json.dumps(ctrl['good_findings'], sort_keys=True)}")
    print(f"verbatim_bad={json.dumps(ctrl['bad_findings'], sort_keys=True)}")
    if not ctrl["silent_on_good"]:
        return fail("check not SILENT on known-good")
    if not ctrl["fires_on_bad"]:
        return fail("check not FIRES on planted-bad")
    want_kinds = {
        "family-count-mismatch",
        "family-id-set-mismatch",
        "family-misassignment",
        "overclaim-oracle",
    }
    if not want_kinds.issubset(set(ctrl["bad_kinds"])):
        return fail(f"planted-bad missing kinds {want_kinds - set(ctrl['bad_kinds'])}")

    neg = negative_control(recs)
    print(f"negative_control result={neg['result']} verbatim={neg['verbatim']}")
    if neg["result"] != "FIRES":
        return fail("negative control did not FIRE")

    art_tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    both = art_tests.get("both-states-catalogue") or {}
    if both.get("verbatim_good") != json.dumps(ctrl["good_findings"], sort_keys=True):
        return fail("artifact verbatim_good drift")
    if both.get("verbatim_bad") != json.dumps(ctrl["bad_findings"], sort_keys=True):
        return fail("artifact verbatim_bad drift")
    art_neg = (doc.get("negative_controls") or [{}])[0]
    if art_neg.get("verbatim") != neg["verbatim"]:
        return fail("artifact negative-control verbatim drift")

    for rec in members:
        status = oracle_status(rec)
        art_row = next(
            (r for r in (doc.get("records") or []) if r.get("id") == rec["id"]),
            None,
        )
        if art_row is None:
            return fail(f"artifact missing record {rec['id']}")
        want = "HAS-ORACLE" if status["has_oracle"] else "NO-ORACLE"
        if art_row.get("verdict") != want:
            return fail(f"overclaim or underclaim {rec['id']} art={art_row.get('verdict')} live={want}")
        if status["has_oracle"] and status["overclaim"]:
            return fail(f"live overclaim {rec['id']}")

    mutant = copy.deepcopy(recs)
    for rec in mutant:
        if rec.get("id") == "P48":
            rec["oracle"] = {"class": "test"}
    planted = coverage_findings(mutant)
    kinds = {f.get("kind") for f in planted}
    print(f"mutant_p48_overclaim kinds={sorted(kinds)}")
    if "overclaim-oracle" not in kinds:
        return fail("P48 class=test without predicate was not rejected")

    print("SUCCESS:CNL-0045-probe2 independent recount both-states overclaim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
