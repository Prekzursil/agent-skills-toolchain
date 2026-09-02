"""Minimum-deliberation floors: a satisfied stopping expression may not end a
council that has not actually deliberated.

Two consumers share this module and it keeps both contracts on purpose:

* IMP-0309 (``evaluate`` / ``run_rounds``): a per-instant *decision* over three
  numeric floors (rounds, independent briefs, objections considered) with a
  reason code and a printable condition table.  Independent briefs are counted
  by DISTINCT author, so cloned authors cannot inflate the count.
* TST-0264 (``validate_spec`` / ``decide_stop``): the per-round *stop-eval row*
  used by ``tools.council.simulate.run_council``.  Floors are a hard
  precondition on a TRUE stopping expression; they are never a stop rule of
  their own, and ``min_rounds=0`` is rejected at validation time as a bypass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------
# IMP-0309 layer: condition ids and decision reasons
# --------------------------------------------------------------------------
CONDITION_ROUNDS = "min_rounds"
CONDITION_BRIEFS = "independent_briefs"
CONDITION_OBJECTIONS = "objections_considered"
FLOOR_BLOCK = "FLOOR_BLOCK"
STOP_ALLOWED = "STOP_ALLOWED"
GATE_DISABLED_STOP = "GATE_DISABLED_STOP"
CEILING_ESCALATE = "CEILING_ESCALATE"

# --------------------------------------------------------------------------
# TST-0264 layer: floor ids, stop-eval reasons, bypass codes
# --------------------------------------------------------------------------
FLOOR_MIN_ROUNDS = "min_rounds"
FLOOR_INDEPENDENT_OPENING_POSITIONS = "independent_opening_positions"
FLOOR_MIN_EVIDENCE = "min_evidence"
FLOOR_MANDATED_ROLES_SPOKEN = "mandated_roles_spoken"
FLOOR_ORDER: tuple[str, ...] = (
    FLOOR_MIN_ROUNDS,
    FLOOR_INDEPENDENT_OPENING_POSITIONS,
    FLOOR_MIN_EVIDENCE,
    FLOOR_MANDATED_ROLES_SPOKEN,
)

REASON_FLOOR_BLOCKS = "floor-blocks-satisfied-stop"
REASON_GATE_DISABLED = "gate-disabled-expression-true"
REASON_EXPRESSION_FALSE = "expression-false"
REASON_STOP = "expression-true-floors-met"
REASON_CEILING = "max-rounds-ceiling"

DECISION_STOP = "stop"
DECISION_CONTINUE = "continue"

# spec key that carries each floor's requirement
FLOOR_SPEC_KEYS: dict[str, str] = {
    FLOOR_MIN_ROUNDS: "min_rounds",
    FLOOR_INDEPENDENT_OPENING_POSITIONS: "min_independent_briefs",
    FLOOR_MIN_EVIDENCE: "min_evidence",
    FLOOR_MANDATED_ROLES_SPOKEN: "mandated_roles",
}
# a floor set to 0 (or below) is a bypass, not a lenient floor
HARD_MINIMUMS: dict[str, int] = {
    FLOOR_MIN_ROUNDS: 1,
    FLOOR_INDEPENDENT_OPENING_POSITIONS: 1,
    FLOOR_MIN_EVIDENCE: 0,
}
BYPASS_CODES: dict[str, str] = {
    FLOOR_MIN_ROUNDS: "floor-bypass-min_rounds",
    FLOOR_INDEPENDENT_OPENING_POSITIONS: "floor-bypass-min_independent_briefs",
    FLOOR_MIN_EVIDENCE: "floor-bypass-min_evidence",
    FLOOR_MANDATED_ROLES_SPOKEN: "floor-bypass-mandated_roles",
}
CODE_NO_ROUNDS = "no-rounds"
CODE_CEILING_BELOW_FLOOR = "ceiling-below-floor"
CODE_NO_ROLES = "no-roles"
CODE_UNKNOWN_MANDATED_ROLE = "mandated-role-unknown"
CODE_BAD_EXPRESSION = "bad-stopping-expression"
CODE_BAD_TYPE = "bad-type"


class FloorValidationError(ValueError):
    """IMP-0309 spec rejection: ``path`` names the offending key."""

    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


class SpecValidationError(ValueError):
    """TST-0264 spec rejection with a stable ``code`` and human ``message``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


