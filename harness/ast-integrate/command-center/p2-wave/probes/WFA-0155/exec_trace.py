"""Foreign linear-DAG and native control-plane interpreters.

Both emit the same canonical execution trace: stages entered, gate
(stage, field, op, value, verdict, observed), and stop reason.
Fidelity is this trace, not a structural walk of the AST.
"""
from __future__ import annotations

from typing import Any

OPS = {
    "gte": lambda a, b: a >= b,
    "gt": lambda a, b: a > b,
    "lte": lambda a, b: a <= b,
    "lt": lambda a, b: a < b,
    "eq": lambda a, b: a == b,
    "neq": lambda a, b: a != b,
}


def eval_pred(pred: dict, case: dict) -> tuple[bool, Any]:
    field = pred["field"]
    op = pred["op"]
    if op not in OPS:
        raise ValueError(f"unknown op {op!r}")
    if field not in case:
        raise ValueError(f"case missing field {field!r}")
    observed = case[field]
    return bool(OPS[op](observed, pred["value"])), observed


def index_nodes(foreign: dict) -> dict[str, dict]:
    nodes = {n["id"]: n for n in foreign["nodes"]}
    if len(nodes) != len(foreign["nodes"]):
        raise ValueError("duplicate foreign node id")
    return nodes


def execute_foreign(foreign: dict, case: dict) -> dict:
    """Walk the foreign DAG. if-nodes become gates on their on_true stage."""
    nodes = index_nodes(foreign)
    start = foreign["start"]
    if start not in nodes:
        raise ValueError(f"missing start {start!r}")
    stages: list[str] = []
    gates: list[dict] = []
    cur = start
    seen: set[str] = set()
    while cur:
        if cur in seen:
            raise ValueError(f"cycle at {cur!r}")
        seen.add(cur)
        node = nodes[cur]
        kind = node["kind"]
        if kind == "task":
            stages.append(node["id"])
            nxt = node.get("next")
            cur = nxt if nxt else None
            continue
        if kind == "if":
            pred = node["predicate"]
            ok, observed = eval_pred(pred, case)
            target = node["on_true"]
            gates.append(
                {
                    "stage": target,
                    "field": pred["field"],
                    "op": pred["op"],
                    "value": pred["value"],
                    "verdict": ok,
                    "observed": observed,
                    "source_node": node["id"],
                }
            )
            cur = target if ok else node["on_false"]
            continue
        if kind == "stop":
            return canonical(
                stages,
                gates,
                {
                    "reason": node.get("reason") or "gate_fail",
                    "halted_before_stage": gates[-1]["stage"] if gates else None,
                },
            )
        raise ValueError(f"unknown foreign kind {kind!r}")
    return canonical(stages, gates, {"reason": "exhausted", "halted_before_stage": None})


def execute_native(native: dict, case: dict) -> dict:
    """Walk ordered native stages; entry gates may halt before a stage."""
    stages_spec = sorted(native["stages"], key=lambda s: int(s["order"]))
    by_stage: dict[str, list[dict]] = {}
    for g in native["gates"]:
        by_stage.setdefault(g["stage"], []).append(g)
    stages: list[str] = []
    gates: list[dict] = []
    for spec in stages_spec:
        sid = spec["id"]
        for g in by_stage.get(sid, []):
            pred = {"field": g["field"], "op": g["op"], "value": g["value"]}
            ok, observed = eval_pred(pred, case)
            gates.append(
                {
                    "stage": sid,
                    "field": g["field"],
                    "op": g["op"],
                    "value": g["value"],
                    "verdict": ok,
                    "observed": observed,
                    "source_node": g.get("from_foreign_node"),
                }
            )
            if not ok:
                return canonical(
                    stages,
                    gates,
                    {"reason": "gate_fail", "halted_before_stage": sid},
                )
        stages.append(sid)
    return canonical(stages, gates, {"reason": "exhausted", "halted_before_stage": None})


def canonical(stages: list[str], gates: list[dict], stop: dict) -> dict:
    return {
        "stages_entered": list(stages),
        "gates": [
            {
                "stage": g["stage"],
                "field": g["field"],
                "op": g["op"],
                "value": g["value"],
                "verdict": bool(g["verdict"]),
                "observed": g["observed"],
            }
            for g in gates
        ],
        "stop": {
            "reason": stop["reason"],
            "halted_before_stage": stop["halted_before_stage"],
        },
    }


# Unique snippet for file:line evidence (must appear once).
CANONICAL_TRACE_FIELDS = ("stages_entered", "gates", "stop")
