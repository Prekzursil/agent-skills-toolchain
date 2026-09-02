"""In-process session co-execution for two blueprints.

A session has one shared filesystem, one control-plane registry, and one
event stream. Two workflows run in that session. Collisions are observed,
not asserted from the declared map.
"""
from __future__ import annotations

from typing import Any

# Discriminating event stream: one shared session clock. Stop rules that
# actually conflict disagree on STOP vs CONTINUE against this stream.
SESSION_EVENTS: dict[str, Any] = {
    "round": 1,
    "error": True,
    "successes": 1,
    "total": 2,
    "dispatched": True,
    "children_done": 1,
    "children_total": 2,
    "replay_exhausted": True,
    "diversity_met": False,
    "consensus": False,
}


def evaluate_stop(stop_id: str, ev: dict[str, Any] | None = None) -> str:
    """Return STOP or CONTINUE for a stop rule on the shared session events."""
    e = SESSION_EVENTS if ev is None else ev
    if stop_id == "halt-on-error":
        return "STOP" if e["error"] else "CONTINUE"
    if stop_id == "continue-on-error":
        return "CONTINUE"
    if stop_id == "first-success":
        return "STOP" if e["successes"] >= 1 else "CONTINUE"
    if stop_id == "all-must-pass":
        if e["error"] or e["successes"] < e["total"]:
            return "CONTINUE"
        return "STOP"
    if stop_id == "fire-and-forget":
        return "STOP" if e["dispatched"] else "CONTINUE"
    if stop_id == "blocking-fan-in":
        return "STOP" if e["children_done"] >= e["children_total"] else "CONTINUE"
    if stop_id == "deterministic-replay":
        return "STOP" if e["replay_exhausted"] else "CONTINUE"
    if stop_id == "non-deterministic-sampling":
        return "STOP" if e["diversity_met"] else "CONTINUE"
    if stop_id == "independent-first-pass":
        return "STOP" if e["round"] >= 1 else "CONTINUE"
    if stop_id == "shared-context-deliberation":
        return "STOP" if e["consensus"] else "CONTINUE"
    if stop_id == "max-rounds-1":
        return "STOP" if e["round"] >= 1 else "CONTINUE"
    if stop_id == "min-rounds-3":
        return "STOP" if e["round"] >= 3 else "CONTINUE"
    raise KeyError(f"unknown stop rule {stop_id!r}")


def _run(wf: dict[str, Any], files: dict[str, str], writers: dict[str, list[str]], planes: dict[str, list[str]]) -> None:
    wid = wf["id"]
    for path in wf.get("writes") or []:
        files[path] = f"{wid}:{path}"
        writers.setdefault(path, []).append(wid)
    plane = wf.get("plane")
    if plane:
        planes.setdefault(plane, []).append(wid)


def co_execute(left: dict[str, Any], right: dict[str, Any], order: str = "ab") -> dict[str, Any]:
    """Run two workflows in one session. order is 'ab' or 'ba'."""
    files: dict[str, str] = {}
    writers: dict[str, list[str]] = {}
    planes: dict[str, list[str]] = {}
    first, second = (left, right) if order == "ab" else (right, left)
    _run(first, files, writers, planes)
    _run(second, files, writers, planes)
    shared_files = sorted(p for p, w in writers.items() if len(set(w)) >= 2)
    shared_planes = sorted(p for p, w in planes.items() if len(set(w)) >= 2)
    sa = evaluate_stop(left["stop"])
    sb = evaluate_stop(right["stop"])
    stop_disagree = sa != sb
    return {
        "order": order,
        "left": left["id"],
        "right": right["id"],
        "files_written": sorted(files),
        "writers": {p: list(w) for p, w in writers.items()},
        "planes": {p: list(w) for p, w in planes.items()},
        "shared_files": shared_files,
        "shared_planes": shared_planes,
        "stop_left": {"id": left["stop"], "decision": sa},
        "stop_right": {"id": right["stop"], "decision": sb},
        "stop_disagree": stop_disagree,
    }


def co_execute_both_orders(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    ab = co_execute(left, right, "ab")
    ba = co_execute(left, right, "ba")
    return {
        "ab": ab,
        "ba": ba,
        "shared_files": sorted(set(ab["shared_files"]) | set(ba["shared_files"])),
        "shared_planes": sorted(set(ab["shared_planes"]) | set(ba["shared_planes"])),
        "stop_disagree": ab["stop_disagree"] and ba["stop_disagree"],
        "stop_left": ab["stop_left"],
        "stop_right": ab["stop_right"],
    }


def static_intersect(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Independent of Session.co_execute: set intersection of declared resources."""
    files = sorted(set(left.get("writes") or []) & set(right.get("writes") or []))
    pa, pb = left.get("plane"), right.get("plane")
    planes = [pa] if pa and pa == pb else []
    sa = evaluate_stop(left["stop"])
    sb = evaluate_stop(right["stop"])
    return {
        "shared_files": files,
        "shared_planes": planes,
        "stop_disagree": sa != sb,
        "stop_left": {"id": left["stop"], "decision": sa},
        "stop_right": {"id": right["stop"], "decision": sb},
    }
