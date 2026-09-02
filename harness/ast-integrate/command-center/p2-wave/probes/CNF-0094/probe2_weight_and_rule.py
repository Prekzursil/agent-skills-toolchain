#!/usr/bin/env python3
"""Named probe 2: weighted-as-unweighted hunt, undeclared-rule, schema mutant.

Different field from probe 1: detector polarity on a non-control corpus,
plus a quoted abstention rule, plus garbage rejected by the schema.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import recompute as R  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0094-council-calibration-recompute.json"
SCHEMA = REPO / "command-center/schema/calibration-report.schema.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0094-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    quoted = (doc.get("aggregation_rule") or {}).get("quoted") or ""
    if "ABSTENTION" not in quoted or "excluded from the Brier" not in quoted:
        print("FAILED:CNF-0094-probe2 abstention rule not quoted on artifact")
        return 1
    if "DELEGATION" not in quoted or "WEIGHTS" not in quoted:
        print("FAILED:CNF-0094-probe2 delegation/weight rule not quoted")
        return 1

    estate = R.score_run(R.load_run(HERE / "fixtures" / "estate-run.json"))
    if estate.brier_weighted == estate.brier_unweighted:
        print("FAILED:CNF-0094-probe2 estate weights are not load-bearing")
        return 1
    planted = R.weighted_counted_as_unweighted(estate, estate.brier_unweighted)
    if not planted["fired"]:
        print("FAILED:CNF-0094-probe2 did not fire on unweighted published Brier")
        print(json.dumps(planted, indent=2))
        return 1
    honest = R.weighted_counted_as_unweighted(estate, estate.brier_weighted)
    if honest["fired"]:
        print("FAILED:CNF-0094-probe2 fired on correctly weighted published Brier")
        return 1
    gap = R.undeclared_rule({"brier_score": str(estate.brier_weighted)})
    if not gap["undeclared"]:
        print("FAILED:CNF-0094-probe2 undeclared-rule missed")
        return 1
    quoted_ok = R.undeclared_rule({"aggregation_rule_quote": quoted})
    if quoted_ok["undeclared"]:
        print("FAILED:CNF-0094-probe2 quoted rule treated as undeclared")
        return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    if list(validator.iter_errors(doc)):
        print("FAILED:CNF-0094-probe2 live artifact fails its schema")
        return 1
    for garbage in ({}, {"unit_id": "CNF-0094", "state": "SUCCESS"}, {"n": -1}):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0094-probe2 schema accepted garbage", garbage)
            return 1

    art_hunt = doc.get("weighted_vote_counted_as_unweighted") or {}
    if art_hunt.get("fired") is not True:
        print("FAILED:CNF-0094-probe2 artifact missing fired detector")
        return 1

    out = {
        "probe": "probe2-weight-and-rule",
        "unit_id": "CNF-0094",
        "weighted_differs_unweighted": True,
        "planted_unweighted_fired": True,
        "honest_weighted_silent": True,
        "undeclared_rule_detected": True,
        "quoted_rule_accepted": True,
        "schema_rejects_garbage": True,
        "abstention_rule_quoted": True,
        "pass": True,
    }
    (HERE / "probe2-weight-and-rule.raw.json").write_text(
        json.dumps(out, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:CNF-0094-probe2 weighted-as-unweighted detector and quoted rule")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
