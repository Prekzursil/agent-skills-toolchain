#!/usr/bin/env python3
"""Live fault-injection scenarios for TST-0091 (one hung unit vs a large batch)."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Event, Thread
from typing import Any, Callable

from pipeline import UnitSpec, naive_parallel, per_unit_pipeline, read_ledger, timeout_class

HERE = Path(__file__).resolve().parent
N = 12
HUNG_INDEX = 7
PER_UNIT_TIMEOUT_S = 0.2
SURVIVOR_SLEEP_S = 0.08
NAIVE_WATCHDOG_S = 0.55
PARTIAL_AFTER_S = 0.12
WALL_BUDGET_S = 0.65
NEG_WALL_BUDGET_S = 0.40


@dataclass
class HangController:
    gate: Event

    def __init__(self) -> None:
        self.gate = Event()

    def hang(self) -> None:
        self.gate.wait()

    def release(self) -> None:
        self.gate.set()


def _survivor(unit_id: str, sleep_s: float) -> Callable[[], dict[str, Any]]:
    def fn() -> dict[str, Any]:
        time.sleep(sleep_s)
        return {"unit_id": unit_id, "work": "complete"}

    return fn


def _hung(unit_id: str, ctrl: HangController) -> Callable[[], dict[str, Any]]:
    def fn() -> dict[str, Any]:
        ctrl.hang()
        return {"unit_id": unit_id, "work": "should-not-complete"}

    return fn


def cohort_ids() -> list[str]:
    return [f"unit-{i:02d}" for i in range(N)]


def hung_id() -> str:
    return cohort_ids()[HUNG_INDEX]


def make_specs(ctrl: HangController, *, include_hung: bool) -> list[UnitSpec]:
    specs: list[UnitSpec] = []
    for i, uid in enumerate(cohort_ids()):
        if include_hung and i == HUNG_INDEX:
            fn = _hung(uid, ctrl)
        else:
            fn = _survivor(uid, SURVIVOR_SLEEP_S)
        specs.append(UnitSpec(unit_id=uid, fn=fn, timeout_s=PER_UNIT_TIMEOUT_S))
    return specs


def ledger_dir(label: str) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%S")
    path = HERE / "runtime" / f"{stamp}-{label}-{time.monotonic_ns()}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_naive_watchdog(
    specs: list[UnitSpec],
    ledger: Path,
    watchdog_s: float = NAIVE_WATCHDOG_S,
) -> dict[str, Any]:
    box: dict[str, Any] = {}
    done = Event()

    def target() -> None:
        try:
            box["payloads"] = naive_parallel(specs, ledger_dir=ledger)
            box["ok"] = True
        except Exception as exc:  # noqa: BLE001 — record, do not swallow into success
            box["error"] = f"{type(exc).__name__}:{exc}"
        finally:
            done.set()

    Thread(target=target, name="tst-0091-naive-parallel", daemon=True).start()
    resolved = done.wait(timeout=watchdog_s)
    durable = read_ledger(ledger)
    return {
        "resolved": bool(resolved),
        "watchdog_s": watchdog_s,
        "n_durable": len(durable),
        "durable_ids": sorted(str(r.get("unit_id") or "") for r in durable),
        "durable_states": sorted(
            f"{r.get('unit_id')}:{r.get('state')}" for r in durable
        ),
        "box_ok": box.get("ok"),
        "error": box.get("error"),
        "ledger_dir": str(ledger),
    }


def run_fixed(specs: list[UnitSpec], ledger: Path) -> dict[str, Any]:
    return per_unit_pipeline(
        specs,
        ledger_dir=ledger,
        partial_after_s=PARTIAL_AFTER_S,
    )


def test_barrier_resolves_despite_one_hung_unit() -> dict[str, Any]:
    ctrl = HangController()
    specs = make_specs(ctrl, include_hung=True)
    naive_ledger = ledger_dir("naive-hung")
    fixed_ledger = ledger_dir("fixed-hung")
    try:
        naive = run_naive_watchdog(specs, naive_ledger)
        fixed = run_fixed(specs, fixed_ledger)
    finally:
        ctrl.release()
    expected_timeout = timeout_class(PER_UNIT_TIMEOUT_S)
    hung = hung_id()
    recs = {r["unit_id"]: r for r in fixed["records"]}
    ok = (
        naive["resolved"] is False
        and naive["n_durable"] == 0
        and fixed["resolved"] is True
        and fixed["n"] == N
        and fixed["n_success"] == N - 1
        and fixed["n_timeout"] == 1
        and fixed["wall_s"] < WALL_BUDGET_S
        and recs[hung]["state"] == "TIMEOUT"
        and recs[hung]["classification"] == expected_timeout
    )
    return {
        "id": "test_barrier_resolves_despite_one_hung_unit",
        "pass": ok,
        "n": N,
        "hung_id": hung,
        "naive": naive,
        "fixed": {
            "resolved": fixed["resolved"],
            "n": fixed["n"],
            "n_success": fixed["n_success"],
            "n_timeout": fixed["n_timeout"],
            "wall_s": fixed["wall_s"],
            "partial": fixed["partial"],
            "ledger_dir": fixed["ledger_dir"],
        },
        "both_states": {
            "naive_blocks": naive["resolved"] is False,
            "fixed_resolves": fixed["resolved"] is True,
            "naive_zero_durable": naive["n_durable"] == 0,
        },
    }


def test_hung_unit_is_classified_timeout_not_silently_dropped() -> dict[str, Any]:
    ctrl = HangController()
    specs = make_specs(ctrl, include_hung=True)
    ledger = ledger_dir("classify-hung")
    try:
        fixed = run_fixed(specs, ledger)
    finally:
        ctrl.release()
    hung = hung_id()
    recs = {r["unit_id"]: r for r in fixed["records"]}
    hung_rec = recs.get(hung)
    ids = [r["unit_id"] for r in fixed["records"]]
    dropped = hung not in ids
    mutant_drop = [r for r in fixed["records"] if r["unit_id"] != hung]
    expected = timeout_class(PER_UNIT_TIMEOUT_S)
    ok = (
        hung_rec is not None
        and not dropped
        and len(fixed["records"]) == N
        and hung_rec["state"] == "TIMEOUT"
        and hung_rec["classification"] == expected
        and hung_rec["payload"] is None
        and len(mutant_drop) == N - 1
    )
    return {
        "id": "test_hung_unit_is_classified_timeout_not_silently_dropped",
        "pass": ok,
        "hung_id": hung,
        "hung_record": hung_rec,
        "n_records": len(fixed["records"]),
        "dropped": dropped,
        "mutant_drop_count": len(mutant_drop),
        "expected_classification": expected,
        "ledger_ids": sorted(str(r.get("unit_id") or "") for r in read_ledger(ledger)),
    }


def test_survivor_results_are_complete_and_attributed() -> dict[str, Any]:
    ctrl = HangController()
    specs = make_specs(ctrl, include_hung=True)
    ledger = ledger_dir("survivors")
    try:
        fixed = run_fixed(specs, ledger)
    finally:
        ctrl.release()
    hung = hung_id()
    survivors = [r for r in fixed["records"] if r["unit_id"] != hung]
    durable = {r["unit_id"]: r for r in read_ledger(ledger)}
    complete = []
    for rec in survivors:
        payload = rec.get("payload") or {}
        row = {
            "unit_id": rec["unit_id"],
            "state": rec["state"],
            "attributed": rec.get("attributed") is True
            and payload.get("unit_id") == rec["unit_id"]
            and payload.get("work") == "complete",
            "durable": rec["unit_id"] in durable
            and durable[rec["unit_id"]].get("state") == "SUCCESS",
        }
        complete.append(row)
    all_ok = (
        len(survivors) == N - 1
        and all(r["state"] == "SUCCESS" for r in survivors)
        and all(r["attributed"] and r["durable"] for r in complete)
        and hung in durable
        and durable[hung].get("state") == "TIMEOUT"
    )
    partial = fixed.get("partial") or {}
    surv_written = [
        r.get("written_monotonic")
        for r in fixed["records"]
        if r["unit_id"] != hung
    ]
    hung_written = next(
        (r.get("written_monotonic") for r in fixed["records"] if r["unit_id"] == hung),
        None,
    )
    write_as_you_go = (
        hung_written is not None
        and all(isinstance(t, (int, float)) for t in surv_written)
        and max(surv_written) < hung_written
    )
    return {
        "id": "test_survivor_results_are_complete_and_attributed",
        "pass": all_ok and write_as_you_go,
        "n_survivors": len(survivors),
        "all_success": all(r["state"] == "SUCCESS" for r in survivors),
        "all_attributed": all(r["attributed"] for r in complete),
        "all_durable": all(r["durable"] for r in complete),
        "write_as_you_go": write_as_you_go,
        "partial": partial,
        "survivor_ids": [r["unit_id"] for r in survivors],
    }


def negative_control_no_hung() -> dict[str, Any]:
    ctrl = HangController()
    specs = make_specs(ctrl, include_hung=False)
    ledger = ledger_dir("negative-all-healthy")
    try:
        fixed = run_fixed(specs, ledger)
    finally:
        ctrl.release()
    ok = (
        fixed["resolved"] is True
        and fixed["n"] == N
        and fixed["n_success"] == N
        and fixed["n_timeout"] == 0
        and fixed["wall_s"] < NEG_WALL_BUDGET_S
        and all(r["state"] == "SUCCESS" for r in fixed["records"])
        and all(r["classification"] == "completed" for r in fixed["records"])
    )
    return {
        "id": "negative_control_no_hung",
        "pass": ok,
        "n": fixed["n"],
        "n_success": fixed["n_success"],
        "n_timeout": fixed["n_timeout"],
        "wall_s": fixed["wall_s"],
        "silent_on_good": ok,
    }


def run_all() -> dict[str, Any]:
    t0 = time.monotonic()
    barrier = test_barrier_resolves_despite_one_hung_unit()
    classify = test_hung_unit_is_classified_timeout_not_silently_dropped()
    survivors = test_survivor_results_are_complete_and_attributed()
    negative = negative_control_no_hung()
    passed = all(x["pass"] for x in (barrier, classify, survivors, negative))
    return {
        "pass": passed,
        "n": N,
        "hung_id": hung_id(),
        "per_unit_timeout_s": PER_UNIT_TIMEOUT_S,
        "timeout_classification": timeout_class(PER_UNIT_TIMEOUT_S),
        "survivor_sleep_s": SURVIVOR_SLEEP_S,
        "naive_watchdog_s": NAIVE_WATCHDOG_S,
        "wall_s": time.monotonic() - t0,
        "test_barrier_resolves_despite_one_hung_unit": barrier,
        "test_hung_unit_is_classified_timeout_not_silently_dropped": classify,
        "test_survivor_results_are_complete_and_attributed": survivors,
        "negative_control_no_hung": negative,
    }


def main() -> int:
    out = run_all()
    print(json.dumps(out, sort_keys=True, default=str))
    if not out["pass"]:
        print("FAILED:TST-0091 scenario")
        return 1
    print("SUCCESS:TST-0091-scenario")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
