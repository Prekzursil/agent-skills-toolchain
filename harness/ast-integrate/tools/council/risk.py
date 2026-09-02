"""Risk-class routing to stricter protocol and quorum floors (IMP-0358).

Every deliberation declares a risk class *before* it starts.  The class maps
to a floor on four dimensions -- protocol strength, quorum, evidence standard
and reviewer count -- and a configuration is accepted only if it meets or
exceeds the floor on every dimension.  Once a session has started the class
is bound: a different class is refused with a ``RISK_CLASS_MUTATION_REFUSED``
event and the run keeps its original floors, so a HIGH-risk question can never
be taken under a LOW-risk configuration by reclassifying mid-run.

``allow_late_reclassification=True`` is the deliberate mutant for the negative
control: with it the class *does* move after start, and ``immutability_holds``
must then report False.
"""
from __future__ import annotations

from typing import Any

SPEC_ANCHOR = (
    "command-center/WORK-UNIT-CATALOG.json work_units[id=IMP-0358] "
    "title='Risk-class routing to stricter protocol and quorum floors'"
)

RISK_CLASSES: tuple[str, ...] = ("LOW", "MODERATE", "HIGH", "CRITICAL")

# Ordinal scales; index order is strength order.
PROTOCOL_STRENGTHS: tuple[str, ...] = ("informal", "deliberative", "adversarial", "judicial")
EVIDENCE_STANDARDS: tuple[str, ...] = (
    "assertion",
    "sourced",
    "reproducible",
    "independent-reproduction",
)
DIMENSIONS: tuple[str, ...] = (
    "protocol_strength",
    "quorum",
    "evidence_standard",
    "reviewer_count",
)

FLOORS: dict[str, dict[str, Any]] = {
    "LOW": {
        "protocol_strength": "informal",
        "quorum": 1,
        "evidence_standard": "assertion",
        "reviewer_count": 0,
    },
    "MODERATE": {
        "protocol_strength": "deliberative",
        "quorum": 3,
        "evidence_standard": "sourced",
        "reviewer_count": 1,
    },
    "HIGH": {
        "protocol_strength": "adversarial",
        "quorum": 4,
        "evidence_standard": "reproducible",
        "reviewer_count": 2,
    },
    "CRITICAL": {
        "protocol_strength": "judicial",
        "quorum": 5,
        "evidence_standard": "independent-reproduction",
        "reviewer_count": 3,
    },
}

EVENT_SESSION_STARTED = "RISK_SESSION_STARTED"
EVENT_SESSION_CONCLUDED = "RISK_SESSION_CONCLUDED"
EVENT_CLASS_DECLARED = "RISK_CLASS_DECLARED"
EVENT_CLASS_MUTATED = "RISK_CLASS_MUTATED"
EVENT_MUTATION_REFUSED = "RISK_CLASS_MUTATION_REFUSED"
EVENT_START_WITHOUT_CLASS = "RISK_START_WITHOUT_CLASS_REFUSED"
EVENT_FLOOR_VIOLATION = "RISK_FLOOR_VIOLATION"
EVENT_CONCLUDE_REFUSED = "RISK_CONCLUDE_REFUSED"


class RiskClassError(ValueError):
    pass


def _require_class(risk_class: Any) -> str:
    cls = str(risk_class).upper() if risk_class is not None else ""
    if cls not in FLOORS:
        raise RiskClassError(f"unknown risk class {risk_class!r}; expected one of {RISK_CLASSES}")
    return cls


def _rank(scale: tuple[str, ...], value: Any) -> int:
    """Position on an ordinal scale; unknown values rank below everything."""
    try:
        return scale.index(str(value))
    except ValueError:
        return -1


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def at_floor(risk_class: str) -> dict[str, Any]:
    """A configuration sitting exactly on the floor of ``risk_class``."""
    return dict(FLOORS[_require_class(risk_class)])


def map_risk_class(risk_class: str) -> dict[str, Any]:
    """Route a class to its floors; the class is immutable once a run starts."""
    cls = _require_class(risk_class)
    row = dict(FLOORS[cls])
    row["risk_class"] = cls
    row["immutable_after_start"] = True
    return row


