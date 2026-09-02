"""Estate control-plane IR walker.

Not LangGraph. Sequential stages, named gates, file-backed thread checkpoints.
This is the chosen estate control plane for evidence B: execute the IR.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from graph_data import END, START, route_key


def _merge(policy: str, left, right):
    if policy == "overwrite":
        return right
    if policy == "concat":
        a = list(left or [])
        b = list(right or [])
        return a + b
    raise ValueError(f"unmapped merge policy {policy}")


def _policies(ir: dict) -> dict[str, str]:
    return {c["key"]: c["merge"] for c in ir["state_channels"]}


def _apply(ir: dict, state: dict, writes: dict) -> dict:
    pol = _policies(ir)
    out = dict(state)
    for k, v in writes.items():
        if k not in pol:
            continue
        out[k] = _merge(pol[k], out.get(k), v)
    return out


def _stage(ir: dict, sid: str) -> dict:
    for s in ir["stages"]:
        if s["id"] == sid:
            return s
    raise KeyError(sid)


def _successors(ir: dict, stage_id: str, state: dict) -> list[str]:
    nxt: list[str] = []
    for e in ir["edges"]:
        if e["from"] == stage_id:
            nxt.append(e["to"])
    for g in ir["gates"]:
        if g["after_stage"] == stage_id:
            key = route_key(state, g["predicate_id"])
            nxt.append(g["path_map"][key])
    return nxt


def _interrupt_before(ir: dict) -> set[str]:
    return {
        h["before_stage"]
        for h in ir["human_checkpoints"]
        if h.get("kind") == "interrupt_before"
    }


def save_checkpoint(store: Path, checkpoint: dict) -> Path:
    store.mkdir(parents=True, exist_ok=True)
    path = store / f"{checkpoint['thread_id']}.json"
    path.write_text(json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8")
    return path


def load_checkpoint(store: Path, thread_id: str) -> dict | None:
    path = store / f"{thread_id}.json"
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def run(
    ir: dict,
    *,
    inputs: dict,
    thread_id: str,
    store: Path,
    resume: bool = False,
) -> dict:
    before = _interrupt_before(ir)
    if resume:
        checkpoint = load_checkpoint(store, thread_id)
        if checkpoint is None:
            raise ValueError(f"no checkpoint for thread {thread_id}")
        state = deepcopy(checkpoint["state"])
        pending = list(checkpoint["pending"])
        order: list[str] = []
        skip_interrupt = set(checkpoint.get("pending") or [])
    else:
        state = deepcopy(inputs)
        pending = _successors(ir, START, state)
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
        if node_id in before and node_id not in skip_interrupt:
            ck = {
                "thread_id": thread_id,
                "state": deepcopy(state),
                "pending": [node_id] + pending,
                "stage_order": list(order),
            }
            save_checkpoint(store, ck)
            return {
                "status": "interrupted",
                "stage_order": order,
                "state": state,
                "checkpoint": ck,
                "interrupt_before": node_id,
                "thread_id": thread_id,
            }
        skip_interrupt.discard(node_id)
        stage = _stage(ir, node_id)
        state = _apply(ir, state, stage.get("writes") or {})
        order.append(node_id)
        pending.extend(_successors(ir, node_id, state))

    return {
        "status": "completed",
        "stage_order": order,
        "state": state,
        "checkpoint": None,
        "thread_id": thread_id,
    }
