"""A1-shaped sketches of separable orchestration mechanisms.

The chosen control plane (A1, config-first) stores capabilities as static JSON
under command-center/control-plane/A1/. These sketches are the same shape:
finite stage lists, declarative retry/HITL/fan-out, sidecar checkpoint files.
They do not import LangGraph, CrewAI, AutoGen, Temporal, Airflow, Prefect, or
Dagster.
"""
from __future__ import annotations

from typing import Any

StageFailed = type("StageFailed", (RuntimeError,), {})
BarrierBroken = type("BarrierBroken", (RuntimeError,), {})
NonSeparable = type("NonSeparable", (RuntimeError,), {})

FOREIGN_RUNTIMES = (
    "langgraph",
    "crewai",
    "autogen",
    "autogen_agentchat",
    "autogen_core",
    "temporalio",
    "airflow",
    "prefect",
    "dagster",
)


def execute(workflow: dict[str, Any], store: dict[str, Any] | None = None) -> dict[str, Any]:
    """Run or resume a static JSON workflow. Checkpoint is the store itself."""
    if store is None:
        store = {"cursor": 0, "payload": {}, "status": "running"}
    stages = workflow["stages"]
    cursor = int(store.get("cursor") or 0)
    payload: dict[str, Any] = dict(store.get("payload") or {})
    while cursor < len(stages):
        stage = stages[cursor]
        kind = stage["kind"]
        sid = stage["id"]
        if kind == "compute":
            payload[sid] = stage.get("emit", True)
        elif kind == "retry":
            fail_until = int(stage.get("fail_until") or 0)
            max_attempts = int(stage.get("max_attempts") or 1)
            attempts = 0
            while True:
                attempts += 1
                if attempts <= fail_until:
                    if attempts >= max_attempts:
                        store.update(cursor=cursor, payload=payload, status="failed")
                        raise StageFailed(f"{sid} exhausted {max_attempts} attempts")
                    continue
                payload[sid] = {"attempts": attempts, "result": "ok"}
                break
        elif kind == "hitl":
            if "human" not in store:
                store.update(cursor=cursor, payload=payload, status="awaiting_human")
                return store
            payload[sid] = store["human"]
        elif kind == "fan_out":
            payload[sid] = list(stage.get("items") or [])
        elif kind == "join":
            src = payload.get(stage["from"])
            expect = int(stage.get("expect") or 0)
            if not isinstance(src, list) or len(src) != expect:
                raise BarrierBroken(f"{sid} expected {expect} got {src!r}")
            payload[sid] = src
        elif kind == "foreign_worker_poll":
            raise NonSeparable(
                "Worker poll loops, schedulers, and daemons are the foreign "
                "control plane; A1 will not sketch them."
            )
        else:
            raise ValueError(f"unknown stage kind {kind}")
        cursor += 1
        store.update(cursor=cursor, payload=payload, status="running")
    store.update(cursor=cursor, payload=payload, status="done")
    return store


SEPARABLE_DEMO = {
    "id": "wf.wfa0027.separable-demo",
    "control_plane": "A1",
    "stages": [
        {"id": "fan", "kind": "fan_out", "items": ["a", "b", "c"]},
        {"id": "join", "kind": "join", "from": "fan", "expect": 3},
        {"id": "flaky", "kind": "retry", "fail_until": 2, "max_attempts": 3},
        {"id": "approve", "kind": "hitl"},
        {"id": "finish", "kind": "compute", "emit": "closed"},
    ],
}

NON_SEPARABLE_DEMO = {
    "id": "wf.wfa0027.temporal-worker-poll",
    "control_plane": "A1",
    "stages": [
        {
            "id": "poll_task_queue",
            "kind": "foreign_worker_poll",
            "runtime": "temporalio.worker.Worker",
        }
    ],
}
