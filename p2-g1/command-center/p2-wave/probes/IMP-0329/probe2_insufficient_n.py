#!/usr/bin/env python3
"""Named probe 2: n<10 must not emit a bare confident score.

Negative control in the same run: planted_bare_score_record publishes a
numeric Brier on bob's n=9 slice; the detector must fire on that twin and
stay silent on the honest record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.calibration.report import (  # noqa: E402
    INSUFFICIENT_MARKER,
    detect_bare_confident_score,
    format_estimate,
    generate_report,
    hand_computed_predictions,
    is_honest_insufficient,
    planted_bare_score_record,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0329-probe2 {msg}")
    return 1


def main() -> int:
    report = generate_report(hand_computed_predictions())
    bob = next(p for p in report["participants"] if p["participant_id"] == "bob")
    cara = next(p for p in report["participants"] if p["participant_id"] == "cara")
    alice = next(p for p in report["participants"] if p["participant_id"] == "alice")

    if bob["resolved_n"] != 9:
        return fail(f"bob n={bob['resolved_n']} want 9")
    if cara["resolved_n"] != 0:
        return fail(f"cara n={cara['resolved_n']} want 0")
    if not is_honest_insufficient(bob) or not is_honest_insufficient(cara):
        return fail("honest n<10 records missing insufficient-data contract")
    if bob["brier"] is not None or cara["brier"] is not None:
        return fail("honest n<10 published a numeric brier")
    if detect_bare_confident_score(bob) or detect_bare_confident_score(cara):
        return fail("detector fired on honest insufficient records")
    text = format_estimate(bob["resolved_n"], bob["brier"])
    if INSUFFICIENT_MARKER not in text or "not yet meaningful" not in text:
        return fail(f"render omitted marker: {text}")
    if "brier=" in text:
        return fail(f"render still named brier: {text}")

    planted = planted_bare_score_record(bob)
    if not detect_bare_confident_score(planted):
        return fail("negative control silent on planted bare brier")
    if planted["brier"] is None:
        return fail("planted twin did not carry a number (control vacuous)")
    if INSUFFICIENT_MARKER in (planted.get("estimate_sentence") or ""):
        return fail("planted twin still carried the insufficient marker")
    if detect_bare_confident_score(alice):
        return fail("detector fired on n>=10 alice")

    store_bob = next(
        r
        for r in report["calibration_store"]["records"]
        if r["participant_id"] == "bob"
    )
    if store_bob["brier"] is not None or store_bob["rank_class"] != "UNRANKABLE":
        return fail("store published a score for n=9")

    payload = {
        "probe": "probe2-insufficient-n",
        "unit_id": "IMP-0329",
        "bob_n": bob["resolved_n"],
        "cara_n": cara["resolved_n"],
        "bob_marker": bob["insufficient_data_marker"],
        "bob_sentence": bob["estimate_sentence"],
        "bob_brier": bob["brier"],
        "planted_brier": planted["brier"],
        "detector_silent_on_honest": not detect_bare_confident_score(bob),
        "detector_fires_on_planted": detect_bare_confident_score(planted),
        "alice_meaningful": alice["estimate_status"] == "MEANINGFUL",
        "pass": True,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    print(
        f"bob_n={bob['resolved_n']} marker={bob['insufficient_data_marker']} "
        f"planted_fires={payload['detector_fires_on_planted']}"
    )
    print("SUCCESS:IMP-0329-probe2 n<10 insufficient-data marker; planted bare score detected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
