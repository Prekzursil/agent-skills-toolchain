#!/usr/bin/env python3
"""Probe 2: both-states control + negative control recorded verbatim.

The check FIRES on planted-bad (gatekeeper off, one-sided forward) and is
SILENT on known-good (completeness seal). Probe 2 re-runs the control
itself; it does not trust probe 1 stdout.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import jury_model as J  # noqa: E402

OUT = HERE / "probe2-negative-control.raw.json"


def main() -> int:
    bad = J.planted_bad()
    good = J.known_good()
    mov_bad = bad["movement"]
    mov_good = good["movement"]

    negative_control = {
        "rejects": (
            "a jury that receives only the presenter's forwarded subset "
            "(gatekeeper off): presenter A forwards claimant-only, presenter "
            "B forwards respondent-only, same pool and same jurors"
        ),
        "observed": (
            "fired="
            + str(bad["check_fires"])
            + " majority_flipped="
            + str(mov_bad["majority_flipped"])
            + " l1="
            + str(mov_bad["l1"])
            + " digest_equal="
            + str(mov_bad["digest_equal"])
            + " presenter_capture="
            + str(bad["presenter_capture"])
        ),
        "verbatim": json.dumps(
            {
                "fixture": "planted-bad-presenter-capture",
                "fired": bad["check_fires"],
                "silent": bad["check_silent"],
                "majority_a": mov_bad["majority_a"],
                "majority_b": mov_bad["majority_b"],
                "majority_flipped": mov_bad["majority_flipped"],
                "l1": mov_bad["l1"],
                "digest_equal": mov_bad["digest_equal"],
                "presenter_capture": bad["presenter_capture"],
            },
            sort_keys=True,
        ),
        "does_on_reject_state": (
            "The check FIRES; majority flips CLAIMANT->RESPONDENT; L1=5; "
            "packet digests differ; presenter_capture=true. It does not "
            "return silent."
        ),
    }

    both_states = {
        "fired_on_bad": bad["check_fires"] and mov_bad["large_movement"],
        "silent_on_good": good["check_silent"] and (not good["presenter_capture"]),
        "good_run": {
            "fired": good["check_fires"],
            "silent": good["check_silent"],
            "l1": mov_good["l1"],
            "majority_flipped": mov_good["majority_flipped"],
            "digest_equal": mov_good["digest_equal"],
            "completeness_a": good["completeness_a"],
            "completeness_b": good["completeness_b"],
        },
        "bad_run": {
            "fired": bad["check_fires"],
            "silent": bad["check_silent"],
            "l1": mov_bad["l1"],
            "majority_flipped": mov_bad["majority_flipped"],
            "digest_equal": mov_bad["digest_equal"],
            "completeness_a": bad["completeness_a"],
            "completeness_b": bad["completeness_b"],
        },
    }

    ok = (
        both_states["fired_on_bad"]
        and both_states["silent_on_good"]
        and mov_bad["majority_flipped"]
        and mov_bad["l1"] == 5
        and (not mov_bad["digest_equal"])
        and mov_good["l1"] == 0
        and mov_good["digest_equal"]
        and good["completeness_a"]
        and good["completeness_b"]
        and (not bad["completeness_a"])
        and (not good["presenter_capture"])
        and bad["presenter_capture"]
    )
    doc = {
        "probe": "probe2-negative-control",
        "unit_id": "CNL-0034",
        "both_states": both_states,
        "negative_control": negative_control,
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
    )
    if not ok:
        print("FAILED:CNL-0034-probe2 both-states control did not discriminate")
        return 1
    print("SUCCESS:CNL-0034-probe2 both-states and negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