def _distinct(values: Iterable[Any]) -> list[str]:
    seen: list[str] = []
    for v in values or []:
        key = str(v).strip()
        if key and key not in seen:
            seen.append(key)
    return seen


def _int_field(obj: dict[str, Any], key: str, path: str, *, default: int | None = None) -> int:
    raw = obj.get(key, default)
    if raw is None:
        raise FloorValidationError(path, "missing")
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise FloorValidationError(path, f"not an integer: {raw!r}")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise FloorValidationError(path, f"not an integer: {raw!r}") from None
    if float(raw) != float(val):
        raise FloorValidationError(path, f"not an integer: {raw!r}")
    return val


@dataclass(frozen=True)
class FloorSpec:
    """Validated IMP-0309 floors."""

    min_rounds: int
    min_independent_briefs: int
    min_objections_considered: int
    max_rounds: int
    gate_enabled: bool = True

    @classmethod
    def from_obj(cls, obj: dict[str, Any]) -> "FloorSpec":
        if not isinstance(obj, dict):
            raise FloorValidationError("spec", "spec must be an object")
        min_rounds = _int_field(obj, "min_rounds", "spec.min_rounds")
        if min_rounds < 1:
            raise FloorValidationError(
                "spec.min_rounds", f"min_rounds={min_rounds} bypasses the floor; hard minimum is 1"
            )
        briefs = _int_field(obj, "min_independent_briefs", "spec.min_independent_briefs")
        if briefs < 1:
            raise FloorValidationError(
                "spec.min_independent_briefs",
                f"min_independent_briefs={briefs} bypasses the floor; hard minimum is 1",
            )
        objections = _int_field(
            obj, "min_objections_considered", "spec.min_objections_considered", default=0
        )
        if objections < 0:
            raise FloorValidationError(
                "spec.min_objections_considered", "min_objections_considered must be >= 0"
            )
        max_rounds = _int_field(obj, "max_rounds", "spec.max_rounds", default=min_rounds)
        if max_rounds < 1:
            raise FloorValidationError("spec.max_rounds", "max_rounds must be >= 1")
        if max_rounds < min_rounds:
            raise FloorValidationError(
                "spec.max_rounds",
                f"max_rounds={max_rounds} is below min_rounds={min_rounds}; the ceiling would "
                "fire before the floor can be met",
            )
        gate = obj.get("gate_enabled", True)
        if not isinstance(gate, bool):
            raise FloorValidationError("spec.gate_enabled", "gate_enabled must be a boolean")
        return cls(
            min_rounds=min_rounds,
            min_independent_briefs=briefs,
            min_objections_considered=objections,
            max_rounds=max_rounds,
            gate_enabled=gate,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "min_rounds": self.min_rounds,
            "min_independent_briefs": self.min_independent_briefs,
            "min_objections_considered": self.min_objections_considered,
            "max_rounds": self.max_rounds,
            "gate_enabled": self.gate_enabled,
        }


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
            "condition_table": [row.as_dict() for row in self.condition_table],
        }


@dataclass
class Trace:
    decisions: list[Decision] = field(default_factory=list)
    stopped: bool = False


def observed_independent_briefs(state: dict[str, Any]) -> int:
    """Distinct brief authors; a declared count is only used when no author list exists."""
    authors = state.get("independent_brief_authors")
    if isinstance(authors, (list, tuple, set)):
        return len(_distinct(authors))
    declared = state.get("independent_briefs")
    return max(0, int(declared or 0))


def observed_objections(state: dict[str, Any]) -> int:
    ids = state.get("objection_ids_considered")
    if isinstance(ids, (list, tuple, set)):
        return len(_distinct(ids))
    declared = state.get("objections_considered")
    return max(0, int(declared or 0))


