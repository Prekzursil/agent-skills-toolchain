#!/usr/bin/env python3
"""Probe 1: quota-starvation both directions + entitled-empty YIELD.

Direction A: a dominant seat is throttled at its own quota.
Direction B: a legitimately prolific seat under quota is not silenced.
Entitled-empty: quiet has the right and remaining quota, yields, quota untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from detect import PROLIFIC_BAG  # noqa: E402
from fixtures import QUOTA_STARVATION, speakers_for  # noqa: E402
from scheduler import SPEAK, THROTTLE, YIELD, Scheduler, clone_seats  # noqa: E402


def recount(sched: Scheduler) -> dict[str, int]:
    """Independent signal: sum SPEAK tokens from the log, not seat.spoken_tokens."""
    totals: dict[str, int] = {s.id: 0 for s in sched.seats}
    for offer in sched.log:
        if offer.kind == SPEAK and offer.seat_id:
            totals[offer.seat_id] += offer.tokens_used
    return totals


def main() -> int:
    seats = clone_seats(QUOTA_STARVATION["seats"])
    sched = Scheduler(
        seats=seats, turn_length_tokens=int(QUOTA_STARVATION["turn_length_tokens"])
    )
    speakers = speakers_for("quota-starvation")
    sched.run(speakers, max_steps=48)
    spoken = sched.spoken()
    independent = recount(sched)
    yields = sched.yields()
    throttles = sched.throttles()
    kinds = [(o.kind, o.seat_id, o.tokens_used) for o in sched.log]
    print("quota-starvation log", json.dumps(kinds))
    print(
        f"spoken={json.dumps(spoken)} independent_recount={json.dumps(independent)} "
        f"yields={json.dumps(yields)} throttles={json.dumps(throttles)}"
    )

    fail = False
    if spoken != independent:
        print("FAILED:CNL-0047-probe1 spoken totals disagree with log recount")
        fail = True
    # Direction A: dominant throttled, not over quota.
    if spoken.get("dominant") != 50:
        print(f"FAILED:CNL-0047-probe1 dominant spoken={spoken.get('dominant')} want=50")
        fail = True
    if throttles.get("dominant", 0) < 1:
        print("FAILED:CNL-0047-probe1 dominant was not throttled")
        fail = True
    after_first_throttle = False
    dominant_spoke_after_throttle = False
    for offer in sched.log:
        if offer.kind == THROTTLE and offer.seat_id == "dominant":
            after_first_throttle = True
            continue
        if after_first_throttle and offer.kind == SPEAK and offer.seat_id == "dominant":
            dominant_spoke_after_throttle = True
    if dominant_spoke_after_throttle:
        print("FAILED:CNL-0047-probe1 dominant spoke after throttle")
        fail = True
    # Direction B: prolific finishes its 45-token bag, not silenced at equalization.
    if spoken.get("prolific") != PROLIFIC_BAG:
        print(
            f"FAILED:CNL-0047-probe1 prolific spoken={spoken.get('prolific')} "
            f"want={PROLIFIC_BAG} (silenced or over-claim)"
        )
        fail = True
    # Entitled-empty: quiet yielded, quota not consumed, not treated as missing.
    if spoken.get("quiet") != 0:
        print(f"FAILED:CNL-0047-probe1 quiet spoke {spoken.get('quiet')}")
        fail = True
    if yields.get("quiet", 0) < 1:
        print("FAILED:CNL-0047-probe1 quiet never yielded")
        fail = True
    quiet = sched.seat_by_id("quiet")
    if quiet.remaining() != quiet.quota_tokens:
        print("FAILED:CNL-0047-probe1 yield consumed quiet quota")
        fail = True
    # No-right seat is never offered.
    if any(o.seat_id == "observer" for o in sched.log):
        print("FAILED:CNL-0047-probe1 observer without speaking right was offered")
        fail = True
    if fail:
        print("FAILED:CNL-0047-probe1 quota-starvation")
        return 1
    print(
        "SUCCESS:CNL-0047-probe1 quota-starvation both directions "
        "and entitled-empty YIELD"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
