"""Compile a CouncilSpec into a typed execution plan (IMP-0262)."""
from __future__ import annotations

import hashlib
import json
from typing import Any


class CompileError(Exception):
    pass


def compile_spec(spec: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, dict):
        raise CompileError("spec is not an object")
    seats = list(spec.get("participants") or [])
    named_participants = sorted(str(s["id"]) for s in seats)
    engagement = spec.get("engagement") or {}
    n_rounds = int((engagement.get("min_turns") or 1))
    rounds = []
    named_rounds: list[str] = []
    named_turns: list[str] = []
    named_gates: list[str] = []
    for r in range(n_rounds):
        rid = f"round-{r:02d}"
        named_rounds.append(rid)
        turns = []
        gates = []
        for s in sorted(seats, key=lambda x: str(x["id"])):
            tid = f"{rid}:{s['id']}"
            named_turns.append(tid)
            turns.append({"turn_id": tid, "participant_id": s["id"], "round_id": rid})
        gid = f"{rid}:gate"
        named_gates.append(gid)
        gates.append({"gate_id": gid, "kind": "round-complete", "round_id": rid})
        rounds.append({"round_id": rid, "turns": turns, "gates": gates})
    final_gid = "final:halt"
    named_gates.append(final_gid)
    plan = {
        "named_participants": named_participants,
        "named_rounds": named_rounds,
        "named_turns": named_turns,
        "named_gates": named_gates,
        "rounds": rounds,
        "final_gates": [{"gate_id": final_gid, "kind": "halt"}],
        "model_calls_scheduled": 0,
        "compiled_before_model_call": True,
        "charter": spec.get("charter") or {},
    }
    return plan


def _canon(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canon(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_canon(x) for x in obj]
    return obj


def dumps_plan(plan: dict[str, Any]) -> str:
    return json.dumps(_canon(plan), sort_keys=True, separators=(",", ":"))


def digest_plan(plan: dict[str, Any]) -> str:
    return hashlib.sha256(dumps_plan(plan).encode("utf-8")).hexdigest()


def execute_plan(plan: dict[str, Any]) -> dict[str, Any]:
    turns = list(plan.get("named_turns") or [])
    gates = list(plan.get("named_gates") or [])
    return {
        "turns": turns,
        "gates": gates,
        "model_calls": 0,
        "executed_turns": turns,
        "executed_gates": gates,
    }


def plan_vs_trace(plan: dict[str, Any], trace: dict[str, Any]) -> dict[str, Any]:
    want_t = list(plan.get("named_turns") or [])
    got_t = list(trace.get("executed_turns") or trace.get("turns") or [])
    want_g = list(plan.get("named_gates") or [])
    got_g = list(trace.get("executed_gates") or trace.get("gates") or [])
    return {
        "turns_equal": want_t == got_t,
        "gates_equal": want_g == got_g,
        "model_calls": int(trace.get("model_calls") or 0),
        "missing_turns": [t for t in want_t if t not in got_t],
        "extra_turns": [t for t in got_t if t not in want_t],
        "missing_gates": [g for g in want_g if g not in got_g],
        "extra_gates": [g for g in got_g if g not in want_g],
    }
