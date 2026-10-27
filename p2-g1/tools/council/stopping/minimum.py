"""Minimum-deliberation stopping gate (IMP-0309).

Instant consensus with unmet floors must not stop while the gate is enabled.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

CONDITION_ROUNDS = "min_rounds"
CONDITION_BRIEFS = "independent_briefs"
CONDITION_OBJECTIONS = "objections_considered"
FLOOR_BLOCK = "FLOOR_BLOCK"
STOP_ALLOWED = "STOP_ALLOWED"
GATE_DISABLED_STOP = "GATE_DISABLED_STOP"
CEILING_ESCALATE = "CEILING_ESCALATE"


class FloorValidationError(ValueError):
    pass


class FloorSpec(dict):
    pass


@dataclass
class ConditionRow:
    id: str
    required: Any
    observed: Any
    met: bool

    @property
    def measured(self) -> Any:
        return self.observed

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "required": self.required,
            "observed": self.observed,
            "measured": self.observed,
            "met": self.met,
        }


@dataclass
class Decision:
    may_stop: bool
    reason: str
    unmet: tuple[str, ...]
    condition_table: list[ConditionRow]
    stop_expression_true: bool
    ceiling_reached: bool = False

    def as_dict(self) -> dict[str, Any]:
        return {
            "may_stop": self.may_stop,
            "reason": self.reason,
            "unmet": list(self.unmet),
            "stop_expression_true": self.stop_expression_true,
            "ceiling_reached": self.ceiling_reached,
        }


@dataclass
class Trace:
    decisions: list[Decision] = field(default_factory=list)
    stopped: bool = False


def evaluate(spec: dict[str, Any], state: dict[str, Any]) -> Decision:
    rounds_req = int(spec.get("min_rounds") or 0)
    briefs_req = int(spec.get("min_independent_briefs") or 0)
    obj_req = int(spec.get("min_objections_considered") or 0)
    max_rounds = int(spec.get("max_rounds") or 0)
    rounds_obs = int(state.get("rounds_completed") or 0)
    briefs_obs = int(
        state.get("independent_briefs")
        or len(state.get("independent_brief_authors") or [])
    )
    obj_obs = int(
        state.get("objections_considered")
        or len(state.get("objection_ids_considered") or [])
    )
    rows = [
        ConditionRow(CONDITION_ROUNDS, rounds_req, rounds_obs, rounds_obs >= rounds_req),
        ConditionRow(CONDITION_BRIEFS, briefs_req, briefs_obs, briefs_obs >= briefs_req),
        ConditionRow(CONDITION_OBJECTIONS, obj_req, obj_obs, obj_obs >= obj_req),
    ]
    unmet = tuple(r.id for r in rows if not r.met)
    stop_expr = bool(state.get("stop_expression_true") or state.get("consensus"))
    ceiling_reached = bool(max_rounds and rounds_obs >= max_rounds)
    if not spec.get("gate_enabled", True):
        return Decision(
            may_stop=True,
            reason=GATE_DISABLED_STOP,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=stop_expr,
            ceiling_reached=ceiling_reached,
        )
    if ceiling_reached and unmet:
        return Decision(
            may_stop=False,
            reason=CEILING_ESCALATE,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=stop_expr,
            ceiling_reached=True,
        )
    may_stop = stop_expr and not unmet
    return Decision(
        may_stop=may_stop,
        reason=STOP_ALLOWED if may_stop else FLOOR_BLOCK,
        unmet=unmet,
        condition_table=rows,
        stop_expression_true=stop_expr,
        ceiling_reached=ceiling_reached,
    )


def format_condition_table(decision: Decision) -> str:
    lines = ["condition required observed met"]
    for row in decision.condition_table:
        lines.append(f"{row.id} {row.required} {row.observed} {row.met}")
    lines.append(f"may_stop={decision.may_stop} reason={decision.reason}")
    return "\n".join(lines)


def run_rounds(spec: dict[str, Any], states: list[dict[str, Any]]) -> Trace:
    trace = Trace()
    for state in states:
        decision = evaluate(spec, state)
        trace.decisions.append(decision)
        if decision.may_stop:
            trace.stopped = True
            break
    return trace


__all__ = [
    "CEILING_ESCALATE",
    "CONDITION_BRIEFS",
    "CONDITION_OBJECTIONS",
    "CONDITION_ROUNDS",
    "Decision",
    "FLOOR_BLOCK",
    "FloorSpec",
    "FloorValidationError",
    "GATE_DISABLED_STOP",
    "STOP_ALLOWED",
    "Trace",
    "evaluate",
    "format_condition_table",
    "run_rounds",
]
