"""Shared TST-0103 checks used by both probes and the receipt emitter."""
from __future__ import annotations

import inspect

from commit import (
    Sample,
    demonstrate_commit_rss_divergence,
    live_host_snapshot,
    snapshot_from_meminfo,
)
from guard import CommitChargeGuard, WorkingSetGuard
from ramp import assert_ramp_invariants, run_default_ramps

FAKE_MEMINFO = """\
MemTotal:       100000 kB
MemAvailable:    80000 kB
Active:          90000 kB
CommitLimit:     50000 kB
Committed_AS:    10000 kB
"""


def probe1_live() -> tuple[dict, list[str]]:
    report = run_default_ramps()
    return report, assert_ramp_invariants(report)


def probe2_live() -> tuple[dict, list[str]]:
    errors: list[str] = []
    failing = Sample(
        step=0,
        ts_ns=0,
        commit_charge=95_000_000,
        available_commit=5_000_000,
        commit_limit=100_000_000,
        working_set=10_000_000,
        ram_total=100_000_000,
        n_processes=16,
        event="fixture-commit-exhaustion",
    )
    ram_pressure = Sample(
        step=0,
        ts_ns=0,
        commit_charge=10_000_000,
        available_commit=90_000_000,
        commit_limit=100_000_000,
        working_set=90_000_000,
        ram_total=100_000_000,
        n_processes=2,
        event="fixture-ram-pressure",
    )
    cc = CommitChargeGuard()
    ws = WorkingSetGuard()
    failing_cc = cc.should_shed(failing)
    failing_ws = ws.should_shed(failing)
    ram_cc = cc.should_shed(ram_pressure)
    ram_ws = ws.should_shed(ram_pressure)
    if not failing_cc:
        errors.append("commit-charge guard silent in commit-exhaustion fixture")
    if failing_ws:
        errors.append("working-set guard fired in commit-exhaustion fixture")
    if ram_cc:
        errors.append("commit-charge guard fired on RAM-pressure / low-commit fixture")
    if not ram_ws:
        errors.append("working-set guard silent on RAM-pressure fixture")

    bound = snapshot_from_meminfo(FAKE_MEMINFO)
    if bound.commit_charge != 10000 * 1024:
        errors.append("parser did not bind commit_charge to Committed_AS")
    if bound.working_set != 90000 * 1024:
        errors.append("parser did not bind working_set to Active")
    if bound.commit_limit != 50000 * 1024:
        errors.append("parser did not bind commit_limit to CommitLimit")
    if bound.available_commit != (50000 - 10000) * 1024:
        errors.append("available_commit is not CommitLimit - Committed_AS")
    if cc.should_shed(bound):
        errors.append("commit guard used Active (90%) instead of Committed_AS (20%)")

    src = inspect.getsource(CommitChargeGuard.should_shed)
    if "working_set" in src or "ram_total" in src:
        errors.append("CommitChargeGuard.should_shed consults working-set fields")
    if "commit_charge" not in src or "commit_limit" not in src:
        errors.append("CommitChargeGuard.should_shed does not read commit counters")

    host = live_host_snapshot()
    mmap_demo = demonstrate_commit_rss_divergence()
    if mmap_demo.get("skipped"):
        mmap_ok = True
    else:
        mmap_ok = bool(mmap_demo.get("commit_moved")) and bool(mmap_demo.get("rss_silent"))
        if not mmap_ok:
            errors.append(
                "live mmap did not diverge: commit_moved="
                f"{mmap_demo.get('commit_moved')} rss_silent="
                f"{mmap_demo.get('rss_silent')}"
            )

    details = {
        "failing_state": {
            "commit_guard_fired": failing_cc,
            "working_set_guard_silent": not failing_ws,
        },
        "ram_pressure_state": {
            "working_set_guard_fired": ram_ws,
            "commit_guard_silent": not ram_cc,
        },
        "parser_binding": {
            "commit_charge_bytes": bound.commit_charge,
            "working_set_bytes": bound.working_set,
            "commit_limit_bytes": bound.commit_limit,
            "available_commit_bytes": bound.available_commit,
            "commit_guard_silent_on_high_active": not cc.should_shed(bound),
        },
        "guard_source_is_commit_charge": (
            "working_set" not in src and "commit_charge" in src
        ),
        "host": {
            "commit_charge": host.commit_charge,
            "available_commit": host.available_commit,
            "commit_limit": host.commit_limit,
            "working_set": host.working_set,
            "ram_total": host.ram_total,
            "commit_charge_ne_working_set": host.commit_charge != host.working_set,
        },
        "mmap": mmap_demo,
        "mmap_ok": mmap_ok,
    }
    return details, errors