def evaluate_config(risk_class: str, config: dict[str, Any]) -> dict[str, Any]:
    """Accept ``config`` only if every dimension meets the class floor."""
    cls = _require_class(risk_class)
    floor = FLOORS[cls]
    violations: list[dict[str, Any]] = []
    for dim in DIMENSIONS:
        observed = config.get(dim) if isinstance(config, dict) else None
        if dim == "protocol_strength":
            below = _rank(PROTOCOL_STRENGTHS, observed) < _rank(PROTOCOL_STRENGTHS, floor[dim])
        elif dim == "evidence_standard":
            below = _rank(EVIDENCE_STANDARDS, observed) < _rank(EVIDENCE_STANDARDS, floor[dim])
        else:
            below = _as_int(observed) < int(floor[dim])
        if below:
            violations.append(
                {
                    "dimension": dim,
                    "floor": floor[dim],
                    "observed": observed,
                    "reason": "below-floor" if observed is not None else "missing",
                }
            )
    return {
        "risk_class": cls,
        "accepted": not violations,
        "violations": violations,
        "config": dict(config) if isinstance(config, dict) else config,
    }


def _one_below(config: dict[str, Any], dim: str) -> dict[str, Any] | None:
    """The same configuration weakened by one step on ``dim`` (None at bottom)."""
    weakened = dict(config)
    if dim == "protocol_strength":
        idx = _rank(PROTOCOL_STRENGTHS, config[dim])
        if idx <= 0:
            return None
        weakened[dim] = PROTOCOL_STRENGTHS[idx - 1]
    elif dim == "evidence_standard":
        idx = _rank(EVIDENCE_STANDARDS, config[dim])
        if idx <= 0:
            return None
        weakened[dim] = EVIDENCE_STANDARDS[idx - 1]
    else:
        if int(config[dim]) <= 0:
            return None
        weakened[dim] = int(config[dim]) - 1
    return weakened


def floor_enforcement_matrix() -> list[dict[str, Any]]:
    """Per class: the at-floor config, then one-below on each dimension.

    One-below rows that cannot be built (already at the bottom of a scale,
    e.g. LOW reviewer_count=0) are still emitted with ``case='floor-is-min'``
    so the matrix shape is identical for every class.
    """
    rows: list[dict[str, Any]] = []
    for cls in RISK_CLASSES:
        base = at_floor(cls)
        base_verdict = evaluate_config(cls, base)
        rows.append(
            {
                "risk_class": cls,
                "case": "at-floor",
                "dimension": None,
                "config": base,
                "accepted": base_verdict["accepted"],
                "violations": base_verdict["violations"],
            }
        )
        for dim in DIMENSIONS:
            weakened = _one_below(base, dim)
            if weakened is None:
                rows.append(
                    {
                        "risk_class": cls,
                        "case": "floor-is-min",
                        "dimension": dim,
                        "config": base,
                        "accepted": base_verdict["accepted"],
                        "violations": base_verdict["violations"],
                    }
                )
                continue
            verdict = evaluate_config(cls, weakened)
            rows.append(
                {
                    "risk_class": cls,
                    "case": "one-below",
                    "dimension": dim,
                    "config": weakened,
                    "accepted": verdict["accepted"],
                    "violations": verdict["violations"],
                }
            )
    return rows


