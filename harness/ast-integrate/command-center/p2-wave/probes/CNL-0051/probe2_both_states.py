#!/usr/bin/env python3
"""Probe 2 — both-states gaming check + independent recount + negative control.

FIRE on planted-bad (5 wording variants claimed as 5 unique).
SILENT on known-good (6 mechanistically distinct ideas claimed as 6).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reviewer as R  # noqa: E402


def main() -> int:
    bundle = R.recount()
    R.assert_invariants(bundle)
    bad = bundle["planted_bad"]
    good = bundle["known_good"]
    print("probe=probe2_both_states unit=CNL-0051")
    print("PLANTED_BAD_VERBATIM " + json.dumps({
        "verdict": bad["verdict"],
        "fired": bad["fired"],
        "claimed_unique": bad["claimed_unique"],
        "corroborated_unique": bad["corroborated_unique"],
        "lexical_unique": bad["lexical_unique"],
        "mechanism_unique": bad["mechanism_unique"],
        "reason": bad["reason"],
    }, sort_keys=True))
    print("KNOWN_GOOD_VERBATIM " + json.dumps({
        "verdict": good["verdict"],
        "fired": good["fired"],
        "claimed_unique": good["claimed_unique"],
        "corroborated_unique": good["corroborated_unique"],
        "lexical_unique": good["lexical_unique"],
        "mechanism_unique": good["mechanism_unique"],
        "reason": good["reason"],
    }, sort_keys=True))
    print(f"BOTH_STATES fired_on_bad={bad['fired']} silent_on_good={good['silent']}")
    # Negative control: the state the check is meant to reject is planted-bad.
    print(
        "NEGATIVE_CONTROL_VERBATIM "
        "state_meant_to_reject=planted-bad-claimed-unique-inflated-by-wording-variants; "
        f"check_does={bad['verdict']} because {bad['reason']}; "
        "on_known_good="
        f"{good['verdict']} because {good['reason']}"
    )
    print(
        "REVIEWER_RECOUNT planted_bad_keys=1 known_good_keys=6 "
        f"r1_corroborated_bad={bad['corroborated_unique']} "
        f"r1_corroborated_good={good['corroborated_unique']} "
        "r2_tokenizer_agrees=True independent=True"
    )
    if not (bad["fired"] and good["silent"]):
        print("FAILED:CNL-0051-probe2 both-states did not discriminate", file=sys.stderr)
        return 1
    print("SUCCESS:CNL-0051-probe2 both-states and independent recount")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as exc:
        print(f"FAILED:CNL-0051-probe2 {exc}", file=sys.stderr)
        raise SystemExit(1)
