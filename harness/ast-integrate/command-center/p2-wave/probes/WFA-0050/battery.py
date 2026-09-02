"""20-state termination battery: grammar vs documented control-flow."""
from __future__ import annotations

from documented import documented_stop
from fixtures import SYNTHETIC_STATES
from stopping import (
    AUTOGEN_GROUPCHAT_STOP,
    PLANTED_AND_MUTATION,
    bind_state,
    evaluate,
    grammar_stop,
)


def row_for(state: dict) -> dict:
    g = grammar_stop(state)
    d = documented_stop(state)
    return {
        "id": state["id"],
        "kind": state["kind"],
        "grammar_stop": g,
        "documented_stop": d,
        "agree": g == d,
    }


def run_battery() -> dict:
    rows = [row_for(s) for s in SYNTHETIC_STATES]
    disagree = [r["id"] for r in rows if not r["agree"]]
    stops = [r["id"] for r in rows if r["documented_stop"]]
    cont = [r["id"] for r in rows if not r["documented_stop"]]
    planted = []
    for state in SYNTHETIC_STATES:
        if state["kind"] != "autogen-groupchat":
            continue
        env = bind_state(state)
        planted_stop = evaluate(PLANTED_AND_MUTATION, env)
        doc = documented_stop(state)
        planted.append(
            {
                "id": state["id"],
                "planted_and_stop": planted_stop,
                "documented_stop": doc,
                "disagree": planted_stop != doc,
            }
        )
    planted_hits = [p["id"] for p in planted if p["disagree"]]
    return {
        "n": len(rows),
        "rows": rows,
        "disagree": disagree,
        "stop_ids": stops,
        "continue_ids": cont,
        "expressions": {
            "crew": "tasks_completed >= task_count",
            "autogen": AUTOGEN_GROUPCHAT_STOP,
            "planted_and": PLANTED_AND_MUTATION,
        },
        "planted_and_hits": planted_hits,
        "planted_and_rows": planted,
    }
