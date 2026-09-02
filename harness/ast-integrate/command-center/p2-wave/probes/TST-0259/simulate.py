"""Deterministic scripted-persona council for planted TST-0259 casts.

tools/council/simulate.py is absent on this worktree (TST-0257 owns that
entry point). This module is the local planted-cast runner: it emits a
round-1 transcript from a cast fixture with no model calls and no wall clock.
Two runs of the same cast are byte-identical.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from casts import (
    collapsed_cast,
    differentiated_cast,
    relabeled_collapsed_cast,
    sweep_casts,
)


def canonical_bytes(obj: Any) -> bytes:
    return (
        json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"
    ).encode("utf-8")


def run_cast(cast: dict[str, Any]) -> dict[str, Any]:
    """Emit a one-round transcript. Personas are state machines over the fixture."""
    participants = []
    for raw in cast["participants"]:
        p = deepcopy(raw)
        participants.append(
            {
                "seat_id": p["seat_id"],
                "role": p["role"],
                "opening": p["opening"],
                "claims": list(p["claims"]),
                "evidence": list(p["evidence"]),
                "vote": int(p["vote"]),
            }
        )
    return {
        "cast_id": cast["cast_id"],
        "kind": cast.get("kind"),
        "similarity": cast.get("similarity"),
        "round": 1,
        "harness": "command-center/p2-wave/probes/TST-0259/simulate.py",
        "production_simulate_py": "tools/council/simulate.py",
        "production_present": False,
        "participants": participants,
    }


def run_named(name: str) -> dict[str, Any]:
    if name == "collapsed":
        return run_cast(collapsed_cast())
    if name == "differentiated":
        return run_cast(differentiated_cast())
    if name == "relabeled":
        return run_cast(relabeled_collapsed_cast())
    raise KeyError(name)


def run_sweep() -> list[dict[str, Any]]:
    return [run_cast(c) for c in sweep_casts()]
