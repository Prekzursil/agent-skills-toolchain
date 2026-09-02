#!/usr/bin/env python3
"""IMP-0264 probe 1: turn order, timeout, obligations, event-count invariant."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))

from council.kernel import (  # noqa: E402
    ExecutionPlan,
    Kernel,
    KernelError,
    ScriptedAdapter,
    TurnResponse,
    kernel_loop_records_turns,
)
from council.topology.round_robin import RoundRobinTopology  # noqa: E402


def adapters_ok(*ids: str) -> dict:
    return {
        pid: ScriptedAdapter(
            TurnResponse(text=f"ok:{pid}", fields={"position": f"POS-{pid}"}, elapsed_ms=5)
        )
        for pid in ids
    }


def run_full() -> dict:
    roster = ("alice", "bob", "cara")
    kernel = Kernel("council-full")
    plan = ExecutionPlan(
        council_id="council-full",
        roster=roster,
        n_rounds=2,
        timeout_ms=100,
        max_chars=64,
        obligations=("position",),
    )
    result = kernel.run(plan, RoundRobinTopology(), adapters_ok(*roster))
    expected_order = roster * 2
    return {
        "id": "full-council-invariant",
        "turns_executed": result.turns_executed,
        "turns_recorded": result.turns_recorded,
        "invariant_ok": result.invariant_ok,
        "turn_order": list(result.turn_order),
        "expected_order": list(expected_order),
        "order_ok": result.turn_order == expected_order,
        "all_ok": all(s == "ok" for s in result.statuses),
        "pass": (
            result.invariant_ok
            and result.turns_executed == 6
            and result.turns_recorded == 6
            and result.turn_order == expected_order
            and all(s == "ok" for s in result.statuses)
        ),
    }


def run_timeout() -> dict:
    roster = ("alice", "bob")
    ads = adapters_ok(*roster)
    ads["bob"] = ScriptedAdapter(TurnResponse(timed_out=True, elapsed_ms=999))
    kernel = Kernel("council-timeout")
    plan = ExecutionPlan(
        council_id="council-timeout",
        roster=roster,
        n_rounds=1,
        timeout_ms=50,
        obligations=("position",),
    )
    result = kernel.run(plan, RoundRobinTopology(), ads)
    bob = [e for e in result.events if e.kind == "TURN" and e.participant_id == "bob"]
    alice = [e for e in result.events if e.kind == "TURN" and e.participant_id == "alice"]
    return {
        "id": "turn-timeout-still-recorded",
        "turns_executed": result.turns_executed,
        "turns_recorded": result.turns_recorded,
        "invariant_ok": result.invariant_ok,
        "bob_status": bob[0].status if bob else None,
        "bob_recorded": bool(bob),
        "alice_status": alice[0].status if alice else None,
        "order": list(result.turn_order),
        "pass": (
            result.invariant_ok
            and result.turns_executed == 2
            and result.turns_recorded == 2
            and bob
            and bob[0].status == "timeout"
            and alice
            and alice[0].status == "ok"
            and result.turn_order == ("alice", "bob")
        ),
    }


def run_obligation() -> dict:
    roster = ("alice", "dave")
    ads = adapters_ok(*roster)
    # Use-vs-mention: prose names the obligation but the structured field is absent.
    ads["dave"] = ScriptedAdapter(
        TurnResponse(
            text="I mention my position is ship-it but I do not fill the field",
            fields={},
            elapsed_ms=3,
        )
    )
    kernel = Kernel("council-ob")
    plan = ExecutionPlan(
        council_id="council-ob",
        roster=roster,
        n_rounds=1,
        obligations=("position",),
    )
    result = kernel.run(plan, RoundRobinTopology(), ads)
    dave = [e for e in result.events if e.kind == "TURN" and e.participant_id == "dave"]
    return {
        "id": "obligation-enforcement-structured-field",
        "turns_executed": result.turns_executed,
        "turns_recorded": result.turns_recorded,
        "invariant_ok": result.invariant_ok,
        "dave_status": dave[0].status if dave else None,
        "dave_missing": list(dave[0].obligations_missing) if dave else [],
        "mention_not_enough": bool(dave) and dave[0].status == "obligation_breach",
        "pass": (
            result.invariant_ok
            and result.turns_executed == 2
            and dave
            and dave[0].status == "obligation_breach"
            and dave[0].obligations_missing == ("position",)
        ),
    }


def run_length() -> dict:
    roster = ("eve",)
    ads = {
        "eve": ScriptedAdapter(
            TurnResponse(
                text="X" * 50,
                fields={"position": "long"},
                elapsed_ms=1,
            )
        )
    }
    kernel = Kernel("council-len")
    plan = ExecutionPlan(
        council_id="council-len",
        roster=roster,
        n_rounds=1,
        max_chars=8,
        obligations=("position",),
    )
    result = kernel.run(plan, RoundRobinTopology(), ads)
    eve = [e for e in result.events if e.kind == "TURN"][0]
    return {
        "id": "turn-length-enforced",
        "status": eve.status,
        "output_len": len(eve.output or ""),
        "truncated": eve.output == "X" * 8,
        "invariant_ok": result.invariant_ok,
        "pass": (
            result.invariant_ok
            and eve.status == "length_exceeded"
            and eve.output == "X" * 8
        ),
    }


def run_no_skip_api() -> dict:
    kernel = Kernel("closed")
    raised = None
    try:
        from council.kernel import TurnSpec

        kernel.execute_turn(
            TurnSpec("alice", ("position",), 10, 10)
        )
    except KernelError as exc:
        raised = str(exc)
    events_is_tuple = isinstance(kernel.events, tuple)
    append_failed = False
    try:
        kernel.events.append("nope")  # type: ignore[arg-type]
    except AttributeError:
        append_failed = True
    struct = kernel_loop_records_turns()
    return {
        "id": "no-bypass-advance",
        "execute_outside_round": raised == "execute-turn-outside-round",
        "events_is_tuple": events_is_tuple,
        "append_on_events_fails": append_failed,
        "turns_executed": kernel.turns_executed,
        "turns_recorded": kernel.turns_recorded,
        "structural": struct,
        "pass": (
            raised == "execute-turn-outside-round"
            and events_is_tuple
            and append_failed
            and kernel.turns_executed == 0
            and kernel.turns_recorded == 0
            and struct["run_calls_execute_turn"]
            and struct["execute_turn_calls_record"]
            and struct["execute_turn_only_returns_record"]
        ),
    }


def main() -> int:
    rows = [
        run_full(),
        run_timeout(),
        run_obligation(),
        run_length(),
        run_no_skip_api(),
    ]
    report = {
        "probe": "probe1-turn-machine",
        "unit_id": "IMP-0264",
        "all_invariants": all(r.get("invariant_ok", True) for r in rows if "invariant_ok" in r),
        "pass": all(r["pass"] for r in rows),
        "rows": rows,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["pass"]:
        print("FAILED:IMP-0264-probe1 turn machine")
        return 1
    print("SUCCESS:IMP-0264-probe1 turn ordering timeout obligation invariant")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
