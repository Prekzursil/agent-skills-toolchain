#!/usr/bin/env python3
"""Probe 2: negative control on a false crossover claim.

The check is check_crossover_claim(claimed, mechanical):
  FIRE   when claimed != mechanical  (the state the check is meant to reject)
  SILENT when claimed == mechanical (known-good)

Planted-bad fixture claims crossover_n=3 (tidy-only region, recoveries equal).
Known-good is the design-note crossover, which must equal the mechanical number.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import sim as S  # noqa: E402

NOTE = REPO / "command-center/design/council/CNL-0030-chair-led-topology-and-agenda-control.md"
BAD = HERE / "fixtures" / "planted_bad_crossover.json"


def main() -> int:
    params = S.load_params()
    mechanical = S.crossover_by_min(params)
    reviewer = S.crossover_forward(S.sweep(params))
    if mechanical is None or mechanical != reviewer:
        print("FAILED:CNL-0030-probe2 mechanical crossover missing or paths disagree")
        return 1
    planted = json.loads(BAD.read_text(encoding="utf-8"))
    bad_claim = int(planted["claimed_crossover_n"])
    if not NOTE.is_file():
        print("FAILED:CNL-0030-probe2 design note missing")
        return 1
    doc = json.loads(NOTE.read_text(encoding="utf-8"))
    good_claim = int(doc["size_sweep"]["crossover_n"])
    bad_verdict = S.check_crossover_claim(bad_claim, mechanical)
    good_verdict = S.check_crossover_claim(good_claim, mechanical)
    # Both-states: FIRE on planted-bad, SILENT on known-good.
    fired_on_bad = bad_verdict == "FIRE"
    silent_on_good = good_verdict == "SILENT"
    print(f"mechanical_crossover={mechanical}")
    print(f"planted_bad claimed={bad_claim} check={bad_verdict}")
    print(f"known_good claimed={good_claim} check={good_verdict}")
    print(
        "negative control on the state it is meant to reject: "
        f"claimed_crossover={bad_claim} vs mechanical={mechanical} -> {bad_verdict}"
    )
    print(f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good}")
    if not (fired_on_bad and silent_on_good):
        print("FAILED:CNL-0030-probe2 negative control did not discriminate")
        return 1
    if bad_claim == mechanical:
        print("FAILED:CNL-0030-probe2 planted-bad is not actually bad")
        return 1
    print("SUCCESS:CNL-0030-probe2 negative control FIRE on false crossover, SILENT on true")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
