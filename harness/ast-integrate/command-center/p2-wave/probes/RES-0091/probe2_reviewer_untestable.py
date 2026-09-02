#!/usr/bin/env python3
"""Probe 2: independent reviewer — re-run checkers; name two untestable properties.

Confirms detectors fire only on the broken fixture, that opinion is not asserted,
and that two desirable properties are named as fundamentally untestable with why.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from properties import (  # noqa: E402
    PLANTED_CREDENTIAL,
    REAL_ARTIFACT_REL,
    UNTESTABLE,
    canonical,
    credential_absence,
    counter_monotonicity,
    file_load_idempotence,
    good_receipt,
    mono_broken,
    mono_good,
    planted_credential_doc,
    producer_broken_time,
    producer_good,
    real_artifact_path,
    rerun_idempotence,
    run_property_battery,
    schema_validity,
)


def fail(msg: str) -> int:
    print(f"FAILED:RES-0091-probe2 {msg}")
    return 1


def main() -> int:
    # Re-run the same checkers from this reviewer script (not a cached summary).
    good = good_receipt(7, state="FAILED")
    if not schema_validity(good)["pass"]:
        return fail("reviewer: FAILED-state good fixture did not pass schema")
    if schema_validity([1, 2, 3])["pass"]:
        return fail("reviewer: array fixture did not fail schema")
    if schema_validity({"unit_id": 91, "state": "SUCCESS"})["pass"]:
        return fail("reviewer: bad unit_id did not fail schema")

    if not rerun_idempotence(producer_good(11), repeats=3)["pass"]:
        return fail("reviewer: good producer was not idempotent")
    if rerun_idempotence(producer_broken_time(11), repeats=3)["pass"]:
        return fail("reviewer: time/counter producer stayed silent (still stable)")

    if not credential_absence(canonical(good_receipt(3)))["pass"]:
        return fail("reviewer: clean fixture flagged as credential")
    planted = canonical(planted_credential_doc(3))
    if credential_absence(planted)["pass"]:
        return fail("reviewer: planted credential was silent")
    if PLANTED_CREDENTIAL not in planted:
        return fail("reviewer: planted fixture missing token")

    if not counter_monotonicity(mono_good(5))["pass"]:
        return fail("reviewer: monotone trace failed")
    if counter_monotonicity(mono_broken(5))["pass"]:
        return fail("reviewer: dipped trace was silent")

    real = real_artifact_path()
    if not real.is_file():
        return fail("reviewer: real artifact missing")
    if not file_load_idempotence(real)["pass"]:
        return fail("reviewer: real artifact double-load mismatch")
    live = json.loads(real.read_text(encoding="utf-8"))
    schema_live = schema_validity(live)
    if not schema_live["pass"]:
        return fail(f"reviewer: real artifact schema {schema_live}")

    if len(UNTESTABLE) < 2:
        return fail("need >=2 named untestable properties")
    for row in UNTESTABLE:
        why = str(row.get("why") or "")
        if len(why) < 80:
            return fail(f"{row.get('id')} why too short")
        if "oracle" not in why.lower() and "judgment" not in why.lower():
            return fail(f"{row.get('id')} does not explain untestability")

    battery = run_property_battery()
    ids = {p["id"] for p in battery["implemented_properties"]}
    for banned in ("semantic-truth", "user-intent", "helpfulness", "opinion-true"):
        if any(banned in i for i in ids):
            return fail(f"implemented set contains opinion property {banned}")
    if battery["untestable_count"] < 2:
        return fail("battery untestable_count < 2")
    # Independent of probe1's print: require live discrimination again.
    if not battery["all_pass"]:
        return fail("reviewer battery all_pass=false")

    report = {
        "reviewer_id": "RES-0091-probe2-reviewer-untestable",
        "independent": True,
        "fires_only_on_broken": True,
        "known_good_schema_includes_FAILED": True,
        "implemented_ids": sorted(ids),
        "untestable": [
            {"id": u["id"], "name": u["name"]} for u in UNTESTABLE
        ],
        "real_artifact": REAL_ARTIFACT_REL,
        "pass": True,
    }
    print(json.dumps(report, sort_keys=True))
    print("untestable=" + ",".join(u["id"] for u in UNTESTABLE))
    print("SUCCESS:RES-0091-probe2 reviewer both-states and two untestable properties")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
