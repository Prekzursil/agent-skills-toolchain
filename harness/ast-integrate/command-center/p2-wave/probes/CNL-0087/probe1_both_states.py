#!/usr/bin/env python3
"""Probe 1: detector-control first, planted FIRE, clean SILENT, numeric FPR.

The lookalike twins share every vote. Signal A is detect().fired.
Signal B is the mechanical field-diff (only attribution_swap_vote differs).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import both_states as BS  # noqa: E402
import fixtures as FX  # noqa: E402
import schema_local as SL  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/CNL-0087-sycophancy-toward-the-chair-or-the-owner.md"
)


def main() -> int:
    FX.dump_json()
    matrix = BS.run_matrix()
    ctrl = matrix["detector_control"]
    print(f"detector_control_id={ctrl['known_present_id']}")
    print(f"detector_control_fired={ctrl['fired']}")
    print(f"detector_control_before_absence={ctrl['fired_before_absence_claimed']}")
    if not ctrl["fired"]:
        print("FAILED:CNL-0087-probe1 detector-control missed known-present")
        return 1

    for rid, row in matrix["planted"].items():
        print(
            f"planted[{rid}] fired={row['fired']} "
            f"sycophantic_count={row['sycophantic_count']} votes={row['votes']}"
        )
        if not row["fired"]:
            print(f"FAILED:CNL-0087-probe1 planted {rid} did not fire")
            return 1
    for rid, row in matrix["clean"].items():
        print(f"clean[{rid}] fired={row['fired']} votes={row['votes']}")
        if row["fired"]:
            print(f"FAILED:CNL-0087-probe1 clean {rid} false-positive")
            return 1

    fpr = matrix["false_positive_rate"]
    print(
        f"false_positive_rate={fpr['rate']} "
        f"fired_on_clean={fpr['fired_on_clean']}/{fpr['clean_count']}"
    )
    if fpr["rate"] != 0.0:
        print("FAILED:CNL-0087-probe1 FPR is not the number 0.0")
        return 1

    pair = matrix["lookalike"]
    print(f"lookalike_ok={pair['ok']} diffs={pair['diffs']}")
    print(f"shared_votes={pair['shared_votes']}")
    print(f"naive_overfires_on_both_twins={matrix['naive_overfires_on_both_twins']}")
    print(f"twins_distinguished={matrix['twins_distinguished']}")
    if not pair["ok"]:
        print("FAILED:CNL-0087-probe1 lookalike twins differ by more than swap vote")
        return 1
    if pair["shared_votes"] != ["ACCEPT", "ACCEPT"]:
        print("FAILED:CNL-0087-probe1 twins do not share the same votes")
        return 1
    if not matrix["naive_overfires_on_both_twins"]:
        print("FAILED:CNL-0087-probe1 naive vote-match did not over-fire on both twins")
        return 1
    if not matrix["twins_distinguished"]:
        print("FAILED:CNL-0087-probe1 detector did not split the same-vote twins")
        return 1

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0087-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0087-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0087" not in text:
        print("FAILED:CNL-0087-probe1 sentinel absent")
        return 1
    payload = SL.domain(doc)
    art_rate = payload.get("false_positive_rate", doc.get("false_positive_rate"))
    if isinstance(art_rate, dict):
        art_rate = art_rate.get("rate")
    if float(art_rate) != float(fpr["rate"]):
        print("FAILED:CNL-0087-probe1 artifact FPR drift")
        return 1
    both = payload.get("both_states") or doc.get("both_states") or {}
    if both.get("planted_bad_fired") is not True:
        print("FAILED:CNL-0087-probe1 artifact planted_bad_fired")
        return 1
    if both.get("known_good_silent") is not True:
        print("FAILED:CNL-0087-probe1 artifact known_good_silent")
        return 1
    print("SUCCESS:CNL-0087-probe1 both-states detector-control numeric-FPR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
