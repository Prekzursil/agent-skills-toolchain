"""Evaluate consensus >= 0.95 AND no_new_objection_rounds >= 2.

Cadence (scoped, CNL-0076 not on disk): one snapshot at end-of-round, after
that round's objections are admitted. The expression is pure.

consensus := support_weight / (support_weight + oppose_weight)
  Silent seats are excluded from both numerator and denominator (they do not
  inflate). Reasoned oppose lowers the score. Distinguishable from silence.

no_new_objection_rounds := consecutive end-of-round ticks with no ADMITTED
  objection that is SAME as none of the previously admitted set.
  Restatement (same slots+observation, any wording, any participant including
  a newly recruited seat) does NOT reset.
  A genuinely new objection, including from a newly recruited participant,
  resets the counter to 0.
"""

from __future__ import annotations

from typing import Any, Callable

from a10 import eval_expr
from expr import SPEC_EXPRESSION
from identity import admissible, same_objection, same_objection_lexical_only, slot_key


def consensus_of(ballots: list[dict[str, Any]]) -> dict[str, Any]:
    support = 0.0
    oppose = 0.0
    silent = 0
    for b in ballots:
        w = float(b.get("weight") or 1.0)
        vote = str(b.get("vote") or "silent").lower()
        if vote in {"support", "aye", "yes"}:
            support += w
        elif vote in {"oppose", "nay", "no"}:
            oppose += w
        else:
            silent += 1
    denom = support + oppose
    value = (support / denom) if denom > 0 else 0.0
    return {
        "consensus": value,
        "support_weight": support,
        "oppose_weight": oppose,
        "silent_seats": silent,
        "cast_weight": denom,
    }


def step_objections(
    seen: list[dict[str, Any]],
    incoming: list[dict[str, Any]],
    same_fn: Callable[[dict[str, Any], dict[str, Any]], bool],
) -> dict[str, Any]:
    inadmissible = [o for o in incoming if not admissible(o)]
    admitted = [o for o in incoming if admissible(o)]
    new_objs: list[dict[str, Any]] = []
    restated: list[dict[str, Any]] = []
    for obj in admitted:
        if any(same_fn(obj, prev) for prev in seen):
            restated.append(obj)
        else:
            new_objs.append(obj)
    return {
        "admitted": admitted,
        "inadmissible": inadmissible,
        "new": new_objs,
        "restated": restated,
        "new_count": len(new_objs),
        "new_slot_keys": [slot_key(o) for o in new_objs],
    }


def run_council(
    fixture: dict[str, Any],
    *,
    same_fn: Callable[[dict[str, Any], dict[str, Any]], bool] | None = None,
) -> dict[str, Any]:
    if same_fn is None:
        same_fn = same_objection
    seen: list[dict[str, Any]] = []
    quiet = 0
    rounds_out: list[dict[str, Any]] = []
    stop = False
    env_last: dict[str, Any] = {}
    for rnd in fixture["rounds"]:
        c = consensus_of(list(rnd.get("ballots") or []))
        step = step_objections(seen, list(rnd.get("objections") or []), same_fn)
        if step["new_count"] > 0:
            quiet = 0
            seen.extend(step["new"])
        else:
            quiet += 1
        env = {
            "consensus": c["consensus"],
            "no_new_objection_rounds": quiet,
        }
        fired = eval_expr(SPEC_EXPRESSION, env)
        stop = bool(fired)
        env_last = env
        rounds_out.append(
            {
                "round": rnd["round"],
                "newly_recruited": list(rnd.get("newly_recruited") or []),
                "consensus": c["consensus"],
                "support_weight": c["support_weight"],
                "oppose_weight": c["oppose_weight"],
                "silent_seats": c["silent_seats"],
                "no_new_objection_rounds": quiet,
                "new_count": step["new_count"],
                "restated_count": len(step["restated"]),
                "inadmissible_count": len(step["inadmissible"]),
                "new_slot_keys": [list(k) for k in step["new_slot_keys"]],
                "stop": stop,
            }
        )
    return {
        "fixture_id": fixture.get("id"),
        "expect_stop": fixture.get("expect_stop"),
        "stop": stop,
        "final": env_last,
        "rounds": rounds_out,
        "identity": same_fn.__name__,
    }


def lexical_mutant_run(fixture: dict[str, Any]) -> dict[str, Any]:
    return run_council(fixture, same_fn=same_objection_lexical_only)


run_council = run_council
lexical_mutant_run = lexical_mutant_run
run_council = run_council
lexical_mutant_run = lexical_mutant_run
run_council = run_council
lexical_mutant_run = lexical_mutant_run
