"""Independent documented-order oracle.

Walks the SOURCE graph using published Pregel / reducer / interrupt_before
rules. Does not read IR. This is evidence B's independent side.
"""
from __future__ import annotations

from copy import deepcopy

from graph_data import END, START, load_graph, node_by_id, route_key


def _merge(reducer: str, left, right):
    if reducer == "last_value":
        return right
    if reducer == "operator.add":
        a = list(left or [])
        b = list(right or [])
        return a + b
    if reducer == "custom:unique_append":
        seen = list(left or [])
        for x in right or []:
            if x not in seen:
                seen.append(x)
        return seen
    raise ValueError(reducer)


def _reducers(graph: dict) -> dict[str, str]:
    return {c["key"]: c["reducer"] for c in graph["state_schema"]}


def _apply(graph: dict, state: dict, writes: dict) -> dict:
    red = _reducers(graph)
    out = dict(state)
    for k, v in writes.items():
        out[k] = _merge(red[k], out.get(k), v)
    return out


def _successors(graph: dict, node_id: str, state: dict) -> list[str]:
    nxt: list[str] = []
    for e in graph["edges"]:
        if e["from"] == node_id:
            nxt.append(e["to"])
    for ce in graph["conditional_edges"]:
        if ce["source"] == node_id:
            key = route_key(state, ce["path"])
            nxt.append(ce["path_map"][key])
    return nxt


def run(
    graph: dict | None = None,
    *,
    inputs: dict,
    thread_id: str,
    checkpoint: dict | None = None,
    resume: bool = False,
) -> dict:
    """One invoke. If resume, continue from checkpoint of the same thread_id."""
    graph = graph or load_graph()
    interrupt_before = list(graph["compile"].get("interrupt_before") or [])

    if resume:
        if checkpoint is None or checkpoint.get("thread_id") != thread_id:
            raise ValueError("resume requires checkpoint for this thread_id")
        state = deepcopy(checkpoint["state"])
        pending = list(checkpoint["pending"])
        order: list[str] = []
        skip_interrupt = set(checkpoint.get("pending") or [])
    else:
        state = deepcopy(inputs)
        pending = _successors(graph, START, state)
        order = []
        skip_interrupt = set()

    while pending:
        node_id = pending.pop(0)
        if node_id == END:
            return {
                "status": "completed",
                "stage_order": order,
                "state": state,
                "checkpoint": None,
                "thread_id": thread_id,
            }
        if node_id in interrupt_before and node_id not in skip_interrupt:
            ck = {
                "thread_id": thread_id,
                "state": deepcopy(state),
                "pending": [node_id] + pending,
                "stage_order": list(order),
            }
            return {
                "status": "interrupted",
                "stage_order": order,
                "state": state,
                "checkpoint": ck,
                "interrupt_before": node_id,
                "thread_id": thread_id,
            }
        skip_interrupt.discard(node_id)
        node = node_by_id(graph, node_id)
        state = _apply(graph, state, node.get("writes") or {})
        order.append(node_id)
        pending.extend(_successors(graph, node_id, state))

    return {
        "status": "completed",
        "stage_order": order,
        "state": state,
        "checkpoint": None,
        "thread_id": thread_id,
    }
