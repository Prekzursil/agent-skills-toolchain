#!/usr/bin/env python3
"""Shared IMP-0144 scenario: record a fixture run, replay it, mutate a field."""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def _load_replay():
    path = REPO / "tools" / "agentspec" / "agentspec" / "replay_log.py"
    spec = importlib.util.spec_from_file_location("imp0144_replay_log", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


_R = _load_replay()
FrozenClock = _R.FrozenClock
CountingFakeRail = _R.CountingFakeRail
drop_payload_field = _R.drop_payload_field
fixture_execute = _R.fixture_execute
mutate_producer_items = _R.mutate_producer_items
record_run = _R.record_run
reconstruct_unverified = _R.reconstruct_unverified
replay_run = _R.replay_run
sha256_bytes = _R.sha256_bytes
try_replay = _R.try_replay

UNIT = "IMP-0144"
RECEIPT_REL = "command-center/receipts/IMP-0144.json"
FIXTURE_LOG_REL = "command-center/p2-wave/probes/IMP-0144/fixtures/recorded-run.jsonl"


def digest_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def record_and_replay() -> dict[str, Any]:
    """Catalog test 1 + evidence: byte-equal plan/verdicts, zero replay spawns."""
    record_rail = CountingFakeRail(fixture_execute)
    recorded = record_run(rail=record_rail, clock=FrozenClock(origin=0))
    replay_rail = CountingFakeRail(fixture_execute)
    replayed = replay_run(recorded.log_bytes, rail=replay_rail)
    kinds = [e["kind"] for e in recorded.events]
    fail_verdicts = [v for v in recorded.verdicts if v["verdict"] == "FAIL"]
    return {
        "dispatch_events": kinds.count("dispatch.recorded"),
        "event_count": len(recorded.events),
        "fail_verdicts": len(fail_verdicts),
        "kinds": kinds,
        "plan_bytes": len(recorded.plan_b),
        "plan_equal": replayed.plan_b == recorded.plan_b,
        "plan_sha256": sha256_bytes(recorded.plan_b),
        "record_spawns": recorded.spawns,
        "replay_calls": list(replay_rail.calls),
        "replay_spawns": replay_rail.spawns,
        "run_id": recorded.run_id,
        "slot_count": len(recorded.plan["slots"]),
        "slot_ids": [s["unit_id"] for s in recorded.plan["slots"]],
        "verdict_equal": replayed.verdicts_b == recorded.verdicts_b,
        "verdict_sha256": sha256_bytes(recorded.verdicts_b),
        "verdicts": list(recorded.verdicts),
        "log_bytes": recorded.log_bytes,
        "recorded": recorded,
        "pass": (
            replayed.plan_b == recorded.plan_b
            and replayed.verdicts_b == recorded.verdicts_b
            and replay_rail.spawns == 0
            and recorded.spawns > 0
            and len(fail_verdicts) == 1
        ),
    }


def field_mutation() -> dict[str, Any]:
    """Catalog test 2: drop a load-bearing field; byte-equality goes red.

    Control: drop debug_note (declared non-load-bearing); plan stays equal.
    """
    recorded = record_run(clock=FrozenClock(origin=0))
    original = recorded.plan_b
    # Load-bearing: drop params from run.start (required for reconstruction).
    dropped_params = drop_payload_field(recorded.log_bytes, "run.start", "params")
    params_err = None
    params_equal: bool | None = None
    try:
        replay_run(dropped_params, rail=CountingFakeRail(fixture_execute))
        params_equal = True  # replay produced a plan; compare below via reconstruct
    except Exception as exc:  # noqa: BLE001 — mutation must go red, any closed failure counts
        params_err = f"{type(exc).__name__}: {exc}"
        params_equal = False

    # Load-bearing value: drop fan-out item "beta" and refresh value_hash so the
    # envelope still parses; unconstrained reconstruct must yield a different plan.
    dropped_item = mutate_producer_items(
        recorded.log_bytes, drop_index=1, refresh_hash=True
    )
    item_strict, item_strict_err = try_replay(
        dropped_item, rail=CountingFakeRail(fixture_execute)
    )
    item_unverified = reconstruct_unverified(dropped_item)
    item_plan_equal = item_unverified.plan_b == original
    item_slots = [s["unit_id"] for s in item_unverified.plan["slots"]]

    # Non-load-bearing control: dropping debug_note must NOT change the plan.
    dropped_note = drop_payload_field(recorded.log_bytes, "run.start", "debug_note")
    note_replay, note_err = try_replay(
        dropped_note, rail=CountingFakeRail(fixture_execute)
    )
    note_equal = note_replay is not None and note_replay.plan_b == original

    # Intact log still matches (both-states: good state silent / equal).
    intact, intact_err = try_replay(
        recorded.log_bytes, rail=CountingFakeRail(fixture_execute)
    )
    intact_equal = intact is not None and intact.plan_b == original

    load_bearing_red = params_equal is False and item_plan_equal is False
    return {
        "intact_equal": intact_equal,
        "intact_err": intact_err,
        "item_plan_equal": item_plan_equal,
        "item_slots": item_slots,
        "item_slot_count": len(item_slots),
        "item_strict_err": item_strict_err,
        "item_strict_ok": item_strict is not None,
        "note_equal": note_equal,
        "note_err": note_err,
        "original_slot_count": len(recorded.plan["slots"]),
        "original_slots": [s["unit_id"] for s in recorded.plan["slots"]],
        "params_equal": params_equal,
        "params_err": params_err,
        "pass": load_bearing_red and note_equal and intact_equal,
    }


def write_fixture_log(log_bytes: bytes) -> Path:
    dest = REPO / FIXTURE_LOG_REL
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(log_bytes)
    return dest
