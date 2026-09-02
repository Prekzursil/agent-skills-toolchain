#!/usr/bin/env python3
"""Probe 1: detector-control first, planted FIRE, clean SILENT, numeric FPR.

Two mechanically independent signals:
  A) detect().fired on each fixture
  B) distinguisher tuple inequality (kind, termination_cause, cap_remaining)
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

ART = REPO / "command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md"


def main() -> int:
    FX.dump_json()
    matrix = BS.run_matrix()
    ctrl = matrix["detector_control"]
    print(f"detector_control_id={ctrl['known_present_id']}")
    print(f"detector_control_fired={ctrl['fired']}")
    print(f"detector_control_before_absence={ctrl['fired_before_absence_claimed']}")
    if not ctrl["fired"]:
        print("FAILED:CNL-0096-probe1 detector-control missed known-present")
        return 1

    for rid, row in matrix["planted"].items():
        print(f"planted[{rid}] fired={row['fired']} codes={row['codes']}")
        if not row["fired"]:
            print(f"FAILED:CNL-0096-probe1 planted {rid} did not fire")
            return 1
    for rid, row in matrix["clean"].items():
        print(f"clean[{rid}] fired={row['fired']} codes={row['codes']}")
        if row["fired"]:
            print(f"FAILED:CNL-0096-probe1 clean {rid} false-positive")
            return 1

    fpr = matrix["false_positive_rate"]
    print(
        f"false_positive_rate={fpr['rate']} "
        f"fired_on_clean={fpr['fired_on_clean']}/{fpr['clean_count']}"
    )
    if fpr["rate"] != 0.0:
        print("FAILED:CNL-0096-probe1 FPR not zero")
        return 1

    pair = matrix["distinguisher_pair"]
    print(f"distinguisher_genuine={pair['genuine_no_decision']}")
    print(f"distinguisher_exhausted={pair['cap_exhausted']}")
    print(f"pair_distinct={pair['distinct']}")
    if not pair["distinct"]:
        print("FAILED:CNL-0096-probe1 cap-hit not distinguishable from no-decision")
        return 1

    if not ART.is_file():
        print("FAILED:CNL-0096-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    payload = BS.artifact_payload(doc)
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0096-probe1 self-declared {doc.get('state')}")
        return 1
    if "SUCCESS:CNL-0096" not in text:
        print("FAILED:CNL-0096-probe1 sentinel absent")
        return 1
    art_fpr = payload.get("false_positive_rate") or {}
    if float(art_fpr.get("rate")) != float(fpr["rate"]):
        print("FAILED:CNL-0096-probe1 artifact FPR drift")
        return 1
    if payload.get("both_states", {}).get("planted_bad_fired") is not True:
        print("FAILED:CNL-0096-probe1 artifact planted_bad_fired")
        return 1
    if payload.get("both_states", {}).get("known_good_silent") is not True:
        print("FAILED:CNL-0096-probe1 artifact known_good_silent")
        return 1
    print("SUCCESS:CNL-0096-probe1 both-states detector-control numeric-FPR")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
