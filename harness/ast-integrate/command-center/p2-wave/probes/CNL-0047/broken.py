"""Planted-bad scheduler: equalizes remaining quota to the global minimum.

Once any seat exhausts its quota, min(remaining)=0, so every later offer is
throttled. A legitimately prolific seat that still has quota and content is
silenced. This is the defect the both-states control must FIRE on.
"""
from __future__ import annotations

from scheduler import HALT, SPEAK, THROTTLE, YIELD, Offer, Scheduler


class EqualizingScheduler(Scheduler):
    def allowed(self, seat):
        if not seat.speaking_right:
            return 0
        own = seat.remaining()
        floor = min((s.remaining() for s in self.seats if s.speaking_right), default=0)
        return min(int(self.turn_length_tokens), own, floor)