def matrix_is_sound(rows: list[dict[str, Any]]) -> list[str]:
    """Return the list of soundness errors (empty when the matrix is sound)."""
    errors: list[str] = []
    seen: set[tuple[str, str, str | None]] = set()
    for row in rows:
        key = (row.get("risk_class"), row.get("case"), row.get("dimension"))
        if key in seen:
            errors.append(f"duplicate row {key}")
        seen.add(key)
        cls = row.get("risk_class")
        if cls not in FLOORS:
            errors.append(f"unknown class in row {key}")
            continue
        recomputed = evaluate_config(cls, row.get("config") or {})
        if recomputed["accepted"] != row.get("accepted"):
            errors.append(f"row {key} accepted={row.get('accepted')} but re-evaluation says {recomputed['accepted']}")
        if row.get("case") in ("at-floor", "floor-is-min"):
            if row.get("accepted") is not True:
                errors.append(f"row {key} at-floor config was rejected")
        elif row.get("case") == "one-below":
            if row.get("accepted") is not False:
                errors.append(f"row {key} one-below config was accepted")
            dims = [v.get("dimension") for v in row.get("violations", [])]
            if dims != [row.get("dimension")]:
                errors.append(f"row {key} expected exactly one violation on {row.get('dimension')}, got {dims}")
        else:
            errors.append(f"row {key} has unknown case")
    for cls in RISK_CLASSES:
        if (cls, "at-floor", None) not in seen:
            errors.append(f"class {cls} has no at-floor row")
        for dim in DIMENSIONS:
            if (cls, "one-below", dim) not in seen and (cls, "floor-is-min", dim) not in seen:
                errors.append(f"class {cls} has no row for dimension {dim}")
    # Floors must be monotone: each class at least as strict as the one below.
    for lower, upper in zip(RISK_CLASSES, RISK_CLASSES[1:]):
        if evaluate_config(lower, FLOORS[upper])["accepted"] is not True:
            errors.append(f"{upper} floors do not meet {lower} floors; classes are not ordered")
    return errors


class DeliberationSession:
    """A run bound to one risk class from start to conclusion."""

    def __init__(
        self,
        config: dict[str, Any],
        risk_class: str | None = None,
        *,
        allow_late_reclassification: bool = False,
    ) -> None:
        self.config: dict[str, Any] = dict(config)
        self._declared_class: str | None = _require_class(risk_class) if risk_class else None
        self._bound_class: str | None = None
        self.allow_late_reclassification = bool(allow_late_reclassification)
        self.started = False
        self.concluded = False
        self.events: list[dict[str, Any]] = []

    @property
    def bound_class(self) -> str | None:
        return self._bound_class

    @property
    def declared_class(self) -> str | None:
        return self._declared_class

    def _emit(self, event_type: str, **fields: Any) -> dict[str, Any]:
        event = {"type": event_type, "seq": len(self.events) + 1}
        event.update(fields)
        self.events.append(event)
        return event

    def start(self) -> dict[str, Any]:
        if self.started:
            return {"accepted": False, "event": self._emit("RISK_ALREADY_STARTED"), "reason": "already started"}
        if self._declared_class is None:
            return {
                "accepted": False,
                "event": self._emit(EVENT_START_WITHOUT_CLASS),
                "reason": "a risk class must be declared before start",
            }
        verdict = evaluate_config(self._declared_class, self.config)
        if not verdict["accepted"]:
            return {
                "accepted": False,
                "event": self._emit(
                    EVENT_FLOOR_VIOLATION,
                    risk_class=self._declared_class,
                    violations=verdict["violations"],
                ),
                "reason": "configuration below the floors of the declared class",
                "violations": verdict["violations"],
            }
        self._bound_class = self._declared_class
        self.started = True
        return {
            "accepted": True,
            "event": self._emit(EVENT_SESSION_STARTED, risk_class=self._bound_class, floors=dict(FLOORS[self._bound_class])),
            "bound_class": self._bound_class,
        }

    def reclassify(self, new_class: str) -> dict[str, Any]:
        cls = _require_class(new_class)
        if not self.started:
            previous = self._declared_class
            self._declared_class = cls
            return {
                "accepted": True,
                "noop": previous == cls,
                "mutated": False,
                "event": self._emit(EVENT_CLASS_DECLARED, from_class=previous, to_class=cls),
            }
        if cls == self._bound_class:
            return {"accepted": True, "noop": True, "mutated": False, "event": None}
        if self.allow_late_reclassification:
            # Deliberate mutant path: the bound class moves after start.
            previous = self._bound_class
            self._bound_class = cls
            self._declared_class = cls
            return {
                "accepted": True,
                "noop": False,
                "mutated": True,
                "event": self._emit(EVENT_CLASS_MUTATED, from_class=previous, to_class=cls),
            }
        return {
            "accepted": False,
            "noop": False,
            "mutated": False,
            "event": self._emit(EVENT_MUTATION_REFUSED, from_class=self._bound_class, to_class=cls),
            "reason": "risk class is immutable after start",
        }

    def conclude(self) -> dict[str, Any]:
        if not self.started or self._bound_class is None:
            return {"accepted": False, "event": self._emit(EVENT_CONCLUDE_REFUSED, reason="not started")}
        if self.concluded:
            return {"accepted": False, "event": self._emit(EVENT_CONCLUDE_REFUSED, reason="already concluded")}
        verdict = evaluate_config(self._bound_class, self.config)
        if not verdict["accepted"]:
            return {
                "accepted": False,
                "event": self._emit(
                    EVENT_CONCLUDE_REFUSED,
                    reason="configuration below bound-class floors",
                    violations=verdict["violations"],
                ),
                "violations": verdict["violations"],
            }
        self.concluded = True
        return {
            "accepted": True,
            "event": self._emit(EVENT_SESSION_CONCLUDED, risk_class=self._bound_class),
            "bound_class": self._bound_class,
        }


