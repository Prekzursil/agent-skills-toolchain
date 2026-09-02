"""Run a suite with egress blocked or allowed; compute undeclared-network delta."""
from __future__ import annotations

import tempfile
import traceback
from pathlib import Path
from typing import Any

import wrap
from suite import Case


def _dests(guard: wrap.EgressGuard, start: int) -> list[dict[str, Any]]:
    return [
        {"host": a["host"], "port": int(a["port"]), "via": a["via"]}
        for a in guard.attempts[start:]
    ]


def run_cases(cases: list[Case], *, block: bool, cache: Path) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []
    with wrap.install(block=block) as guard:
        start = 0
        for case in cases:
            rec: dict[str, Any] = {
                "id": case.id,
                "network": case.network,
                "role": case.role,
                "ok": False,
                "error": None,
            }
            try:
                rec["result"] = case.fn(cache)
                rec["ok"] = True
            except Exception as exc:  # noqa: BLE001 — measurement, record every failure
                rec["error"] = f"{type(exc).__name__}: {exc}"
                rec["traceback_tail"] = traceback.format_exc()[-400:]
            rec["attempted_destinations"] = _dests(guard, start)
            start = len(guard.attempts)
            steps.append(rec)
        all_attempts = _dests(guard, 0)
    return {
        "mode": "blocked" if block else "allowed",
        "completed": True,
        "steps": steps,
        "attempted_destinations": all_attempts,
    }


def step(run: dict[str, Any], name: str) -> dict[str, Any]:
    for item in run["steps"]:
        if item["id"] == name:
            return item
    raise KeyError(name)


def undeclared_delta(cases: list[Case], blocked: dict, allowed: dict) -> list[dict[str, Any]]:
    """Tests whose pass/fail changes and that do not declare network."""
    by_id = {c.id: c for c in cases}
    out: list[dict[str, Any]] = []
    blocked_map = {s["id"]: s for s in blocked["steps"]}
    allowed_map = {s["id"]: s for s in allowed["steps"]}
    for cid, case in by_id.items():
        b, a = blocked_map[cid], allowed_map[cid]
        if bool(b["ok"]) == bool(a["ok"]):
            continue
        if case.network:
            continue
        out.append(
            {
                "id": cid,
                "blocked_ok": bool(b["ok"]),
                "allowed_ok": bool(a["ok"]),
                "network_declared": False,
                "blocked_error": b.get("error"),
                "blocked_destinations": b.get("attempted_destinations") or [],
            }
        )
    return out


def identical_for_undeclared(cases: list[Case], blocked: dict, allowed: dict) -> bool:
    blocked_map = {s["id"]: s for s in blocked["steps"]}
    allowed_map = {s["id"]: s for s in allowed["steps"]}
    for case in cases:
        if case.network:
            continue
        if bool(blocked_map[case.id]["ok"]) != bool(allowed_map[case.id]["ok"]):
            return False
    return True


def with_cache() -> tempfile.TemporaryDirectory[str]:
    return tempfile.TemporaryDirectory(prefix="tst0133-")
