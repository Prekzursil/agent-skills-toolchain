#!/usr/bin/env python3
"""Probe 1: planted-defect + detector-control (known-present must FIRE)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from detector import detect, load_council  # noqa: E402

PLANTED = HERE / "fixtures" / "planted-bad.json"


def main() -> int:
    council = load_council(PLANTED)
    result = detect(council)
    fired = bool(result["fires"])
    findings = result["findings"]
    p3 = [f for f in findings if f.get("participant") == "p3"]
    winner = result.get("winner_actual")
    print(f"fixture={council['id']}")
    print(f"detector_control_known_present_found={fired}")
    print(f"fires_on_planted_bad={fired}")
    print(f"p3_flagged={bool(p3)}")
    print(f"winner_actual={winner}")
    if p3:
        print(f"winner_if_stated={p3[0]['winner_if_stated_ballot']}")
        print(f"stated={p3[0]['stated_ranking']}")
        print(f"ballot={p3[0]['submitted_ballot']}")
    print(json.dumps({"result": result}, sort_keys=True))
    if not fired:
        print("FAILED:CNL-0093-probe1 planted-bad did not fire (fixture broken)")
        return 1
    if not p3:
        print("FAILED:CNL-0093-probe1 expected p3 pivotal-misreport-gain")
        return 1
    if winner != "B":
        print(f"FAILED:CNL-0093-probe1 expected winner B, got {winner}")
        return 1
    if p3[0].get("winner_if_stated_ballot") != "A":
        print("FAILED:CNL-0093-probe1 counterfactual winner is not A")
        return 1
    print("SUCCESS:CNL-0093-probe1 planted-bad fires detector-control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
