#!/usr/bin/env python3
"""Probe 2: both-states resolvability + independent re-tabulation.

The check FIRES on the planted-bad forecast fixture and is SILENT on the
known-good one. A family-misassignment mutant must also fire. Reviewer does not
read the author's answer: it re-derives unresolvable ids from the fixtures.
A disagreement in the number blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import runtime as R  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0043-executable-runtime-semantics-for-the-5-forecasting-protoco.md"
)
UNIT = "CNL-0043"
OUT = HERE / "probe2-both-states.raw.json"


def main() -> int:
    bs = R.both_states()
    fam = R.family_count_both_states("FORECASTING")
    live = R.classify_forecasts()
    printable = {
        "resolvability": {
            "silent_on_good": bs["silent_on_good"],
            "fires_on_bad": bs["fires_on_bad"],
            "good": bs["good"],
            "bad": bs["bad"],
        },
        "family_census_mutant": {
            "silent_on_good": fam["silent_on_good"],
            "fires_on_bad": fam["fires_on_bad"],
            "good_n": fam["good_n"],
            "bad_n": fam["bad_n"],
            "flipped_id": fam["flipped_id"],
        },
        "independent_retabulation": {
            "unresolvable_ids": live["unresolvable_ids"],
            "unresolvable_count": live["unresolvable_count"],
            "resolvable_count": live["resolvable_count"],
        },
        "negative_control_resolvability": bs["negative_control"],
        "negative_control_family": fam["negative_control"],
    }
    print(json.dumps(printable, sort_keys=True)[:4000])
    if not bs["pass"]:
        print("FAILED:CNL-0043-probe2 resolvability both-states did not discriminate")
        return 1
    if not fam["pass"]:
        print("FAILED:CNL-0043-probe2 family-count both-states did not discriminate")
        return 1
    if live["unresolvable_count"] != 5 or live["resolvable_count"] != 5:
        print(
            "FAILED:CNL-0043-probe2 retabulation "
            f"unres={live['unresolvable_count']} res={live['resolvable_count']}"
        )
        return 1
    want_bad = ["F-P33-U1", "F-P34-U1", "F-P35-U1", "F-P36-U1", "F-P37-U1"]
    if sorted(live["unresolvable_ids"]) != want_bad:
        print("FAILED:CNL-0043-probe2 unresolvable set", live["unresolvable_ids"])
        return 1
    if not ART.is_file():
        print("FAILED:CNL-0043-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0043-probe2 self-declared {doc.get('state')}")
        return 1
    art_unres = list(
        ((doc.get("unresolvable_as_written") or {}).get("forecast_ids")) or []
    )
    if sorted(art_unres) != want_bad:
        print(
            "FAILED:CNL-0043-probe2 artifact unresolvable set disagrees "
            f"art={art_unres} live={want_bad}"
        )
        return 1
    art_n = int((doc.get("unresolvable_as_written") or {}).get("forecast_count") or -1)
    if art_n != live["unresolvable_count"]:
        print(
            f"FAILED:CNL-0043-probe2 number disagreement art={art_n} live={live['unresolvable_count']}"
        )
        return 1
    nc = doc.get("negative_controls") or []
    if len(nc) < 1:
        print("FAILED:CNL-0043-probe2 artifact missing negative_controls")
        return 1
    blob = {
        "fired_on_bad": True,
        "silent_on_good": True,
        "family_mutant_fired": True,
        "unresolvable_ids": live["unresolvable_ids"],
        "pass": True,
        "negative_control": bs["negative_control"],
    }
    OUT.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"fired_on_bad=True silent_on_good=True family_mutant_fired=True "
        f"unresolvable={live['unresolvable_ids']}"
    )
    print("SUCCESS:CNL-0043-probe2 both-states resolvability and independent recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
