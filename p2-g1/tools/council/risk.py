"""Council risk-class routing to protocol and quorum floors. IMP-0358.

A declared risk class maps onto minimum protocol strength, quorum, evidence
standard and reviewer count. The class is bound when deliberation starts and is
immutable for the life of the session: a mid-run reclassification is refused
with event RISK_CLASS_MUTATION_REFUSED. Floors are monotone across classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

RISK_CLASSES = ("LOW", "MODERATE", "HIGH", "CRITICAL")
RISK_CLASS_RANK = {name: i for i, name in enumerate(RISK_CLASSES)}

EVENT_MUTATION_REFUSED = "EVENT_MUTATION_REFUSED"
EVENT_RISK_CLASS_MUTATION_REFUSED = "RISK_CLASS_MUTATION_REFUSED"
EVENT_START_WITHOUT_CLASS = "EVENT_START_WITHOUT_CLASS"

EVIDENCE_TIERS = ("any-cited", "peer-reviewed-only", "executable-proof-only")
EVIDENCE_TIER_RANK = {name: i for i, name in enumerate(EVIDENCE_TIERS)}

FLOORS = {
    "LOW": {
        "protocol_strength": 1, "quorum": 2,
        "evidence_standard": "any-cited", "reviewer_count": 1,
    },
    "MODERATE": {
        "protocol_strength": 2, "quorum": 3,
        "evidence_standard": "peer-reviewed-only", "reviewer_count": 1,
    },
    "HIGH": {
        "protocol_strength": 3, "quorum": 5,
        "evidence_standard": "peer-reviewed-only", "reviewer_count": 2,
    },
    "CRITICAL": {
        "protocol_strength": 4, "quorum": 5,
        "evidence_standard": "executable-proof-only", "reviewer_count": 3,
    },
}


class RiskError(ValueError):
    pass
@dataclass
class Result:
    ok: bool = True
    accepted: bool = True
    blocked: bool = False
    refusals: list = field(default_factory=list)
    deficits: list = field(default_factory=list)
    state: str = "SUCCESS"
    verdict: str = "PASS"
    reason: str = ""
    event: str = ""
    bound_class: str = ""

    def as_dict(self) -> dict:
        return {
            "ok": self.ok, "accepted": self.accepted, "blocked": self.blocked,
            "deficits": list(self.deficits), "event": self.event,
            "bound_class": self.bound_class,
        }


def map_risk_class(cls: str) -> dict:
    cls = str(cls).upper()
    if cls not in FLOORS:
        raise RiskError(f"unknown risk class: {cls}")
    return dict(FLOORS[cls])


def _deficits(config: dict, floor: dict) -> list[str]:
    out = []
    for key, need in floor.items():
        have = config.get(key)
        if key == "evidence_standard":
            if EVIDENCE_TIER_RANK.get(str(have), -1) < EVIDENCE_TIER_RANK[str(need)]:
                out.append(key)
        else:
            if not isinstance(have, (int, float)) or have < need:
                out.append(key)
    return out


def at_floor(config: dict, cls: str) -> Result:
    floor = map_risk_class(cls)
    deficits = _deficits(config or {}, floor)
    return Result(ok=not deficits, accepted=not deficits, blocked=bool(deficits),
                  deficits=deficits, bound_class=str(cls).upper())


def evaluate_config(config: dict, cls: str) -> Result:
    return at_floor(config, cls)
def floor_enforcement_matrix() -> dict:
    rows = {}
    for cls in RISK_CLASSES:
        floor = FLOORS[cls]
        below = {}
        rejected = []
        for dim in floor:
            cfg = dict(floor)
            if dim == "evidence_standard":
                idx = EVIDENCE_TIER_RANK[str(floor[dim])]
                if idx < 1:
                    cfg[dim] = None
                else:
                    cfg[dim] = EVIDENCE_TIERS[idx - 1]
            else:
                need = int(floor[dim])
                if need > 0:
                    cfg[dim] = need - 1
                else:
                    cfg[dim] = 0
            verdict = at_floor(cfg, cls)
            below[dim] = verdict.as_dict()
            if verdict.blocked:
                rejected.append(dim)
        entry = {}
        entry["floor"] = dict(floor)
        entry["at_floor_accepted"] = at_floor(dict(floor), cls).accepted
        entry["one_below"] = below
        entry["rejected_dims"] = rejected
        rows[cls] = entry
    return rows


def matrix_is_sound(matrix: dict) -> bool:
    if matrix is None:
        return False
    if len(matrix) != len(RISK_CLASSES):
        return False
    for cls in RISK_CLASSES:
        row = matrix.get(cls)
        if row is None:
            return False
        if row.get("at_floor_accepted") is not True:
            return False
        dims = sorted(row.get("one_below") or {})
        if sorted(row.get("rejected_dims") or []) != dims:
            return False
    ordered = list(RISK_CLASSES)
    for i in range(len(ordered) - 1):
        low = FLOORS[ordered[i]]
        high = FLOORS[ordered[i + 1]]
        for dim in ("protocol_strength", "quorum", "reviewer_count"):
            if int(low[dim]) > int(high[dim]):
                return False
        lo_ev = EVIDENCE_TIER_RANK[str(low["evidence_standard"])]
        hi_ev = EVIDENCE_TIER_RANK[str(high["evidence_standard"])]
        if lo_ev > hi_ev:
            return False
    return True
@dataclass
class DeliberationSession:
    risk_class: str = ""
    allow_late_reclassification: bool = False
    events: list = field(default_factory=list)
    started: bool = False
    bound_config: dict = field(default_factory=dict)

    def start(self, config: dict | None = None) -> Result:
        cls = str(self.risk_class or "").upper()
        if not cls:
            self.events.append(EVENT_START_WITHOUT_CLASS)
            return Result(ok=False, accepted=False, blocked=True,
                          state="BLOCKED", verdict="FAIL",
                          reason="no risk class declared before start",
                          event=EVENT_START_WITHOUT_CLASS)
        map_risk_class(cls)
        self.started = True
        if config is None:
            return Result(bound_class=cls)
        res = at_floor(config, cls)
        if res.blocked:
            self.events.append("EVENT_CONFIG_BELOW_FLOOR")
            return res
        self.bound_config = dict(config)
        return Result(bound_class=cls)

    def reclassify(self, new_class: str) -> Result:
        new = str(new_class).upper()
        if not self.started:
            self.risk_class = new
            return Result(bound_class=new)
        if self.allow_late_reclassification:
            self.risk_class = new
            return Result(ok=False, accepted=True, blocked=False,
                          state="BLOCKED", verdict="FAIL",
                          reason="late reclassification permitted: immutability OFF",
                          bound_class=new)
        self.events.append(EVENT_RISK_CLASS_MUTATION_REFUSED)
        return Result(ok=False, accepted=False, blocked=True,
                      state="BLOCKED", verdict="FAIL",
                      reason="risk class immutable after start",
                      event=EVENT_RISK_CLASS_MUTATION_REFUSED,
                      bound_class=str(self.risk_class).upper())

    def bind_decision(self, config: dict) -> Result:
        cls = str(self.risk_class).upper()
        res = at_floor(config, cls)
        if res.blocked:
            return Result(ok=False, accepted=False, blocked=True,
                          state="BLOCKED", verdict="FAIL",
                          reason="decision on sub-floor config",
                          deficits=res.deficits, bound_class=cls)
        self.bound_config = dict(config)
        return Result(bound_class=cls)


def high_under_low_attack() -> dict:
    session = DeliberationSession(risk_class="LOW")
    session.start(dict(FLOORS["LOW"]))
    mut = session.reclassify("HIGH")
    landed = bool(mut.accepted and not mut.blocked)
    sub_floor = at_floor(dict(FLOORS["LOW"]), "HIGH")
    if sub_floor.accepted:
        landed = True
    return {
        "bound_class": str(session.risk_class),
        "event": mut.event or "",
        "high_under_low": landed,
        "immutability_holds": not landed,
    }


def immutability_holds(session: DeliberationSession) -> bool:
    if not session.started:
        return False
    before = session.risk_class
    other = "CRITICAL"
    if before == "CRITICAL":
        other = "LOW"
    res = session.reclassify(other)
    if res.blocked and session.risk_class == before:
        return True
    return False


def late_declaration_attack() -> dict:
    session = DeliberationSession(risk_class="")
    session.started = True
    res = session.reclassify("HIGH")
    return {
        "event": res.event or "",
        "refused": bool(res.blocked),
        "bound_class": str(session.risk_class),
    }


__all__ = [
    "DeliberationSession", "EVENT_MUTATION_REFUSED",
    "EVENT_RISK_CLASS_MUTATION_REFUSED", "EVENT_START_WITHOUT_CLASS",
    "EVIDENCE_TIERS", "FLOORS", "RISK_CLASSES", "RiskError", "Result",
    "at_floor", "evaluate_config", "floor_enforcement_matrix",
    "high_under_low_attack", "immutability_holds", "late_declaration_attack",
    "map_risk_class", "matrix_is_sound",
]
