#!/usr/bin/env python3
"""Probe 2: RAM-percent control + never-kill shared service.

Mechanically different from probe 1:
  * both-states on the counter (commit-high/RAM-low vs commit-low/RAM-high)
  * a live dummy shared-service process that must still be alive after shed(kill)
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools"))

from headroom_guard.guard import (  # noqa: E402
    RAM_ONLY_CONTROL_PERCENT,
    HeadroomGuard,
    ShedRequest,
    pid_alive,
    ram_percent_would_fire,
)
from scenario import commit_high_ram_low, commit_low_ram_high  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0445.json"
SENTINEL = "SENTINEL:IMP-0445:HEADROOM-GUARD-COMMIT-CHARGE"


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0445-probe2 {msg}")
    return 1


def main() -> int:
    guard = HeadroomGuard()
    names = set(HeadroomGuard.decide.__code__.co_names)
    if "ram_percent_would_fire" in names:
        return fail("decide() bytecode calls the RAM-only comparator")

    estate = commit_high_ram_low()
    trap = commit_low_ram_high()

    d_estate = guard.decide(current_concurrency=2, requested_concurrency=4, snapshot=estate)
    d_trap = guard.decide(current_concurrency=2, requested_concurrency=4, snapshot=trap)

    ram_estate = ram_percent_would_fire(estate)
    ram_trap = ram_percent_would_fire(trap)

    # Both-states on the counter choice.
    if not d_estate.fired:
        return fail("estate signature (commit-high/RAM-low) did not fire the real guard")
    if ram_estate:
        return fail(
            f"RAM-percent alone would have fired on the estate signature "
            f"ram_percent={estate.ram_percent:.2f} threshold={RAM_ONLY_CONTROL_PERCENT}"
        )
    if d_trap.fired:
        return fail("commit-low/RAM-high fired the real guard (wrong-counter-read)")
    if not ram_trap:
        return fail(
            f"RAM-percent control did not fire on RAM-high "
            f"ram_percent={trap.ram_percent:.2f}"
        )
    if d_estate.kill_shared_service or d_trap.kill_shared_service:
        return fail("decision requested a shared-service kill")

    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(45)"],
    )
    time.sleep(0.15)
    if not pid_alive(child.pid):
        child.kill()
        return fail("dummy shared-service exited before shed")
    shed = guard.shed(
        ShedRequest(mode="kill", target_name="sshd", target_pid=child.pid)
    )
    still = pid_alive(child.pid)
    child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)
    if not shed.refused or shed.killed_pids:
        return fail(f"shed killed or did not refuse {shed.as_dict()}")
    if not still:
        return fail("dummy shared-service died during refused kill (guard-kills-shared-service)")
    if shed.action != "REFUSE_RAISE_CONCURRENCY":
        return fail(f"shed action={shed.action}")
    if not shed.protected_hit:
        return fail("sshd was not recognized as protected")

    if not ART.is_file():
        return fail("receipt artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel-absent")

    out = {
        "probe": "probe2-ram-control",
        "unit_id": "IMP-0445",
        "pass": True,
        "estate_commit_high_ram_low": {
            "commit_ratio": round(estate.commit_ratio, 6),
            "ram_percent": round(estate.ram_percent, 4),
            "guard_fired": d_estate.fired,
            "ram_only_would_fire": ram_estate,
        },
        "trap_commit_low_ram_high": {
            "commit_ratio": round(trap.commit_ratio, 6),
            "ram_percent": round(trap.ram_percent, 4),
            "guard_fired": d_trap.fired,
            "ram_only_would_fire": ram_trap,
        },
        "shared_service_survived_kill_request": still,
        "shed": shed.as_dict(),
        "ram_threshold_percent": RAM_ONLY_CONTROL_PERCENT,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"estate_guard_fired={d_estate.fired} estate_ram_only={ram_estate} "
        f"trap_guard_fired={d_trap.fired} trap_ram_only={ram_trap} "
        f"service_alive={still}"
    )
    print("SUCCESS:IMP-0445-probe2 RAM-percent control and refuse-kill shared service")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
