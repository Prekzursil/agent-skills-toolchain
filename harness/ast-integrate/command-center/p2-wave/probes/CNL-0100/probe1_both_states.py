#!/usr/bin/env python3
"""Probe 1: both-states + detector-control + numeric false-positive rate.

Signal 1 (structural): non-operator provenance in the instruction channel.
The planted-bad run is assemble(mode=raw) on the dissent payload; the
known-good run is assemble(mode=fence) on the SAME turns.

Detector-control: the known-present (raw) instance is required to FIRE
before any silence on the good fixture is reported.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import boundary as B  # noqa: E402
import fixtures as F  # noqa: E402

OUT = HERE / "probe1-both-states.raw.json"
SCRATCH = HERE / "scratch" / "probe1"


def main() -> int:
    F.write_fixture_files()
    if SCRATCH.exists():
        shutil.rmtree(SCRATCH)
    SCRATCH.mkdir(parents=True)

    # Detector-control FIRST: refuse to talk about absence until known-present fires.
    control_turns = F.planted_turns("dissent")
    control_asm = B.assemble(control_turns, mode="raw")
    control = B.detect(control_asm)
    control_line = B.dump(
        {
            "known_present_found": control["fired"],
            "leak_count": control["leak_count"],
            "carriers": [x["carrier"] for x in control["leaks"]],
        }
    )
    if not control["fired"]:
        print("FAILED:CNL-0100-probe1 detector-control did not find known-present")
        print(control_line)
        return 1
    print(f"detector_control_known_present_found=True {control_line}")

    pair = B.run_pair(control_turns, SCRATCH / "pair")
    if not pair["fired_on_bad"]:
        print("FAILED:CNL-0100-probe1 planted-bad did not fire")
        return 1
    if not pair["silent_on_good"]:
        print("FAILED:CNL-0100-probe1 known-good was not silent")
        return 1

    fp = B.false_positive_rate(F.mention_corpus())
    if fp["numerator"] != 0:
        print(f"FAILED:CNL-0100-probe1 false-positive rate {fp['rate']} on mention corpus")
        return 1
    if fp["denominator"] < 10:
        print("FAILED:CNL-0100-probe1 mention corpus smaller than 10")
        return 1

    bad_line = B.dump(pair["bad"]["detect"])
    good_line = B.dump(pair["good"]["detect"])
    print(f"fired_on_bad=True {bad_line}")
    print(f"silent_on_good=True {good_line}")
    print(
        f"false_positive_rate={fp['rate']} "
        f"numerator={fp['numerator']} denominator={fp['denominator']}"
    )

    doc = {
        "fired_on_bad": True,
        "silent_on_good": True,
        "detector_control_known_present_found": True,
        "before_absence_reported": True,
        "false_positive_rate": fp["rate"],
        "false_positive_numerator": fp["numerator"],
        "false_positive_denominator": fp["denominator"],
        "bad_run_verbatim": bad_line,
        "good_run_verbatim": good_line,
        "detector_control_verbatim": control_line,
        "pass": True,
    }
    OUT.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("SUCCESS:CNL-0100-probe1 both-states detector-control false-positive-rate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
