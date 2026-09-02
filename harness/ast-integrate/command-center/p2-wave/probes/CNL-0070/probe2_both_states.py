#!/usr/bin/env python3
"""Probe 2: both-states control + negative control recorded verbatim.

The check FIRES on planted-bad (dropped dissent) and is SILENT on known-good.
The negative control is the omitting synthesis: the check must FIRE, naming
the missing dissent_id. A review that did not execute this control is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fixtures as F  # noqa: E402
import preservation as P  # noqa: E402

OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    good = F.known_good()
    bad = F.dropped_dissent()
    none = F.no_dissent()
    unattr = F.unattributed()

    good_r = P.check(good)
    bad_r = P.check(bad)
    none_r = P.check(none)
    unattr_r = P.check(unattr)
    planted = P.plant_drop(good, "D-ALPHA")
    planted_r = P.check(planted)

    negative_control = {
        "rejects": (
            "a synthesis whose minority_report omits a dissent_id that the "
            "transcript recorded (FC-11340 drop class; catalog regression "
            "anchor _USER-PROMPTS.md:11341)"
        ),
        "observed": (
            "fired="
            + str(bad_r["fired"])
            + " missing_ids="
            + json.dumps(bad_r["conservation"]["missing_ids"])
            + " empty_when_mandatory="
            + str(bad_r["empty_when_mandatory"])
        ),
        "verbatim": json.dumps(
            {
                "fixture": "dropped-dissent",
                "fired": bad_r["fired"],
                "silent": bad_r["silent"],
                "missing_ids": bad_r["conservation"]["missing_ids"],
                "transcript_ids": bad_r["conservation"]["transcript_ids"],
                "report_ids": bad_r["conservation"]["report_ids"],
                "empty_when_mandatory": bad_r["empty_when_mandatory"],
            },
            sort_keys=True,
        ),
        "does_on_reject_state": (
            "FIRES; conservation.missing_ids is nonempty; emit of that "
            "synthesis is refused. It does not return silent/HEALTHY."
        ),
    }

    both_states = {
        "fired_on_bad": bad_r["fired"] and planted_r["fired"],
        "silent_on_good": good_r["silent"],
        "silent_on_unanimous_no_dissent": none_r["silent"],
        "fired_on_unattributed": unattr_r["fired"],
        "good_run": {
            "fired": good_r["fired"],
            "silent": good_r["silent"],
            "missing_ids": good_r["conservation"]["missing_ids"],
            "transcript_ids": good_r["conservation"]["transcript_ids"],
            "report_ids": good_r["conservation"]["report_ids"],
        },
        "bad_run": {
            "fired": bad_r["fired"],
            "silent": bad_r["silent"],
            "missing_ids": bad_r["conservation"]["missing_ids"],
            "transcript_ids": bad_r["conservation"]["transcript_ids"],
            "report_ids": bad_r["conservation"]["report_ids"],
        },
        "planted_run": {
            "fired": planted_r["fired"],
            "missing_ids": planted_r["conservation"]["missing_ids"],
        },
    }

    ok = (
        both_states["fired_on_bad"]
        and both_states["silent_on_good"]
        and both_states["silent_on_unanimous_no_dissent"]
        and both_states["fired_on_unattributed"]
        and bad_r["conservation"]["missing_ids"] == ["D-ALPHA"]
        and good_r["conservation"]["empty_difference"]
        and "D-ALPHA" in unattr_r["unattributed_ids"]
        and none_r["recorded_count"] == 0
    )
    doc = {
        "probe": "probe2-both-states",
        "unit_id": "CNL-0070",
        "both_states": both_states,
        "negative_control": negative_control,
        "unattributed": {
            "fired": unattr_r["fired"],
            "unattributed_ids": unattr_r["unattributed_ids"],
        },
        "no_dissent": {
            "fired": none_r["fired"],
            "silent": none_r["silent"],
            "recorded_count": none_r["recorded_count"],
        },
        "pass": bool(ok),
        "reviewer_reran_control": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("BOTH-STATES-GOOD " + json.dumps(both_states["good_run"], sort_keys=True))
    print("BOTH-STATES-BAD " + json.dumps(both_states["bad_run"], sort_keys=True))
    print("NEGATIVE-CONTROL " + negative_control["verbatim"])
    print(
        "fired_on_bad="
        + str(both_states["fired_on_bad"])
        + " silent_on_good="
        + str(both_states["silent_on_good"])
        + " silent_on_unanimous="
        + str(both_states["silent_on_unanimous_no_dissent"])
        + " fired_on_unattributed="
        + str(both_states["fired_on_unattributed"])
    )
    if not ok:
        print("FAILED:CNL-0070-probe2 both-states control did not discriminate")
        return 1
    print("SUCCESS:CNL-0070-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
