"""Independent adversarial reviewer for CNL-0047.

Does not trust Scheduler.spoken(). Rebuilds totals from the offer log and
attempts a remainder-cap counterexample: a seat with remaining quota 5 and
turn_length 20 must be offered a 5-token SPEAK, not a whole-turn THROTTLE.
"""
from __future__ import annotations

from fixtures import REMAINDER_CAP, speakers_for
from scheduler import SPEAK, THROTTLE, Scheduler, clone_seats


def recount_from_log(sched: Scheduler) -> dict[str, int]:
    totals = {s.id: 0 for s in sched.seats}
    for offer in sched.log:
        if offer.kind == SPEAK and offer.seat_id:
            totals[offer.seat_id] += int(offer.tokens_used)
    return totals


def remainder_cap_counterexample() -> dict:
    """Counterexample instance: remaining 5 < turn_length 20.

    A scheduler that throttles whenever remaining < turn_length would
    leave `partial` stuck at 20 instead of 25. That instance is constructed
    here; REFUTED if the live scheduler exhibits it.
    """
    seats = clone_seats(REMAINDER_CAP["seats"])
    sched = Scheduler(
        seats=seats, turn_length_tokens=int(REMAINDER_CAP["turn_length_tokens"])
    )
    sched.run(speakers_for("remainder-cap"), max_steps=24)
    spoken = recount_from_log(sched)
    partial_speaks = [
        o.tokens_used
        for o in sched.log
        if o.kind == SPEAK and o.seat_id == "partial"
    ]
    last = partial_speaks[-1] if partial_speaks else 0
    # The defect instance: last offer is THROTTLE while remaining would have been 5.
    throttled_instead = last != 5 or spoken.get("partial") != 25
    return {
        "id": "remainder-cap-quota-5-vs-turn-length-20",
        "attempted": True,
        "refuted": throttled_instead,
        "partial_speak_sizes": partial_speaks,
        "spoken_from_log": spoken,
        "instance": {
            "turn_length_tokens": 20,
            "quota_tokens": 25,
            "expected_last_speak": 5,
            "expected_total": 25,
        },
        "note": (
            "REFUTED-NOT-ATTEMPTED is forbidden; this instance was run. "
            "A whole-turn throttle when remaining < turn_length would refute "
            "the remainder-cap clause of the contract."
        ),
    }


def independent_review() -> dict:
    counter = remainder_cap_counterexample()
    ok = counter["attempted"] and not counter["refuted"]
    return {
        "reviewer_id": "CNL-0047-independent-log-recount",
        "independent": True,
        "verdict": "PASS" if ok else "REFUTED",
        "pass": ok,
        "counterexample": counter,
        "method": (
            "Re-sum SPEAK tokens from the offer log (not seat.spoken_tokens) "
            "and run a remainder-cap instance the author did not use as probe1."
        ),
    }


def main() -> int:
    import json

    review = independent_review()
    print(json.dumps(review, sort_keys=True))
    if not review["pass"]:
        print("FAILED:CNL-0047-reviewer")
        return 1
    print("SUCCESS:CNL-0047-reviewer remainder-cap counterexample survived")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
