"""Concurrent-session bleed experiment on keyed stores (IMP-0430)."""
from __future__ import annotations

import sys
import threading
from pathlib import Path

GOAL_A = "GOAL-A-do-not-bleed"
GOAL_B = "GOAL-B-sibling"


def run_bleed(store_cls, project_id: str = "proj-shared") -> dict:
    """Two concurrent sessions in one project: each writes then reads its goal."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from fixtures import build_stores, fresh_store_root

    stores = build_stores(fresh_store_root(), store_cls)
    barrier = threading.Barrier(2)
    observed = {}

    def worker(sid, goal):
        for name, store in stores.items():
            store.write(project_id, sid, {"goal": goal, "store": name})
        barrier.wait(timeout=10)
        read = stores["goal_inject"].read(project_id, sid)
        observed[sid] = str(read.get("goal", ""))

    ta = threading.Thread(target=worker, args=("session-A", GOAL_A))
    tb = threading.Thread(target=worker, args=("session-B", GOAL_B))
    ta.start(); tb.start(); ta.join(); tb.join()

    isolated = observed["session-A"] == GOAL_A and observed["session-B"] == GOAL_B
    return {"isolated": isolated, "bled": not isolated,
            "read_a": observed["session-A"], "read_b": observed["session-B"]}
