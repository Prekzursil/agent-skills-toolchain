#!/usr/bin/env python3
"""CNL-0080 evaluator: unanimity == true OR max_rounds == 12.

Bindings (anti-tautology):
  unanimity  -> computed from seated ballots this round (never copied from stop)
  max_rounds -> clock.round_index of the round just completed
                NEVER stopping.configured_max_rounds (that would be a tautology
                whenever the configured ceiling is 12)

Cadence: end-of-round only. Both disjuncts are evaluated (no short-circuit) so
a timer-and-agreement coincidence is visible as BOTH, not as whichever branch
was visited first.

Outcome record: TIMER_EXHAUSTION is a different outcome_kind than AGREEMENT.
Downstream consumers must key off (outcome_kind, unanimity, stop_reason), not
off `stopped`.
"""
from __future__ import annotations

from typing import Any

from a10_grammar import (
    CNL_0080_EXPR,
    parse_unchanged,
    static_reject_tautology,
)

ABSTAIN = "ABSTAIN"
LEGAL_BINDINGS = {
    "unanimity": "computed.unanimity_from_ballots",
    "max_rounds": "clock.round_index",
}
ILLEGAL_BIND_MAX_ROUNDS_TO_CONFIG = "stopping.configured_max_rounds"

CONTINUE = "CONTINUE"
AGREEMENT = "AGREEMENT"
TIMER_EXHAUSTION = "TIMER_EXHAUSTION"
AGREEMENT_AT_CEILING = "AGREEMENT_AT_CEILING"
AGREEMENT_HELD_FOR_REVALUATION = "AGREEMENT_HELD_FOR_REVALUATION"


def unanimity_from_ballots(seats: list[str], ballots: dict[str, Any]) -> bool:
    if not seats:
        return False
    if set(seats) != set(ballots.keys()):
        return False
    values = [ballots[s] for s in seats]
    if any(v is None or v == ABSTAIN for v in values):
        return False
    return len(set(values)) == 1


def instant_unanimity_trigger(ctx: dict) -> bool:
    """CNL-0059: suspiciously fast unanimity. Silent on timer exhaustion."""
    return (
        unanimity_from_ballots(ctx["seats"], ctx["ballots"])
        and int(ctx["round_index"]) == 1
        and int(ctx.get("independent_briefs") or 0) == 0
    )


def bind_legal(ctx: dict) -> dict[str, Any]:
    return {
        "unanimity": unanimity_from_ballots(ctx["seats"], ctx["ballots"]),
        "max_rounds": int(ctx["round_index"]),
    }


def bind_tautology(ctx: dict) -> dict[str, Any]:
    """Illegal: bind max_rounds to the configured ceiling (always 12 here)."""
    return {
        "unanimity": unanimity_from_ballots(ctx["seats"], ctx["ballots"]),
        "max_rounds": int(ctx["configured_max_rounds"]),
    }


def _cmp(op: str, left: Any, right: Any) -> bool:
    if op == "==":
        return left == right
    if op == "!=":
        return left != right
    if op == ">=":
        return left >= right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == "<":
        return left < right
    raise ValueError(op)


def eval_ast(ast: dict, metrics: dict[str, Any], trace: dict | None = None) -> bool:
    """Full evaluation: OR/AND visit every child. Unknown metric -> NOT-CHECKED (not False)."""
    op = ast["op"]
    if op == "CMP":
        name = ast["left"]
        if name not in metrics:
            if trace is not None:
                trace.setdefault("not_checked", []).append(name)
            raise ValueError(f"unbound metric {name}")
        val = _cmp(ast["cmp"], metrics[name], ast["right"])
        if trace is not None:
            trace.setdefault("cmp", []).append(
                {
                    "left": name,
                    "observed": metrics[name],
                    "cmp": ast["cmp"],
                    "right": ast["right"],
                    "value": val,
                }
            )
        return val
    if op == "OR":
        vals = [eval_ast(a, metrics, trace) for a in ast["args"]]
        return any(vals)
    if op == "AND":
        vals = [eval_ast(a, metrics, trace) for a in ast["args"]]
        return all(vals)
    if op == "NOT":
        return not eval_ast(ast["arg"], metrics, trace)
    if op == "ANY":
        return any(eval_ast(a, metrics, trace) for a in ast["args"])
    if op == "ALL":
        return all(eval_ast(a, metrics, trace) for a in ast["args"])
    raise ValueError(op)


