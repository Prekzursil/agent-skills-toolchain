"""Translate foreign.linear-dag.v1 onto ast-integrate.control-plane.v1.

The translator is a mapping, not a proof. Proof is execute-then-diff.
"""
from __future__ import annotations

from exec_trace import index_nodes


NATIVE_PLANE = "ast-integrate.control-plane.v1"
FOREIGN_FORMAT = "foreign.linear-dag.v1"


def translate(foreign: dict) -> dict:
    if foreign.get("format") != FOREIGN_FORMAT:
        raise ValueError(f"unsupported format {foreign.get('format')!r}")
    nodes = index_nodes(foreign)
    tasks: list[str] = []
    gates: list[dict] = []
    halt_reasons: list[str] = []
    for node in foreign["nodes"]:
        kind = node["kind"]
        if kind == "task":
            tasks.append(node["id"])
        elif kind == "if":
            pred = node["predicate"]
            target = node["on_true"]
            if target not in nodes or nodes[target]["kind"] != "task":
                raise ValueError(f"if {node['id']!r} on_true is not a task")
            fail = node["on_false"]
            if fail not in nodes or nodes[fail]["kind"] != "stop":
                raise ValueError(f"if {node['id']!r} on_false is not a stop")
            gates.append(
                {
                    "id": f"{target}.{pred['field']}",
                    "stage": target,
                    "field": pred["field"],
                    "op": pred["op"],
                    "value": pred["value"],
                    "on_fail": "stop",
                    "from_foreign_node": node["id"],
                }
            )
        elif kind == "stop":
            halt_reasons.append(node.get("reason") or "gate_fail")
        else:
            raise ValueError(f"unknown kind {kind!r}")
    if not tasks:
        raise ValueError("no tasks to translate")
    start = foreign["start"]
    if start not in tasks:
        raise ValueError("start is not a task")
    # Preserve foreign task encounter order (list order of task nodes).
    stages = [{"id": tid, "order": i} for i, tid in enumerate(tasks)]
    return {
        "id": f"native:{foreign.get('id') or 'unnamed'}",
        "plane": NATIVE_PLANE,
        "source_format": FOREIGN_FORMAT,
        "source_id": foreign.get("id"),
        "route": "TRANSLATE",
        "stages": stages,
        "gates": gates,
        "stop": {
            "on": "ANY",
            "rules": [
                {
                    "when": "gate_fail",
                    "gate_id": g["id"],
                    "stage": g["stage"],
                    "field": g["field"],
                }
                for g in gates
            ]
            + [{"when": "stages_exhausted"}],
        },
    }
