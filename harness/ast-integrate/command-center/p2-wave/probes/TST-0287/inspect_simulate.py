#!/usr/bin/env python3
"""Inspect tools/council/simulate.py for a stated-probability channel.

The file exists (replacement-scoped kernel). Ballots carry vote choice only.
Calibration scoring therefore cannot use that transcript as a forecast table.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[4]


def inspect_simulator(*, seed: int = 287) -> dict[str, Any]:
    path = REPO / "tools" / "council" / "simulate.py"
    present = path.is_file()
    out: dict[str, Any] = {
        "path": "tools/council/simulate.py",
        "present": present,
        "bytes": path.stat().st_size if present else 0,
        "imported": False,
        "ran": False,
        "status": None,
        "n_ballots": 0,
        "ballot_keys": [],
        "has_stated_p": False,
        "has_confidence": False,
        "usable_as_forecast_table": False,
        "error": None,
    }
    if not present:
        return out
    tools = str(REPO / "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    try:
        from council.simulate import dump_result, initial_state, run_until_complete
    except Exception as exc:  # pragma: no cover - environment
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    out["imported"] = True
    try:
        state = initial_state(seed=seed)
        state = run_until_complete(state)
        dumped = dump_result(state)
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {exc}"
        return out
    out["ran"] = True
    out["status"] = dumped.get("status") or state.get("status")
    ballots = list(state.get("ballots") or [])
    out["n_ballots"] = len(ballots)
    keys: list[str] = []
    for b in ballots:
        for k in b:
            if k not in keys:
                keys.append(k)
    out["ballot_keys"] = keys
    out["has_stated_p"] = any("stated_p" in b or "p" in b for b in ballots)
    out["has_confidence"] = any("confidence" in b for b in ballots)
    out["usable_as_forecast_table"] = bool(
        ballots and out["has_stated_p"] and out["status"] == "complete"
    )
    return out
