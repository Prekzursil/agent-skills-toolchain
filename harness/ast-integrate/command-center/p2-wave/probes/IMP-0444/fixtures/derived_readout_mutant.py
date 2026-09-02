"""Planted mutant: readout returns the ceiling constant instead of measuring live counts.

Probe2 must FIRE readout-derived-from-config on this file and stay silent on
the shipped LiveReadout. Both-states control for failure class
readout-derived-from-config.
"""

from __future__ import annotations


class LiveReadout:
    def __init__(self, ceilings):
        self.ceilings = ceilings
        self._samples = []

    def record(self, tick, live, queued):
        self._samples.append((tick, dict(live), dict(queued)))

    def peak(self, substrate):
        return self.ceilings[substrate]

    def peaks(self):
        return dict(self.ceilings)

    def live_at(self, tick, substrate):
        return self.ceilings[substrate]


class ConcurrencyGovernor:
    def __init__(self, ceilings):
        self.ceilings = dict(ceilings)

    def live_counts(self):
        return dict(self.ceilings)

    def sample(self, tick):
        return dict(self.ceilings)
