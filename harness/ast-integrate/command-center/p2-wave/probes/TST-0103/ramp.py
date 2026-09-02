"""Load ramp: drive synthetic commit charge toward the limit.

Does not allocate host commit. Logical time is ramp-step * 1ms so shed vs
process-creation-failure ordering is a property of the spawn schedule.
"""
from __future__ import annotations

from dataclasses import dataclass

from commit import Sample
from guard import CommitChargeGuard, WorkingSetGuard
from kernel import (
    PROCESS_CREATION_FAIL,
    RESCUE_COMMIT,
    RESCUE_RSS,
    SimulatedCommitKernel,
)

# 100 MiB synthetic commit limit. 5 MiB committed per "MCP-like" worker,
# 64 KiB RSS: working-set percent stays ~0.01% of 8 GiB fake RAM.
COMMIT_LIMIT = 100 * 1024 * 1024
RAM_TOTAL = 8 * 1024 * 1024 * 1024
COMMIT_PER = 5 * 1024 * 1024
RSS_PER = 64 * 1024
MAX_STEPS = 40


@dataclass
class RampResult:
    kind: str
    shed: dict | None
    fail: dict | None
    samples: list[dict]
    n_spawns: int
    rescue_ok: bool | None

    def summary(self) -> dict:
        return {
            "kind": self.kind,
            "n_spawns": self.n_spawns,
            "shed": self.shed,
            "fail": self.fail,
            "rescue_ok": self.rescue_ok,
            "sample_count": len(self.samples),
            "samples": self.samples,
        }


def _event_dict(sample: Sample) -> dict:
    d = sample.to_dict()
    d["commit_ratio"] = round(sample.commit_ratio(), 6)
    d["working_set_ratio"] = round(sample.working_set_ratio(), 6)
    return d


def _kernel() -> SimulatedCommitKernel:
    return SimulatedCommitKernel(
        commit_limit=COMMIT_LIMIT,
        ram_total=RAM_TOTAL,
        commit_per_proc=COMMIT_PER,
        rss_per_proc=RSS_PER,
    )


def run_ramp(kind: str, guard) -> RampResult:
    kernel = _kernel()
    shed: dict | None = None
    fail: dict | None = None
    n_spawns = 0
    rescue_ok: bool | None = None
    for step in range(MAX_STEPS):
        snap = kernel.peek(step)
        kernel.history.append(
            Sample(
                step=step,
                ts_ns=snap.ts_ns,
                commit_charge=snap.commit_charge,
                available_commit=snap.available_commit,
                commit_limit=snap.commit_limit,
                working_set=snap.working_set,
                ram_total=snap.ram_total,
                n_processes=snap.n_processes,
                event="pre-spawn",
            )
        )
        if guard is not None and guard.should_shed(snap):
            kernel.clock.tick()
            shed_snap = kernel.snapshot(step, "shed")
            ok, rescue = kernel.try_spawn(
                step,
                commit=RESCUE_COMMIT,
                rss=RESCUE_RSS,
                event_ok="rescue-ok",
            )
            rescue_ok = ok
            shed = _event_dict(shed_snap)
            shed["rescue_spawn_succeeded"] = ok
            shed["rescue_event"] = rescue.event
            break
        ok, sample = kernel.try_spawn(step)
        if ok:
            n_spawns += 1
            continue
        fail = _event_dict(sample)
        break
    samples = []
    for s in kernel.history:
        if s.event in {"pre-spawn", "spawn-ok", "shed", PROCESS_CREATION_FAIL, "rescue-ok"}:
            samples.append(_event_dict(s))
    return RampResult(
        kind=kind,
        shed=shed,
        fail=fail,
        samples=samples,
        n_spawns=n_spawns,
        rescue_ok=rescue_ok,
    )


