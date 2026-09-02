#!/usr/bin/env python3
"""Named probe 1: case schema, provenance completeness, split disjointness.

Signal: jsonschema errors plus computed set intersections of case ids.
Does not score oracle known-good / known-bad (that is probe 2).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "bench"))

from oracle import load_cases, split_intersections  # noqa: E402

UNIT = "TST-0295"
ART = REPO / "command-center" / "receipts" / "TST-0295.json"
SCHEMA = REPO / "command-center" / "schema" / "bench-case.schema.json"
GARBAGE = (
    {},
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
)


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:{UNIT}-probe1 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, default=str)[:4000])
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != UNIT:
        return fail("unit_id", doc.get("unit_id"))
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:TST-0295" not in json.dumps(doc):
        return fail("sentinel absent")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    for probe in GARBAGE:
        if not list(validator.iter_errors(probe)):
            return fail("schema accepts garbage", probe)

    cases = load_cases()
    if len(cases) < 2:
        return fail("corpus too small", {"n": len(cases)})
    schema_hits = []
    empty_prov = []
    for case in cases:
        for err in validator.iter_errors(case):
            schema_hits.append({"id": case.get("id"), "path": list(err.path), "msg": err.message})
        source = (case.get("provenance") or {}).get("source")
        if not isinstance(source, str) or not source.strip():
            empty_prov.append(case.get("id"))
    if schema_hits:
        return fail("case schema", schema_hits[:8])
    if empty_prov:
        return fail("empty provenance", empty_prov[:8])

    intersections = split_intersections(cases)
    if any(intersections[k] for k in intersections):
        return fail("split overlap computed", intersections)

    rec_inter = doc.get("split_disjointness") or {}
    for key in ("dev_and_test", "dev_and_held_out", "test_and_held_out"):
        live = intersections[key]
        recorded = rec_inter.get(key)
        if recorded != live:
            return fail("receipt split intersection drift", {"key": key, "live": live, "recorded": recorded})

    by_split: dict[str, int] = {}
    by_stratum: dict[str, int] = {}
    for case in cases:
        by_split[case["split"]] = by_split.get(case["split"], 0) + 1
        by_stratum[case["difficulty_stratum"]] = by_stratum.get(case["difficulty_stratum"], 0) + 1
    if by_split != doc.get("counts_by_split"):
        return fail("receipt split counts drift", {"live": by_split, "recorded": doc.get("counts_by_split")})
    if by_stratum != doc.get("counts_by_stratum"):
        return fail("receipt stratum counts drift", {"live": by_stratum, "recorded": doc.get("counts_by_stratum")})
    if min(by_split.values()) < 1:
        return fail("empty split", by_split)

    payload = {
        "pass": True,
        "probe": "probe1-schema-splits",
        "unit_id": UNIT,
        "n_cases": len(cases),
        "schema_garbage_rejected": True,
        "provenance_holes": 0,
        "split_intersections": intersections,
        "counts_by_split": by_split,
        "counts_by_stratum": by_stratum,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"n={len(cases)} splits={by_split} strata={by_stratum} "
        f"intersections_empty=True"
    )
    print("SUCCESS:TST-0295-probe1 schema provenance split-disjointness")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
