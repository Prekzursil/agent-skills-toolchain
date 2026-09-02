"""Bleed test: two concurrent sessions in one project must not share goals."""
from __future__ import annotations

import tempfile
import threading
from pathlib import Path
from typing import Any

from session_store import SessionKeyedStore

PROJECT = "proj-ast-integrate"
SESS_A = "sess-A"
SESS_B = "sess-B"
GOAL_A = "GOAL-A-do-not-bleed"
GOAL_B = "GOAL-B-sibling"
STORES = ("goal_inject", "ledger_replay", "claims", "caches")


def _run_pair(mode: str, store_name: str = "goal_inject") -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix=f"imp0430-{mode}-"))
    store = SessionKeyedStore(tmp, mode=mode)  # type: ignore[arg-type]
    barrier = threading.Barrier(2)
    results: dict[str, Any] = {}
    errors: list[str] = []

    def worker(sid: str, payload: Any) -> None:
        try:
            store.put(store_name, PROJECT, sid, payload)
            barrier.wait(timeout=5)
            results[sid] = store.get(store_name, PROJECT, sid)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{sid}:{type(exc).__name__}:{exc}")

    t1 = threading.Thread(target=worker, args=(SESS_A, {"goal": GOAL_A, "store": store_name}))
    t2 = threading.Thread(target=worker, args=(SESS_B, {"goal": GOAL_B, "store": store_name}))
    t1.start()
    t2.start()
    t1.join(timeout=8)
    t2.join(timeout=8)
    a = (results.get(SESS_A) or {}).get("goal")
    b = (results.get(SESS_B) or {}).get("goal")
    isolated = a == GOAL_A and b == GOAL_B
    bled = (a == GOAL_B) or (b == GOAL_A) or (a == b and a is not None)
    return {
        "mode": mode,
        "store": store_name,
        "root": str(tmp),
        "read_a": a,
        "read_b": b,
        "isolated": isolated,
        "bled": bled,
        "errors": errors,
        "threads_alive": t1.is_alive() or t2.is_alive(),
    }


def bleed_both_states() -> dict[str, Any]:
    per_store = {}
    all_ok = True
    for name in STORES:
        good = _run_pair("session", name)
        bad = _run_pair("project", name)
        ok = bool(
            good["isolated"]
            and not good["bled"]
            and bad["bled"]
            and not bad["isolated"]
            and not good["errors"]
            and not bad["errors"]
            and not good["threads_alive"]
            and not bad["threads_alive"]
        )
        per_store[name] = {"session_keyed": good, "project_keyed_mutant": bad, "ok": ok}
        all_ok = all_ok and ok
    goal = per_store["goal_inject"]
    return {
        "per_store": per_store,
        "session_keyed": goal["session_keyed"],
        "project_keyed_mutant": goal["project_keyed_mutant"],
        "pass": all_ok,
    }