def run_default_ramps() -> dict:
    commit_g = CommitChargeGuard()
    ws_g = WorkingSetGuard()
    guarded = run_ramp("commit-charge-guard", commit_g)
    unguarded = run_ramp("unguarded", None)
    ws_only = run_ramp("working-set-guard", ws_g)
    shed_step = None if guarded.shed is None else guarded.shed["step"]
    fail_step = None if unguarded.fail is None else unguarded.fail["step"]
    shed_ts = None if guarded.shed is None else guarded.shed["ts_ns"]
    fail_ts = None if unguarded.fail is None else unguarded.fail["ts_ns"]
    return {
        "params": {
            "commit_limit": COMMIT_LIMIT,
            "ram_total": RAM_TOTAL,
            "commit_per_proc": COMMIT_PER,
            "rss_per_proc": RSS_PER,
            "shed_ratio": commit_g.shed_ratio,
            "max_steps": MAX_STEPS,
        },
        "guarded": guarded.summary(),
        "unguarded": unguarded.summary(),
        "working_set_guard": ws_only.summary(),
        "ordering": {
            "shed_step": shed_step,
            "fail_step": fail_step,
            "shed_logical_ts_ns": shed_ts,
            "fail_logical_ts_ns": fail_ts,
            "shed_before_fail": (
                shed_step is not None
                and fail_step is not None
                and shed_step < fail_step
                and shed_ts is not None
                and fail_ts is not None
                and shed_ts < fail_ts
            ),
            "guarded_rescue_spawn_succeeded": guarded.rescue_ok is True,
            "guarded_had_no_process_creation_failure": guarded.fail is None,
            "unguarded_process_creation_failed": unguarded.fail is not None
            and (unguarded.fail or {}).get("event") == PROCESS_CREATION_FAIL,
            "working_set_guard_did_not_shed": ws_only.shed is None,
            "working_set_guard_hit_process_creation_failure": ws_only.fail is not None,
        },
    }


def assert_ramp_invariants(report: dict) -> list[str]:
    errors: list[str] = []
    ord_ = report["ordering"]
    guarded = report["guarded"]
    unguarded = report["unguarded"]
    ws = report["working_set_guard"]
    if not ord_["shed_before_fail"]:
        errors.append("shed was not before process-creation failure on the spawn schedule")
    if not ord_["guarded_rescue_spawn_succeeded"]:
        errors.append("rescue spawn after shed failed; process creation already dead")
    if not ord_["guarded_had_no_process_creation_failure"]:
        errors.append("commit-charge guard still reached process-creation failure")
    if not ord_["unguarded_process_creation_failed"]:
        errors.append("unguarded ramp never hit process-creation failure")
    if not ord_["working_set_guard_did_not_shed"]:
        errors.append("working-set guard shed; it must stay silent at low RSS")
    if not ord_["working_set_guard_hit_process_creation_failure"]:
        errors.append("working-set guard did not reach process-creation failure")
    shed = guarded.get("shed") or {}
    fail = unguarded.get("fail") or {}
    if shed.get("commit_charge") is None or fail.get("commit_charge") is None:
        errors.append("missing commit_charge on shed or fail event")
    elif shed["commit_charge"] >= fail["commit_charge"]:
        errors.append("shed commit_charge was not below the fail commit_charge")
    if shed.get("available_commit") is None or shed["available_commit"] <= 0:
        errors.append("available_commit at shed was not a positive second counter")
    if fail.get("available_commit") is None or fail["available_commit"] >= shed.get(
        "available_commit", 0
    ):
        errors.append("available_commit did not drop from shed to fail")
    if shed.get("commit_charge") == shed.get("available_commit"):
        errors.append("commit_charge and available_commit are not two different counters")
    pre = [s for s in guarded.get("samples") or [] if s.get("event") == "pre-spawn"]
    if len(pre) < 8:
        errors.append("ramp did not sample enough pre-spawn points")
    for s in pre:
        if "commit_charge" not in s or "available_commit" not in s:
            errors.append("sample missing one of the two required counters")
            break
        if s["commit_charge"] + s["available_commit"] != s["commit_limit"]:
            errors.append("available_commit is not commit_limit - commit_charge")
            break
    return errors
