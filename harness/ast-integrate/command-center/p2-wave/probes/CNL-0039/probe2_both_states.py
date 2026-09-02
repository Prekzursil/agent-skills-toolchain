#!/usr/bin/env python3
"""Probe 2: both-states attack-real check + family-count plant."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import family as F  # noqa: E402
import runtime as R  # noqa: E402
import transcripts as T  # noqa: E402

RAW = HERE / "probe2-both-states.raw.json"


def main() -> int:
    good = T.all_good()
    bad = T.all_bad()
    per: dict[str, dict] = {}
    fired_on_bad = True
    silent_on_good = True
    for pid in F.ids_from_fixture():
        g = R.check_transcript(good[pid])
        b = R.check_transcript(bad[pid])
        per[pid] = {
            "good_silent": g["silent"],
            "good_verdict": g["verdict"],
            "good_violations": g["violations"],
            "bad_fired": b["fired"],
            "bad_verdict": b["verdict"],
            "bad_violations": b["violations"],
        }
        if not g["silent"] or g["fired"]:
            silent_on_good = False
        if not b["fired"] or b["silent"]:
            fired_on_bad = False
        print(
            f"{pid} good={g['verdict']} silent={g['silent']} "
            f"bad={b['verdict']} fired={b['fired']} "
            f"bad_violations={b['violations']}"
        )

    fixture = F.load_fixture()
    good_count = len(F.ids_from_fixture(fixture))
    planted = F.plant_family_undercount(fixture)
    bad_count = len(F.ids_from_fixture(planted))
    count_silent = good_count == 7
    count_fired = bad_count != 7
    print(
        f"family_count good={good_count} planted={bad_count} "
        f"count_silent={count_silent} count_fired={count_fired}"
    )

    p07_bad = per["P07"]["bad_violations"]
    print("negative_control_verbatim " + json.dumps(p07_bad, separators=(",", ":")))
    print(
        "negative_control_state planted-bad P07 cooperative clash_ledger "
        "with hashes that do not bind to proposition speeches"
    )

    doc = {
        "fired_on_bad": fired_on_bad,
        "silent_on_good": silent_on_good,
        "family_count_silent_on_good": count_silent,
        "family_count_fired_on_plant": count_fired,
        "per_protocol": per,
        "negative_control": {
            "protocol_id": "P07",
            "state": "planted-bad",
            "check_does": (
                "FIRES PERFORMED-ATTACK with violations unbound-quote / no-bound-clash "
                "when clash_ledger hashes do not match proposition speech digests"
            ),
            "verbatim_violations": p07_bad,
        },
        "pass": fired_on_bad and silent_on_good and count_silent and count_fired,
    }
    RAW.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not doc["pass"]:
        print("FAILED:CNL-0039-probe2 both-states did not discriminate")
        return 1
    print("fired_on_bad=True silent_on_good=True")
    print("SUCCESS:CNL-0039-probe2 both-states attack-real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