def evaluate(spec: dict[str, Any], state: dict[str, Any]) -> Decision:
    """Decide whether the council MAY stop at this instant (IMP-0309)."""
    rounds_req = int(spec.get("min_rounds") or 0)
    briefs_req = int(spec.get("min_independent_briefs") or 0)
    obj_req = int(spec.get("min_objections_considered") or 0)
    max_rounds = int(spec.get("max_rounds") or 0)
    gate_enabled = bool(spec.get("gate_enabled", True))

    rounds_obs = int(state.get("rounds_completed") or 0)
    briefs_obs = observed_independent_briefs(state)
    obj_obs = observed_objections(state)
    stop_expr = bool(state.get("stop_expression_true", state.get("consensus", False)))

    rows = [
        ConditionRow(CONDITION_ROUNDS, rounds_req, rounds_obs, rounds_obs >= rounds_req),
        ConditionRow(CONDITION_BRIEFS, briefs_req, briefs_obs, briefs_obs >= briefs_req),
        ConditionRow(CONDITION_OBJECTIONS, obj_req, obj_obs, obj_obs >= obj_req),
    ]
    unmet = tuple(row.id for row in rows if not row.met)
    ceiling_reached = bool(max_rounds) and rounds_obs >= max_rounds

    if not gate_enabled:
        # Negative control: with the gate off the expression alone decides.
        return Decision(
            may_stop=stop_expr,
            reason=GATE_DISABLED_STOP if stop_expr else FLOOR_BLOCK,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=stop_expr,
            ceiling_reached=ceiling_reached,
        )
    if ceiling_reached and unmet:
        # The ceiling never converts unmet floors into a stop; it escalates.
        return Decision(
            may_stop=False,
            reason=CEILING_ESCALATE,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=stop_expr,
            ceiling_reached=True,
        )
    if not stop_expr:
        return Decision(
            may_stop=False,
            reason=FLOOR_BLOCK,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=False,
            ceiling_reached=ceiling_reached,
        )
    if unmet:
        return Decision(
            may_stop=False,
            reason=FLOOR_BLOCK,
            unmet=unmet,
            condition_table=rows,
            stop_expression_true=True,
            ceiling_reached=ceiling_reached,
        )
    return Decision(
        may_stop=True,
        reason=STOP_ALLOWED,
        unmet=(),
        condition_table=rows,
        stop_expression_true=True,
        ceiling_reached=ceiling_reached,
    )


def format_condition_table(decision: Decision) -> str:
    widths = (24, 10, 10, 5)
    header = ("condition", "required", "observed", "met")
    lines = ["  ".join(h.ljust(w) for h, w in zip(header, widths))]
    for row in decision.condition_table:
        cells = (row.id, str(row.required), str(row.observed), "yes" if row.met else "NO")
        lines.append("  ".join(c.ljust(w) for c, w in zip(cells, widths)))
    lines.append(
        f"stop_expression_true={decision.stop_expression_true} "
        f"may_stop={decision.may_stop} reason={decision.reason} "
        f"unmet={list(decision.unmet)}"
    )
    return "\n".join(lines)


def run_rounds(spec: dict[str, Any], states: list[dict[str, Any]]) -> Trace:
    """Evaluate each candidate-stop instant in order; stop at the first allowed one."""
    trace = Trace()
    for state in states:
        decision = evaluate(spec, state)
        trace.decisions.append(decision)
        if decision.may_stop:
            trace.stopped = True
            break
    return trace


