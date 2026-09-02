#!/usr/bin/env python3
"""Probe 1: live recompute of the benchmark register vs the emitted artifact.

Every applicable row must name a harness-level improvement. Every citation
with a number must carry a baseline or be graded E3. Stored verdicts must
match the engine on the committed paper_facts fixture.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402

UID = "RES-0093"
ART = REPO / "command-center/research/RES-0093.json"
SCHEMA = REPO / "command-center/schema/research-registry.schema.json"
COMPLETION = (
    "SUCCESS:RES-0093 in the receipt AND a benchmark register with an "
    "applicability verdict and a named detectable improvement per applicable row"
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0093-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if COMPLETION not in text:
        return fail("catalog sentinel absent")
    if "SUCCESS:RES-0093" not in text:
        return fail("SUCCESS:RES-0093 absent")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return fail(f"unparseable {exc}")
    if not isinstance(doc, dict):
        return fail("not an object")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")
    if doc.get("unit_id") != UID:
        return fail(f"unit_id {doc.get('unit_id')}")

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(doc, schema)

    live_rows = E.build_register()
    live_tests = E.tests_from_register(live_rows)
    stored = doc.get("benchmark_register") or []
    if len(stored) != len(live_rows):
        return fail(f"register length stored={len(stored)} live={len(live_rows)}")

    live_by = {r["benchmark_id"]: r for r in live_rows}
    stored_by = {r["benchmark_id"]: r for r in stored}
    if set(live_by) != set(stored_by):
        return fail(f"id set drift live={sorted(live_by)} stored={sorted(stored_by)}")

    for bid, live in live_by.items():
        got = stored_by[bid]
        if got.get("applicability_verdict") != live["applicability_verdict"]:
            return fail(f"{bid} verdict stored={got.get('applicability_verdict')} live={live['applicability_verdict']}")
        if got.get("named_detectable_improvement") != live["named_detectable_improvement"]:
            return fail(f"{bid} named improvement drift")
        if got.get("evidence_tier") != live["evidence_tier"]:
            return fail(f"{bid} evidence_tier drift")
        live_c = {c["claim_id"]: c for c in live["citations"]}
        got_c = {c["claim_id"]: c for c in (got.get("citations") or [])}
        if set(live_c) != set(got_c):
            return fail(f"{bid} citation id drift")
        for cid, lc in live_c.items():
            gc = got_c[cid]
            if gc.get("evidence_tier") != lc["evidence_tier"]:
                return fail(f"{bid}/{cid} tier drift")
            if gc.get("effect_size") != lc["effect_size"]:
                return fail(f"{bid}/{cid} effect_size drift")
            if gc.get("baseline_value") != lc["baseline_value"]:
                return fail(f"{bid}/{cid} baseline_value drift")

    if not live_tests["named_improvement_per_applicable"]:
        return fail("live applicable rows missing named improvement")
    if not live_tests["inapplicable_popular_control"]["pass"]:
        return fail("live missing popular inapplicable control")
    if live_tests["inapplicable_popular_control"]["benchmark_id"] not in {
        "humaneval",
        "mmlu",
        "osworld",
        "webarena",
        "swe-bench-verified-public",
    }:
        return fail("popular inapplicable control is not a named popular bench")

    stored_tests = doc.get("tests") or {}
    if stored_tests.get("named_improvement_per_applicable") is not True:
        return fail("stored tests.named_improvement_per_applicable is not True")
    if stored_tests.get("inapplicable_popular_control", {}).get("pass") is not True:
        return fail("stored popular inapplicable control did not pass")

    he = live_by["humaneval"]
    if he["applicability_verdict"] != "inapplicable":
        return fail("HumanEval must be the inapplicable popular control")
    if live_by["swe-bench"]["applicability_verdict"] != "applicable":
        return fail("SWE-bench should be applicable")
    if not live_by["swe-bench"].get("named_detectable_improvement"):
        return fail("SWE-bench applicable without named improvement")

    e3 = [
        c
        for r in live_rows
        for c in r["citations"]
        if c["evidence_tier"] == "E3"
    ]
    if not e3:
        return fail("planted E3 headline-without-baseline missing")
    for c in e3:
        owner = next(r for r in live_rows if c["claim_id"] in {x["claim_id"] for x in r["citations"]})
        if c["claim_id"] in (owner.get("promoting_claim_ids") or []):
            return fail(f"E3 {c['claim_id']} promoted a mechanism")

    print(
        json.dumps(
            {
                "applicable": live_tests["applicable_count"],
                "inapplicable": live_tests["inapplicable_count"],
                "control": live_tests["inapplicable_popular_control"]["benchmark_id"],
                "e3_claims": [c["claim_id"] for c in e3],
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"applicable={live_tests['applicable_count']} "
        f"inapplicable={live_tests['inapplicable_count']} "
        f"control={live_tests['inapplicable_popular_control']['benchmark_id']}"
    )
    print("SUCCESS:RES-0093-probe1 live-register")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
