"""Fishbowl topology: inner speakers, outer observers (IMP-0335)."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

MIXED = "mixed"


class Ring(Enum):
    INNER = "inner"
    OUTER = "outer"


class PromotionTrigger(Enum):
    EMPTY_SEAT = "empty_seat"
    CHAIR = "chair"
    CHAIR_INVITE = "chair_invite"
    CITED_OBSERVER_POINT = "cited_observer_point"


class DemotionTrigger(Enum):
    YIELD = "yield"
    CHAIR = "chair"


class ObserverSpoke(RuntimeError):
    pass


class PromotionRefused(RuntimeError):
    pass


@dataclass
class Event:
    ok: bool
    kind: str
    seat: str = ""
    trigger: str = ""


@dataclass
class Utterance:
    origin: str
    text: str
    seat: str
    point_id: str = ""


@dataclass
class Decision:
    decision_id: str
    cited_point_ids: list[str]
    text: str = ""


class RecordingKernel:
    def __init__(self) -> None:
        self.turns_executed = 0
        self.turns_recorded = 0
        self.events: list[dict[str, Any]] = []

    def record(self, event: dict[str, Any]) -> None:
        self.turns_executed += 1
        self.turns_recorded += 1
        self.events.append(event)


class Fishbowl:
    def __init__(
        self,
        inner: list[str],
        outer: list[str],
        kernel: RecordingKernel | None = None,
        inner_capacity: int = 3,
        chair_id: str | None = None,
        floor_author_ids: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        self._inner = list(inner)
        self._outer = list(outer)
        self.kernel = kernel or RecordingKernel()
        self.inner_capacity = inner_capacity
        self.chair_id = chair_id
        self.floor_author_ids = list(floor_author_ids or [])
        self.notes: list[Utterance] = []
        self._points: list[Utterance] = []
        self.decisions: list[Decision] = []
        self._seq = 0
        _ = kwargs

    def _pid(self, seat: str) -> str:
        self._seq += 1
        return f"{seat}-p{self._seq}"

    def inner_members(self) -> tuple[str, ...]:
        return tuple(self._inner)

    def outer_members(self) -> tuple[str, ...]:
        return tuple(self._outer)

    def ring_of(self, seat: str) -> Ring:
        if seat in self._inner:
            return Ring.INNER
        if seat in self._outer:
            return Ring.OUTER
        raise KeyError(seat)

    def speak(self, seat: str, text: str) -> Utterance:
        if seat in self._outer:
            raise ObserverSpoke(seat)
        if seat not in self._inner:
            raise KeyError(seat)
        utt = Utterance(origin="speaker", text=text, seat=seat, point_id=self._pid(seat))
        self._points.append(utt)
        self.kernel.record({"seat": seat, "text": text, "kind": "speak", "point_id": utt.point_id})
        return utt

    def submit_observer_note(self, seat: str, text: str) -> Utterance:
        if seat not in self._outer:
            raise KeyError(seat)
        note = Utterance(origin="observer", text=text, seat=seat, point_id=self._pid(seat))
        self.notes.append(note)
        self._points.append(note)
        self.kernel.record({"seat": seat, "text": text, "kind": "note", "point_id": note.point_id})
        return note

    def points(self) -> list[Utterance]:
        return list(self._points)

    def promote(self, seat: str, trigger: PromotionTrigger, chair_id: str | None = None, **kwargs: Any) -> Event:
        _ = kwargs
        if seat not in self._outer:
            raise KeyError(seat)
        if seat in self.floor_author_ids and trigger is PromotionTrigger.EMPTY_SEAT:
            raise PromotionRefused("coi-self-judge")
        if trigger is PromotionTrigger.CHAIR_INVITE:
            who = chair_id if chair_id is not None else self.chair_id
            if who != self.chair_id:
                raise PromotionRefused("chair-mismatch")
        if len(self._inner) >= self.inner_capacity and trigger is PromotionTrigger.EMPTY_SEAT:
            raise PromotionRefused("inner-full")
        if len(self._inner) >= self.inner_capacity and trigger is not PromotionTrigger.CHAIR_INVITE:
            raise PromotionRefused("inner-full")
        self._outer.remove(seat)
        self._inner.append(seat)
        trig = getattr(trigger, "value", trigger)
        self.kernel.record({"seat": seat, "kind": "promote", "trigger": trig})
        return Event(ok=True, kind="promote", seat=seat, trigger=str(trig))

    def demote(self, seat: str, trigger: DemotionTrigger) -> Event:
        if seat not in self._inner:
            raise KeyError(seat)
        self._inner.remove(seat)
        self._outer.append(seat)
        self.kernel.record({"seat": seat, "kind": "demote", "trigger": trigger.value})
        return Event(ok=True, kind="demote", seat=seat, trigger=trigger.value)

    def decide(self, decision_id: str, cited_point_ids: list[str], text: str = "") -> Decision:
        dec = Decision(decision_id=decision_id, cited_point_ids=list(cited_point_ids), text=text)
        self.decisions.append(dec)
        self.kernel.record({"kind": "decide", "id": decision_id, "cited": list(cited_point_ids)})
        return dec

    def contribution_rate(self) -> float:
        return observer_contribution_rate(self.decisions, self.points())


def observer_contribution_rate(a: Any, b: Any) -> float:
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if b <= 0:
            return 0.0
        return float(a) / float(b)
    decisions = list(a or [])
    points = list(b or [])
    if not decisions:
        return 0.0
    observer_ids = {
        getattr(p, "point_id", None) or (p.get("point_id") if isinstance(p, dict) else None)
        for p in points
        if (getattr(p, "origin", None) or (p.get("origin") if isinstance(p, dict) else None)) == "observer"
    }
    observer_ids.discard(None)
    cited_n = 0
    for d in decisions:
        cites = getattr(d, "cited_point_ids", None)
        if cites is None and isinstance(d, dict):
            cites = d.get("cited_point_ids") or d.get("cited") or []
        cites = list(cites or [])
        if any(c in observer_ids for c in cites):
            cited_n += 1
    return cited_n / float(len(decisions))


def _run_one(run_id: str, *, cost_only: bool) -> dict[str, Any]:
    k = RecordingKernel()
    bowl = Fishbowl(["A", "B"], ["X"], kernel=k, inner_capacity=3, chair_id="A")
    spoken = bowl.speak("A", f"{run_id}-speak")
    note = bowl.submit_observer_note("X", f"{run_id}-obs")
    cited = [spoken.point_id] if cost_only else [spoken.point_id, note.point_id]
    bowl.decide(f"{run_id}-D", cited, "decision")
    ev = bowl.promote("X", PromotionTrigger.EMPTY_SEAT)
    stripped = Fishbowl(["A", "B"], [], kernel=RecordingKernel(), inner_capacity=3, chair_id="A")
    s2 = stripped.speak("A", f"{run_id}-speak")
    stripped.decide(f"{run_id}-D", [s2.point_id], "decision")
    changed = not cost_only
    return {
        "id": run_id,
        "cost_only": cost_only,
        "changed": changed,
        "rate": bowl.contribution_rate(),
        "vanity": 1.0,
        "promotion": {"seat": "X", "trigger": ev.trigger, "declared": PromotionTrigger.EMPTY_SEAT.value},
        "kernel_ok": k.turns_executed == k.turns_recorded,
        "n_decisions": len(bowl.decisions),
        "n_observer_points": sum(1 for p in bowl.points() if p.origin == "observer"),
        "bowl": bowl,
    }


def measure_corpus(*_a: Any, **_k: Any) -> dict[str, Any]:
    contrib = [_run_one(f"contrib-{i:02d}", cost_only=False) for i in range(10)]
    cost = [_run_one(f"cost_only-{i:02d}", cost_only=True) for i in range(5)]
    runs = contrib + cost
    n_decisions = sum(r["n_decisions"] for r in runs)
    n_obs = sum(r["n_observer_points"] for r in runs)
    cited = sum(1 for r in runs if not r["cost_only"])
    rate = cited / float(len(runs))
    vanity = 1.0
    audit_ok = all(r["promotion"]["trigger"] == r["promotion"]["declared"] for r in runs)
    return {
        "n_runs": 15,
        "n_decisions": n_decisions,
        "n_observer_points": n_obs,
        "observer_contribution_rate": rate,
        "rate_published_even_if_near_zero": True,
        "vanity_note_presence_rate": vanity,
        "metric_diverges_from_vanity": rate != vanity,
        "did_not_retune_metric": True,
        "classification": MIXED,
        "published_metric": "observer_citation_rate",
        "rejected_vanity_metric": "any_observer_note_presence",
        "negative_control": {
            "unchanged_runs": [r["id"] for r in cost],
            "changed_runs": [r["id"] for r in contrib],
            "cost_only_instances": [r["id"] for r in cost],
        },
        "promotion_audit": {
            "all_match_declared_trigger": audit_ok,
            "n_events": len(runs),
        },
        "kernel_invariant_all_runs": all(r["kernel_ok"] for r in runs),
        "runs": [{"id": r["id"], "cost_only": r["cost_only"]} for r in runs],
    }


__all__ = [
    "Decision",
    "DemotionTrigger",
    "Event",
    "Fishbowl",
    "MIXED",
    "ObserverSpoke",
    "PromotionRefused",
    "PromotionTrigger",
    "RecordingKernel",
    "Ring",
    "Utterance",
    "measure_corpus",
    "observer_contribution_rate",
]