def branch_fired(metrics: dict[str, Any]) -> list[str]:
    fired = []
    if metrics["unanimity"] is True:
        fired.append("unanimity == true")
    if metrics["max_rounds"] == 12:
        fired.append("max_rounds == 12")
    return fired


def outcome_record(ctx: dict, metrics: dict[str, Any], expression_true: bool, trace: dict) -> dict:
    u = bool(metrics["unanimity"])
    t = metrics["max_rounds"] == 12
    suspicion = instant_unanimity_trigger(ctx)
    if not expression_true:
        kind = CONTINUE
        reason = None
        stopped = False
    elif u and t:
        kind = AGREEMENT_AT_CEILING
        reason = "BOTH"
        stopped = True
    elif u and suspicion:
        kind = AGREEMENT_HELD_FOR_REVALUATION
        reason = "UNANIMITY"
        stopped = True
    elif u:
        kind = AGREEMENT
        reason = "UNANIMITY"
        stopped = True
    elif t:
        kind = TIMER_EXHAUSTION
        reason = "MAX_ROUNDS"
        stopped = True
    else:
        kind = CONTINUE
        reason = None
        stopped = False
    return {
        "expression": CNL_0080_EXPR,
        "stopped": stopped,
        "expression_true": expression_true,
        "stop_reason": reason,
        "outcome_kind": kind,
        "unanimity": u,
        "round_index": metrics["max_rounds"],
        "configured_max_rounds": int(ctx["configured_max_rounds"]),
        "branch_fired": branch_fired(metrics),
        "instant_unanimity_trigger": suspicion,
        "evaluation_cadence": "end-of-round",
        "side_effect_free": True,
        "short_circuit": False,
        "bindings": dict(LEGAL_BINDINGS),
        "trace": trace,
        "distinguishable_from_unanimity": kind != AGREEMENT,
        "consumer_key": [kind, u, reason],
    }


def evaluate_fixture(ctx: dict, *, bind=bind_legal) -> dict:
    parsed = parse_unchanged(CNL_0080_EXPR)
    if bind is bind_tautology:
        constants = {"max_rounds": int(ctx["configured_max_rounds"])}
        why = static_reject_tautology(parsed.ast, constants)
        if why:
            return {
                "rejected": True,
                "reject_reason": why,
                "binding_mode": ILLEGAL_BIND_MAX_ROUNDS_TO_CONFIG,
            }
    metrics = bind(ctx)
    trace: dict = {"cmp": [], "not_checked": []}
    true = eval_ast(parsed.ast, metrics, trace)
    rec = outcome_record(ctx, metrics, true, trace)
    rec["rejected"] = False
    rec["parse_accepted"] = parsed.accepted
    rec["source_verbatim"] = parsed.source_verbatim
    rec["fixture_id"] = ctx.get("id")
    rec["computed_unanimity"] = metrics["unanimity"]
    return rec


def naive_consumer_treats_stop_as_unanimity(record: dict) -> dict:
    """The overclaim this unit exists to prevent: stopped => agreed."""
    return {
        "unanimity": bool(record.get("stopped")),
        "outcome_kind": "AGREEMENT" if record.get("stopped") else CONTINUE,
        "stop_reason": "UNANIMITY" if record.get("stopped") else None,
    }


def overclaim_detector(record: dict, naive: dict) -> dict:
    """FIRE when a consumer reports unanimity that the ballots did not produce."""
    fired = bool(naive.get("unanimity")) and record.get("unanimity") is False
    return {
        "id": "NC-STOPPED-IS-NOT-UNANIMITY",
        "fired": fired,
        "silent": not fired,
        "meant_to_reject": (
            "a downstream consumer that copies stopped==true onto unanimity==true "
            "when the timer, not agreement, ended the council"
        ),
        "actual_unanimity": record.get("unanimity"),
        "naive_unanimity": naive.get("unanimity"),
        "actual_outcome_kind": record.get("outcome_kind"),
        "naive_outcome_kind": naive.get("outcome_kind"),
    }
