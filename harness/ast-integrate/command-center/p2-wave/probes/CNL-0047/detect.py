"""Detector: prolific seat silenced after a dominant seat exhausted quota.

FIRES when, after the first THROTTLE of `dominant`, `prolific` records no
further SPEAK even though prolific still had remaining quota at that moment
and still had content (its spoken total is below its bag of 45).
SILENT on the known-good engine, which lets prolific finish the remainder.
"""
from __future__ import annotations

from scheduler import SPEAK, THROTTLE, Scheduler


PROLIFIC_BAG = 45


def prolific_silenced_after_dominant_throttle(sched: Scheduler) -> dict:
    dominant_throttle_at = None
    prolific_spoken_at_throttle = 0
    prolific_quota = 0
    for seat in sched.seats:
        if seat.id == "prolific":
            prolific_quota = seat.quota_tokens
    prolific_after = 0
    for i, offer in enumerate(sched.log):
        if (
            dominant_throttle_at is None
            and offer.kind == THROTTLE
            and offer.seat_id == "dominant"
        ):
            dominant_throttle_at = i
            prolific_spoken_at_throttle = sum(
                o.tokens_used
                for o in sched.log[:i]
                if o.kind == SPEAK and o.seat_id == "prolific"
            )
        if dominant_throttle_at is not None and i > dominant_throttle_at:
            if offer.kind == SPEAK and offer.seat_id == "prolific":
                prolific_after += offer.tokens_used
    fired = False
    reason = "no-dominant-throttle"
    if dominant_throttle_at is not None:
        remaining_quota = prolific_quota - prolific_spoken_at_throttle
        remaining_content = PROLIFIC_BAG - prolific_spoken_at_throttle
        could_have_spoken = remaining_quota > 0 and remaining_content > 0
        fired = could_have_spoken and prolific_after == 0
        reason = (
            f"throttle_at={dominant_throttle_at} prolific_then={prolific_spoken_at_throttle} "
            f"remaining_quota={remaining_quota} remaining_content={remaining_content} "
            f"prolific_after={prolific_after} fired={fired}"
        )
    return {
        "fired": fired,
        "reason": reason,
        "dominant_throttle_at": dominant_throttle_at,
        "prolific_spoken_at_throttle": prolific_spoken_at_throttle,
        "prolific_after": prolific_after,
    }
