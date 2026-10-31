"""Staggered fan-out admission driven only by an injected clock."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence


@dataclass(frozen=True)
class RailPolicy:
    rail_id: str
    stagger_interval_s: float
    rate_per_s: float | None = None


@dataclass(frozen=True)
class AdmissionEvent:
    unit_id: str
    rail_id: str
    admitted_at: float
    waited_s: float


class UnknownRailError(Exception):
    def __init__(self, rail_id: str) -> None:
        self.rail_id = rail_id
        super().__init__(f"unknown-rail:{rail_id}")


class StaggeredAdmissionScheduler:
    def __init__(self, clock, policies: dict[str, RailPolicy], *, stagger_enabled: bool = True) -> None:
        self.clock = clock
        self.policies = dict(policies)
        self.stagger_enabled = bool(stagger_enabled)
        self._last_by_rail: dict[str, float] = {}

    def admit(self, unit_id: str, rail_id: str) -> AdmissionEvent:
        if rail_id not in self.policies:
            raise UnknownRailError(rail_id)
        policy = self.policies[rail_id]
        now = float(self.clock.now())
        wait = 0.0
        last = self._last_by_rail.get(rail_id)
        if self.stagger_enabled:
            interval = float(policy.stagger_interval_s)
            if last is not None:
                due = last + interval
                wait = max(0.0, due - now)
        elif policy.rate_per_s:
            interval = 1.0 / float(policy.rate_per_s)
            if last is not None:
                due = last + interval
                wait = max(0.0, due - now)
        if wait:
            self.clock.sleep(wait)
            now = float(self.clock.now())
        self._last_by_rail[rail_id] = now
        return AdmissionEvent(unit_id=unit_id, rail_id=rail_id, admitted_at=now, waited_s=wait)

    def admit_fanout(self, cohort: Sequence[tuple[str, str]]) -> list[AdmissionEvent]:
        if self.stagger_enabled:
            by_rail: dict[str, list[str]] = {r: [] for r in self.policies}
            for uid, rail in cohort:
                if rail not in by_rail:
                    raise UnknownRailError(rail)
                by_rail[rail].append(uid)
            events: list[AdmissionEvent] = []
            n = max((len(v) for v in by_rail.values()), default=0)
            rails = list(self.policies)
            for i in range(n):
                t = float(self.clock.now())
                for rail in rails:
                    units = by_rail[rail]
                    if i >= len(units):
                        continue
                    last = self._last_by_rail.get(rail)
                    wait = 0.0 if last is None else max(0.0, t - last)
                    ev = AdmissionEvent(unit_id=units[i], rail_id=rail, admitted_at=t, waited_s=wait)
                    events.append(ev)
                    self._last_by_rail[rail] = t
                if i + 1 < n:
                    interval = float(next(iter(self.policies.values())).stagger_interval_s)
                    self.clock.sleep(interval)
            return events
        return [self.admit(uid, rail) for uid, rail in cohort]


def interarrival_histogram(events: Iterable[AdmissionEvent], *, per_rail: bool = True) -> dict:
    rows = list(events)
    by_rail: dict[str, list[float]] = {}
    for e in rows:
        by_rail.setdefault(e.rail_id, []).append(float(e.admitted_at))
    gaps_by_rail: dict[str, list[float]] = {}
    all_gaps: list[float] = []
    for rail, ts in by_rail.items():
        ts = sorted(ts)
        gaps = [b - a for a, b in zip(ts, ts[1:])]
        gaps_by_rail[rail] = gaps
        all_gaps.extend(gaps)
    times = [float(e.admitted_at) for e in rows]
    span = (max(times) - min(times)) if times else 0.0
    unique = len({round(t, 12) for t in times})
    bins: dict[str, int] = {}
    for g in all_gaps:
        key = f"{round(g, 9):.9f}"
        bins[key] = bins.get(key, 0) + 1
    return {
        "n_events": len(rows),
        "n_rails": len(by_rail),
        "gaps_by_rail": gaps_by_rail if per_rail else {},
        "all_gaps": all_gaps,
        "span": span,
        "unique_timestamps": unique,
        "bins": bins,
    }


def histogram_matches_stagger(hist: dict, interval_s: float) -> bool:
    gaps = list(hist.get("all_gaps") or [])
    if not gaps:
        return False
    return all(abs(g - float(interval_s)) <= 1e-9 for g in gaps)


def is_burst(hist: dict) -> bool:
    return int(hist.get("unique_timestamps") or 0) <= 1
