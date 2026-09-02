"""Nested council fan-in: stopping expressions plus the shared completion reducer.

When the child stopping rule is satisfiable and the parent's is not (or the
reverse), the fan-in must not copy the child's complete bit onto the parent.
That copy is the council-local completion mutant this unit names.

Shared path: a level is complete only when its own stopping expression is
true AND ``lib.completion_reducer.reduce_completion`` returns COMPLETE for
that level's receipt. Parent complete additionally requires the child
complete. Mismatch therefore BLOCKs. Cycle-wait is cut by a recorded timeout.

Local mutant: parent_complete := child_complete. Mismatch is silently accepted.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "CNL-0010"))
sys.path.insert(0, str(REPO / "command-center" / "p2-wave" / "probes" / "IMP-0415"))

from fixtures import materialize  # noqa: E402
from grammar import parse  # noqa: E402
from lib.completion_reducer import reduce_completion  # noqa: E402
from staticcheck import eval_tree  # noqa: E402

SHARED_SYMBOL = "lib.completion_reducer.reduce_completion"
TIMEOUT_SECONDS = 0.20
TIMEOUT_TICKS = 80

CHILD_SATISFIABLE = "rounds >= 2"
PARENT_UNSATISFIABLE = "proof_of_impossibility == true"
PARENT_CONSISTENT = "rounds >= 2"
CHILD_WAITS_ON_PARENT = "parent_complete == true"
PARENT_WAITS_ON_CHILD = "child_complete == true"


def stopping_holds(surface: str, metrics: dict[str, Any]) -> bool:
    return bool(eval_tree(parse(surface), metrics))


def _receipt_complete(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    result = reduce_completion(record, root=root)
    verdict = str(result.get("verdict") or "")
    return {
        "verdict": verdict,
        "complete": verdict == "COMPLETE",
        "symbol": SHARED_SYMBOL,
    }


def shared_receipts() -> dict[str, Any]:
    """Evaluate the live shared reducer on a known-complete and a known-incomplete tree."""
    with TemporaryDirectory(prefix="adv0102-recv-") as tmp:
        good_root = Path(tmp) / "good"
        bad_root = Path(tmp) / "bad"
        good_rec = materialize(good_root, violate=None)
        bad_rec = materialize(bad_root, violate=2)
        good = _receipt_complete(good_root, good_rec)
        bad = _receipt_complete(bad_root, bad_rec)
    if not good["complete"]:
        raise RuntimeError(
            f"shared reducer did not return COMPLETE on the positive tree: {good}"
        )
    if bad["complete"]:
        raise RuntimeError(
            f"shared reducer returned COMPLETE on the missing-artifact tree: {bad}"
        )
    return {"complete_receipt": good, "incomplete_receipt": bad}


def _tick_shared(
    *,
    child_stop: bool,
    parent_stop: bool,
    child_receipt: bool,
    parent_receipt: bool,
    child_complete: bool,
    parent_complete: bool,
) -> tuple[bool, bool]:
    child_complete = bool(child_stop and child_receipt)
    parent_complete = bool(parent_stop and parent_receipt and child_complete)
    return child_complete, parent_complete


def _tick_local(
    *,
    child_stop: bool,
    parent_stop: bool,
    child_receipt: bool,
    parent_receipt: bool,
    child_complete: bool,
    parent_complete: bool,
) -> tuple[bool, bool]:
    del parent_stop, parent_receipt, parent_complete
    child_complete = bool(child_stop and child_receipt)
    # Council-local completion: child's complete bit is the parent's.
    parent_complete = child_complete
    return child_complete, parent_complete


def run_nested(
    *,
    child_expr: str,
    parent_expr: str,
    metrics: dict[str, Any],
    policy: str,
    child_receipt_complete: bool,
    parent_receipt_complete: bool,
    timeout_seconds: float = TIMEOUT_SECONDS,
    timeout_ticks: int = TIMEOUT_TICKS,
) -> dict[str, Any]:
    if policy not in {"shared", "local"}:
        raise ValueError(f"unknown policy {policy}")
    tick = _tick_shared if policy == "shared" else _tick_local
    child_complete = False
    parent_complete = False
    started = time.monotonic()
    timed_out = False
    ticks = 0
    terminal = "RUNNING"
    for ticks in range(1, timeout_ticks + 1):
        live = dict(metrics)
        live["child_complete"] = child_complete
        live["parent_complete"] = parent_complete
        child_stop = stopping_holds(child_expr, live)
        parent_stop = stopping_holds(parent_expr, live)
        child_complete, parent_complete = tick(
            child_stop=child_stop,
            parent_stop=parent_stop,
            child_receipt=child_receipt_complete,
            parent_receipt=parent_receipt_complete,
            child_complete=child_complete,
            parent_complete=parent_complete,
        )
        elapsed = time.monotonic() - started
        if child_complete and parent_complete:
            terminal = "BOTH_COMPLETE"
            break
        if child_complete != parent_complete:
            # Stable disagreement: do not wait out the timeout (that is deadlock).
            terminal = "DISAGREEMENT"
            break
        if elapsed >= timeout_seconds:
            timed_out = True
            terminal = "TIMEOUT"
            break
    else:
        timed_out = True
        terminal = "TIMEOUT"
        elapsed = time.monotonic() - started

    elapsed = time.monotonic() - started
    if terminal == "BOTH_COMPLETE":
        behaviour = "complete"
    elif timed_out and not child_complete and not parent_complete:
        behaviour = "spin"
        terminal = "DEADLOCK_DETECTED"
    elif child_complete and not parent_complete:
        behaviour = "block"
        terminal = "CHILD_COMPLETE_PARENT_BLOCKED"
    elif parent_complete and not child_complete:
        behaviour = "accept"
        terminal = "PARENT_COMPLETE_CHILD_INCOMPLETE"
    elif parent_complete and child_complete:
        behaviour = "complete"
        terminal = "BOTH_COMPLETE"
    else:
        behaviour = "spin"
        terminal = "DEADLOCK_DETECTED"

    # Local mutant on a child-complete/parent-unsatisfiable pair silently accepts.
    if policy == "local" and child_complete and parent_complete:
        parent_stop_alone = stopping_holds(parent_expr, dict(metrics, child_complete=True))
        if not parent_stop_alone:
            behaviour = "accept"
            terminal = "SILENT_ACCEPT_PARENT_COPIED_CHILD"

    return {
        "policy": policy,
        "shared_symbol": SHARED_SYMBOL,
        "child_expr": child_expr,
        "parent_expr": parent_expr,
        "metrics": dict(metrics),
        "child_receipt_complete": child_receipt_complete,
        "parent_receipt_complete": parent_receipt_complete,
        "child_complete": child_complete,
        "parent_complete": parent_complete,
        "child_stopping": stopping_holds(
            child_expr, dict(metrics, child_complete=child_complete, parent_complete=parent_complete)
        ),
        "parent_stopping": stopping_holds(
            parent_expr, dict(metrics, child_complete=child_complete, parent_complete=parent_complete)
        ),
        "terminal": terminal,
        "elapsed_behaviour": behaviour,
        "ticks": ticks,
        "elapsed_seconds": round(elapsed, 6),
        "timeout_seconds": timeout_seconds,
        "timeout_ticks": timeout_ticks,
        "timeout_fired": timed_out,
    }


def scenarios(receipts: dict[str, Any] | None = None) -> dict[str, Any]:
    rec = receipts or shared_receipts()
    good = rec["complete_receipt"]["complete"]
    bad = rec["incomplete_receipt"]["complete"]
    mismatch_metrics = {"rounds": 2, "proof_of_impossibility": False}
    consistent_metrics = {"rounds": 2, "proof_of_impossibility": False}
    deadlock_metrics = {"child_complete": False, "parent_complete": False}

    mismatch_shared = run_nested(
        child_expr=CHILD_SATISFIABLE,
        parent_expr=PARENT_UNSATISFIABLE,
        metrics=mismatch_metrics,
        policy="shared",
        child_receipt_complete=good,
        parent_receipt_complete=bad,
    )
    mismatch_local = run_nested(
        child_expr=CHILD_SATISFIABLE,
        parent_expr=PARENT_UNSATISFIABLE,
        metrics=mismatch_metrics,
        policy="local",
        child_receipt_complete=good,
        parent_receipt_complete=bad,
    )
    control = run_nested(
        child_expr=CHILD_SATISFIABLE,
        parent_expr=PARENT_CONSISTENT,
        metrics=consistent_metrics,
        policy="shared",
        child_receipt_complete=good,
        parent_receipt_complete=good,
    )
    deadlock = run_nested(
        child_expr=CHILD_WAITS_ON_PARENT,
        parent_expr=PARENT_WAITS_ON_CHILD,
        metrics=deadlock_metrics,
        policy="shared",
        child_receipt_complete=good,
        parent_receipt_complete=good,
        timeout_seconds=TIMEOUT_SECONDS,
        timeout_ticks=TIMEOUT_TICKS,
    )
    reverse = run_nested(
        child_expr=PARENT_UNSATISFIABLE,
        parent_expr=CHILD_SATISFIABLE,
        metrics=mismatch_metrics,
        policy="shared",
        child_receipt_complete=bad,
        parent_receipt_complete=good,
    )
    return {
        "receipts": rec,
        "mismatch_shared": mismatch_shared,
        "mismatch_local": mismatch_local,
        "control_consistent": control,
        "deadlock": deadlock,
        "reverse_parent_sat_child_unsat": reverse,
        "timeout_seconds_recorded": TIMEOUT_SECONDS,
        "timeout_ticks_recorded": TIMEOUT_TICKS,
    }


def assertions(bundle: dict[str, Any]) -> list[tuple[str, bool]]:
    ms = bundle["mismatch_shared"]
    ml = bundle["mismatch_local"]
    ctrl = bundle["control_consistent"]
    dl = bundle["deadlock"]
    rev = bundle["reverse_parent_sat_child_unsat"]
    rec = bundle["receipts"]
    return [
        ("shared_reducer_complete_receipt", rec["complete_receipt"]["complete"] is True),
        ("shared_reducer_incomplete_receipt", rec["incomplete_receipt"]["complete"] is False),
        ("mismatch_child_complete", ms["child_complete"] is True),
        ("mismatch_parent_blocked", ms["parent_complete"] is False),
        ("mismatch_behaviour_block", ms["elapsed_behaviour"] == "block"),
        ("mismatch_not_accept", ms["elapsed_behaviour"] != "accept"),
        ("mismatch_not_unbounded_spin", ms["timeout_fired"] is False),
        ("local_mutant_silent_accept", ml["elapsed_behaviour"] == "accept"),
        ("local_mutant_parent_complete", ml["parent_complete"] is True),
        ("control_both_complete", ctrl["terminal"] == "BOTH_COMPLETE"),
        ("control_child_complete", ctrl["child_complete"] is True),
        ("control_parent_complete", ctrl["parent_complete"] is True),
        ("deadlock_detected", dl["terminal"] == "DEADLOCK_DETECTED"),
        ("deadlock_timeout_fired", dl["timeout_fired"] is True),
        ("deadlock_timeout_seconds_recorded", isinstance(dl["timeout_seconds"], float)),
        ("deadlock_timeout_value", dl["timeout_seconds"] == TIMEOUT_SECONDS),
        ("reverse_does_not_complete_child", rev["child_complete"] is False),
        ("reverse_does_not_silently_complete_parent", rev["parent_complete"] is False),
    ]
