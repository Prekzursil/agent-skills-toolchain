#!/usr/bin/env python3
"""Probe 2: both-states control + negative control recorded verbatim.

The check is 'prolific silenced after dominant quota exhaustion'.
It must FIRE on the planted equalizing scheduler and be SILENT on the
known-good scheduler. Negative control: the check is meant to reject
equalization-silencing; on the known-good state it must stay silent.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from broken import EqualizingScheduler  # noqa: E402
from detect import prolific_silenced_after_dominant_throttle  # noqa: E402
from fixtures import QUOTA_STARVATION, speakers_for  # noqa: E402
from reviewer import independent_review  # noqa: E402
from scheduler import Scheduler, clone_seats  # noqa: E402


def run(cls) -> tuple:
    seats = clone_seats(QUOTA_STARVATION["seats"])
    sched = cls(
        seats=seats, turn_length_tokens=int(QUOTA_STARVATION["turn_length_tokens"])
    )
    sched.run(speakers_for("quota-starvation"), max_steps=48)
    return sched, prolific_silenced_after_dominant_throttle(sched)


def main() -> int:
    good_sched, good = run(Scheduler)
    bad_sched, bad = run(EqualizingScheduler)
    print(
        "both-states known-good",
        json.dumps(
            {
                "fired": good["fired"],
                "reason": good["reason"],
                "spoken": good_sched.spoken(),
            }
        ),
    )
    print(
        "both-states planted-bad",
        json.dumps(
            {
                "fired": bad["fired"],
                "reason": bad["reason"],
                "spoken": bad_sched.spoken(),
            }
        ),
    )
    # Negative control recorded verbatim: the state the check is meant to reject
    # is equalization-silencing of a still-entitled prolific seat.
    print(
        "negative-control "
        "check=prolific_silenced_after_dominant_throttle "
        "reject_state=equalizing-scheduler-silences-prolific-when-dominant-hits-quota "
        f"on_reject_state={bad['fired']} "
        f"on_known_good={good['fired']}"
    )
    silent_on_good = good["fired"] is False
    fires_on_bad = bad["fired"] is True
    if not silent_on_good:
        print("FAILED:CNL-0047-probe2 check was not SILENT on known-good")
        return 1
    if not fires_on_bad:
        print("FAILED:CNL-0047-probe2 check did not FIRE on planted-bad")
        return 1
    review = independent_review()
    print("reviewer", json.dumps(review, sort_keys=True))
    if not review.get("pass"):
        print("FAILED:CNL-0047-probe2 independent reviewer")
        return 1
    print(
        "SUCCESS:CNL-0047-probe2 both-states FIRE on planted-bad SILENT on known-good"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
