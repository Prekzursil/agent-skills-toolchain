#!/usr/bin/env python3
"""Probe 1: kill/crash/429/timeout/duplicate map to BLOCKED, never REFUTED."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from scenario import run_scenario  # noqa: E402

FORBIDDEN = frozenset({"CONFIRMED", "REFUTED"})


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0136-probe1 {msg}")
    return 1


def check_blocked(rec: dict, fault: str, prereq: str, label: str) -> str | None:
    if rec.get("verdict") != "BLOCKED":
        return f"{label} verdict={rec.get('verdict')} want=BLOCKED"
    if rec.get("verdict") in FORBIDDEN:
        return f"{label} laundered to {rec.get('verdict')}"
    if rec.get("fault_class") != fault:
        return f"{label} fault_class={rec.get('fault_class')} want={fault}"
    if rec.get("named_prerequisite") != prereq:
        return f"{label} prerequisite={rec.get('named_prerequisite')} want={prereq}"
    if rec.get("source_probe"):
        return f"{label} must not carry a claim source_probe"
    return None


def main() -> int:
    data = run_scenario()
    if not data.get("arrival_rate_required"):
        return fail("scheduler accepted arrival_rate_hz<=0")
    if data.get("quota_posture") != "NOT-CHECKED":
        return fail(f"quota_posture={data.get('quota_posture')} want=NOT-CHECKED")
    if not data.get("taxonomy_ok"):
        return fail("taxonomy row escaped BLOCKED or naive launderer broken")

    err = check_blocked(
        data["kill"], "severed-stream", "restore-confirmer-stream", "kill"
    )
    if err:
        return fail(err)
    err = check_blocked(
        data["crash"], "severed-stream", "restore-confirmer-stream", "crash"
    )
    if err:
        return fail(err)
    err = check_blocked(
        data["timeout"],
        "timeout-<n>s",
        "extend-or-split-confirmation-timeout",
        "timeout",
    )
    if err:
        return fail(err)
    if data["timeout"].get("timeout_seconds") != 30:
        return fail("timeout record missing timeout_seconds=30")
    err = check_blocked(
        data["duplicate"],
        "duplicate-dispatch",
        "dedupe-confirmation-job-id",
        "duplicate",
    )
    if err:
        return fail(err)

    burst = data["burst"]
    if len(burst) != 8:
        return fail(f"burst n={len(burst)} want=8")
    for i, rec in enumerate(burst):
        err = check_blocked(
            rec, "quota-429-storm", "vendor-quota-headroom", f"burst[{i}]"
        )
        if err:
            return fail(err)
    gaps = data["burst_gaps"]
    want = data["want_gap_ms"]
    if not gaps or any(g != want for g in gaps):
        return fail(f"stagger gaps={gaps} want_all={want}")
    if data["burst_slots"][0] != 0:
        return fail(f"first slot {data['burst_slots'][0]} want=0")

    summary = {
        "kill_verdict": data["kill"]["verdict"],
        "kill_fault": data["kill"]["fault_class"],
        "burst_n": len(burst),
        "burst_verdicts": sorted({r["verdict"] for r in burst}),
        "stagger_gap_ms": want,
        "timeout_fault": data["timeout"]["fault_class"],
        "duplicate_fault": data["duplicate"]["fault_class"],
        "quota_posture": data["quota_posture"],
        "pass": True,
        "probe": "probe1-fault-injection",
        "unit_id": "CNF-0136",
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "kill=BLOCKED/severed-stream "
        "burst=BLOCKED/quota-429-storm "
        f"stagger={want}ms "
        "timeout=BLOCKED "
        "duplicate=BLOCKED"
    )
    print("SUCCESS:CNF-0136-probe1 fault injection BLOCKED never REFUTED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