def immutability_holds(session: DeliberationSession, new_class: str) -> bool:
    """Try to move a started session to ``new_class``; True iff it did not move."""
    before = session.bound_class
    result = session.reclassify(new_class)
    if before is None:
        # Nothing was bound; immutability is not yet in force.
        return False
    return session.bound_class == before and not result.get("mutated")


def high_under_low_attack(*, allow_late_reclassification: bool = False) -> dict[str, Any]:
    """Start LOW on LOW floors, then try to take HIGH mid-run."""
    session = DeliberationSession(
        config=at_floor("LOW"),
        risk_class="LOW",
        allow_late_reclassification=allow_late_reclassification,
    )
    start = session.start()
    mutation = session.reclassify("HIGH")
    bound = session.bound_class
    high_eval = evaluate_config("HIGH", session.config)
    conclude = session.conclude()
    return {
        "allow_late_reclassification": allow_late_reclassification,
        "start": start,
        "mutation": mutation,
        "bound_class": bound,
        "config": dict(session.config),
        "high_floors_met_by_config": high_eval["accepted"],
        "high_risk_taken_under_low_config": bound == "HIGH" and high_eval["accepted"] is False,
        "immutability_holds": bound == "LOW" and not mutation.get("mutated"),
        "conclude": conclude,
        "events": list(session.events),
    }


def late_declaration_attack() -> dict[str, Any]:
    """Start with no class, then declare HIGH late under a LOW configuration."""
    session = DeliberationSession(config=at_floor("LOW"), risk_class=None)
    start = session.start()
    refused = start.get("accepted") is False and (start.get("event") or {}).get("type") == EVENT_START_WITHOUT_CLASS
    late = session.reclassify("HIGH")
    restart = session.start()
    return {
        "start": start,
        "refused_start_without_class": refused,
        "started": session.started,
        "late_declaration": late,
        "restart": restart,
        "bound_class": session.bound_class,
        "late_high_bound_under_low_config": session.started and session.bound_class == "HIGH",
        "events": list(session.events),
    }


__all__ = [
    "DIMENSIONS",
    "DeliberationSession",
    "EVENT_CLASS_DECLARED",
    "EVENT_CLASS_MUTATED",
    "EVENT_CONCLUDE_REFUSED",
    "EVENT_FLOOR_VIOLATION",
    "EVENT_MUTATION_REFUSED",
    "EVENT_SESSION_CONCLUDED",
    "EVENT_SESSION_STARTED",
    "EVENT_START_WITHOUT_CLASS",
    "EVIDENCE_STANDARDS",
    "FLOORS",
    "PROTOCOL_STRENGTHS",
    "RISK_CLASSES",
    "RiskClassError",
    "SPEC_ANCHOR",
    "at_floor",
    "evaluate_config",
    "floor_enforcement_matrix",
    "high_under_low_attack",
    "immutability_holds",
    "late_declaration_attack",
    "map_risk_class",
    "matrix_is_sound",
]