# --------------------------------------------------------------------------
# TST-0264 layer
# --------------------------------------------------------------------------
def _require_int(spec: dict[str, Any], key: str, *, default: int | None = None) -> int:
    raw = spec.get(key, default)
    if raw is None:
        raise SpecValidationError(CODE_BAD_TYPE, f"spec.{key} is required")
    if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
        raise SpecValidationError(CODE_BAD_TYPE, f"spec.{key} must be an integer, got {raw!r}")
    try:
        val = int(raw)
    except (TypeError, ValueError):
        raise SpecValidationError(CODE_BAD_TYPE, f"spec.{key} must be an integer, got {raw!r}") from None
    if float(raw) != float(val):
        raise SpecValidationError(CODE_BAD_TYPE, f"spec.{key} must be an integer, got {raw!r}")
    return val


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Reject floor bypasses before any round runs; return the normalised floors."""
    if not isinstance(spec, dict):
        raise SpecValidationError(CODE_BAD_TYPE, "spec must be an object")
    roles = [str(r) for r in (spec.get("roles") or []) if str(r).strip()]
    if not roles:
        raise SpecValidationError(CODE_NO_ROLES, "spec.roles must name at least one role")
    mandated = [str(r) for r in (spec.get("mandated_roles") or roles)]
    unknown = [r for r in mandated if r not in roles]
    if unknown:
        raise SpecValidationError(
            CODE_UNKNOWN_MANDATED_ROLE, f"mandated roles not in spec.roles: {unknown}"
        )
    min_rounds = _require_int(spec, "min_rounds")
    if min_rounds < HARD_MINIMUMS[FLOOR_MIN_ROUNDS]:
        raise SpecValidationError(
            BYPASS_CODES[FLOOR_MIN_ROUNDS],
            f"min_rounds={min_rounds} is a floor bypass; hard minimum is "
            f"{HARD_MINIMUMS[FLOOR_MIN_ROUNDS]}",
        )
    min_briefs = _require_int(spec, "min_independent_briefs")
    if min_briefs < HARD_MINIMUMS[FLOOR_INDEPENDENT_OPENING_POSITIONS]:
        raise SpecValidationError(
            BYPASS_CODES[FLOOR_INDEPENDENT_OPENING_POSITIONS],
            f"min_independent_briefs={min_briefs} is a floor bypass; hard minimum is "
            f"{HARD_MINIMUMS[FLOOR_INDEPENDENT_OPENING_POSITIONS]}",
        )
    min_evidence = _require_int(spec, "min_evidence", default=0)
    if min_evidence < HARD_MINIMUMS[FLOOR_MIN_EVIDENCE]:
        raise SpecValidationError(
            BYPASS_CODES[FLOOR_MIN_EVIDENCE],
            f"min_evidence={min_evidence} is below the hard minimum "
            f"{HARD_MINIMUMS[FLOOR_MIN_EVIDENCE]}",
        )
    max_rounds = _require_int(spec, "max_rounds", default=max(min_rounds, 1))
    if max_rounds < 1:
        raise SpecValidationError(CODE_NO_ROUNDS, "spec.max_rounds must allow at least one round")
    if max_rounds < min_rounds:
        raise SpecValidationError(
            CODE_CEILING_BELOW_FLOOR,
            f"max_rounds={max_rounds} is below min_rounds={min_rounds}",
        )
    expression = spec.get("stopping_expression")
    if not isinstance(expression, str) or not expression.strip():
        raise SpecValidationError(CODE_BAD_EXPRESSION, "spec.stopping_expression must be a non-empty string")
    from . import expr as _expr

    try:
        _expr.parse(expression)
    except Exception as exc:  # the expr module raises its own typed error
        raise SpecValidationError(CODE_BAD_EXPRESSION, f"stopping_expression does not parse: {exc}") from exc
    return {
        "id": spec.get("id"),
        "roles": roles,
        "mandated_roles": mandated,
        "stopping_expression": expression,
        "min_rounds": min_rounds,
        "min_independent_briefs": min_briefs,
        "min_evidence": min_evidence,
        "max_rounds": max_rounds,
    }


def measure_floors(
    floors: dict[str, Any], measured: dict[str, Any]
) -> tuple[dict[str, Any], list[str], dict[str, str]]:
    """Compare measured deliberation against the floors; return (required, unmet, detail)."""
    rounds = int(measured.get("rounds_completed") or 0)
    briefs = int(measured.get("independent_briefs") or 0)
    evidence = int(measured.get("evidence") or 0)
    spoken = _distinct(measured.get("mandated_roles_spoken") or [])
    mandated = [str(r) for r in floors.get("mandated_roles") or []]
    silent = [r for r in mandated if r not in spoken]
    required = {
        FLOOR_MIN_ROUNDS: int(floors["min_rounds"]),
        FLOOR_INDEPENDENT_OPENING_POSITIONS: int(floors["min_independent_briefs"]),
        FLOOR_MIN_EVIDENCE: int(floors.get("min_evidence") or 0),
        FLOOR_MANDATED_ROLES_SPOKEN: list(mandated),
    }
    detail: dict[str, str] = {}
    unmet: list[str] = []
    if rounds < required[FLOOR_MIN_ROUNDS]:
        unmet.append(FLOOR_MIN_ROUNDS)
        detail[FLOOR_MIN_ROUNDS] = f"rounds completed: {rounds} < min {required[FLOOR_MIN_ROUNDS]}"
    if briefs < required[FLOOR_INDEPENDENT_OPENING_POSITIONS]:
        unmet.append(FLOOR_INDEPENDENT_OPENING_POSITIONS)
        detail[FLOOR_INDEPENDENT_OPENING_POSITIONS] = (
            f"independent opening positions submitted: {briefs} < min "
            f"{required[FLOOR_INDEPENDENT_OPENING_POSITIONS]}"
        )
    if evidence < required[FLOOR_MIN_EVIDENCE]:
        unmet.append(FLOOR_MIN_EVIDENCE)
        detail[FLOOR_MIN_EVIDENCE] = f"evidence items cited: {evidence} < min {required[FLOOR_MIN_EVIDENCE]}"
    if silent:
        unmet.append(FLOOR_MANDATED_ROLES_SPOKEN)
        detail[FLOOR_MANDATED_ROLES_SPOKEN] = f"mandated roles still silent: {','.join(silent) or '(none)'}"
    ordered = [f for f in FLOOR_ORDER if f in unmet]
    return required, ordered, detail


def decide_stop(
    floors: dict[str, Any],
    measured: dict[str, Any],
    *,
    round_no: int,
    stop_expression_true: bool,
    apply_floors: bool = True,
    ceiling_reached: bool = False,
) -> dict[str, Any]:
    """One stop-eval row: the floor gate applied AFTER the stopping expression."""
    required, unmet, detail = measure_floors(floors, measured)
    floors_met = not unmet
    named = unmet[0] if unmet else None
    message = ""
    expr_true = bool(stop_expression_true)
    if not apply_floors:
        decision = DECISION_STOP if expr_true else DECISION_CONTINUE
        reason = REASON_GATE_DISABLED if expr_true else REASON_EXPRESSION_FALSE
    elif not expr_true:
        decision, reason = DECISION_CONTINUE, REASON_EXPRESSION_FALSE
    elif unmet:
        decision, reason = DECISION_CONTINUE, REASON_FLOOR_BLOCKS
        message = f"FLOOR BLOCKS STOP: {named} ({detail[named]})"
    else:
        decision, reason = DECISION_STOP, REASON_STOP
    if decision == DECISION_CONTINUE and ceiling_reached:
        # The ceiling ends the run without pretending the stop rule was satisfied.
        decision, reason = DECISION_STOP, REASON_CEILING
    return {
        "round": int(round_no),
        "stop_expression": floors.get("stopping_expression"),
        "stop_expression_true": expr_true,
        "apply_floors": bool(apply_floors),
        "measured": {
            "rounds_completed": int(measured.get("rounds_completed") or 0),
            "independent_briefs": int(measured.get("independent_briefs") or 0),
            "evidence": int(measured.get("evidence") or 0),
            "mandated_roles_spoken": _distinct(measured.get("mandated_roles_spoken") or []),
        },
        "required": required,
        "floors_met": floors_met,
        "unmet_floors": unmet,
        "floor_detail": detail,
        "named_floor": named,
        "floor_block_message": message,
        "ceiling_reached": bool(ceiling_reached),
        "decision": decision,
        "reason": reason,
    }


__all__ = [
    "BYPASS_CODES",
    "CEILING_ESCALATE",
    "CODE_BAD_EXPRESSION",
    "CODE_BAD_TYPE",
    "CODE_CEILING_BELOW_FLOOR",
    "CODE_NO_ROLES",
    "CODE_NO_ROUNDS",
    "CODE_UNKNOWN_MANDATED_ROLE",
    "CONDITION_BRIEFS",
    "CONDITION_OBJECTIONS",
    "CONDITION_ROUNDS",
    "ConditionRow",
    "DECISION_CONTINUE",
    "DECISION_STOP",
    "Decision",
    "FLOOR_BLOCK",
    "FLOOR_INDEPENDENT_OPENING_POSITIONS",
    "FLOOR_MANDATED_ROLES_SPOKEN",
    "FLOOR_MIN_EVIDENCE",
    "FLOOR_MIN_ROUNDS",
    "FLOOR_ORDER",
    "FLOOR_SPEC_KEYS",
    "FloorSpec",
    "FloorValidationError",
    "GATE_DISABLED_STOP",
    "HARD_MINIMUMS",
    "REASON_CEILING",
    "REASON_EXPRESSION_FALSE",
    "REASON_FLOOR_BLOCKS",
    "REASON_GATE_DISABLED",
    "REASON_STOP",
    "STOP_ALLOWED",
    "SpecValidationError",
    "Trace",
    "decide_stop",
    "evaluate",
    "format_condition_table",
    "measure_floors",
    "observed_independent_briefs",
    "observed_objections",
    "run_rounds",
    "validate_spec",
]
