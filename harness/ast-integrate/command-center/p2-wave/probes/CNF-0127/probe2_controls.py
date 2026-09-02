#!/usr/bin/env python3
"""Named probe 2: schema, required controls, CNF-0002 plants, mutants.

Mechanically different from probe 1: does not remesure the workload. It
validates the report, requires revert + file + independence, and proves the
checker is not a rubber stamp by mutating KEEP/REVERT rows.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import checks as C  # noqa: E402
import jsonschema  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0127-retention-remeasure.json"
SCHEMA = REPO / "command-center/schema/benchmark-report.schema.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0127-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft7Validator.check_schema(schema)
    jsonschema.Draft7Validator(schema).validate(doc)
    for garbage in ({}, {"totally": "unrelated", "passing_tests": 999999}, {"x": "x" * 200}):
        try:
            jsonschema.Draft7Validator(schema).validate(garbage)
        except jsonschema.ValidationError:
            print(f"garbage_rejected={list(garbage)[:1] or '{}'}")
            continue
        print("FAILED:CNF-0127-probe2 schema accepts garbage")
        return 1

    ok, why = C.check_artifact(doc)
    print(f"checker_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0127-probe2 checker rejected live artifact")
        return 1

    cases = {c["id"]: c for c in doc["cases"]}
    reverts = [c for c in doc["cases"] if c["verdict"] == "REVERT"]
    filed = [c for c in doc["cases"] if c["verdict"] == "FILE"]
    harmful = [c for c in reverts if c.get("classification") == "neutral-or-harmful"]
    if not harmful:
        print("FAILED:CNF-0127-probe2 no neutral/harmful revert")
        return 1
    if "imp-comment-only" not in cases or cases["imp-comment-only"]["verdict"] != "REVERT":
        print("FAILED:CNF-0127-probe2 comment-only was retained")
        return 1
    if "imp-extra-scan" not in cases or cases["imp-extra-scan"]["verdict"] != "REVERT":
        print("FAILED:CNF-0127-probe2 extra-scan was retained")
        return 1
    if not filed or cases.get("imp-set-no-casefold", {}).get("verdict") != "FILE":
        print("FAILED:CNF-0127-probe2 unguarded speedup not filed")
        return 1
    if cases.get("imp-casefold-index", {}).get("verdict") != "KEEP":
        print("FAILED:CNF-0127-probe2 genuine gain not kept")
        return 1
    print(
        f"controls revert={ [c['id'] for c in reverts] } "
        f"filed={[c['id'] for c in filed]} keep=imp-casefold-index"
    )

    mutant = copy.deepcopy(doc)
    mutant["cases"] = copy.deepcopy(doc["cases"])
    for row in mutant["cases"]:
        if row["id"] == "imp-extra-scan":
            row["verdict"] = "KEEP"
            break
    else:
        print("FAILED:CNF-0127-probe2 extra-scan row missing")
        return 1
    mok, mwhy = C.check_artifact(mutant)
    print(f"mutant_keep_harmful ok={mok} {mwhy}")
    if mok:
        print("FAILED:CNF-0127-probe2 mutant KEEP of harmful was accepted")
        return 1

    mutant2 = copy.deepcopy(doc)
    for row in mutant2["cases"]:
        if row["verdict"] == "KEEP":
            row["remeasurements"]["raw"] = []
            row["verdict"] = "KEEP"
            break
    m2ok, m2why = C.check_artifact(mutant2)
    print(f"mutant_unmeasured_keep ok={m2ok} {m2why}")
    if m2ok:
        print("FAILED:CNF-0127-probe2 unmeasured KEEP was accepted")
        return 1

    rb = doc["independence_controls"]["rule_b_reviewed_impl"]
    if rb.get("rejected") is not True or rb.get("authorship_only_would_accept") is not True:
        print("FAILED:CNF-0127-probe2 independence plant inert", rb)
        return 1
    ids = {r["reviewer_id"] for r in doc["reviewers"]}
    if len(ids) < 2:
        print("FAILED:CNF-0127-probe2 reviewer count", ids)
        return 1
    print("reviewers", sorted(ids))
    print("SUCCESS:CNF-0127-probe2 controls schema mutants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
