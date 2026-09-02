"""Clock-jump lab for TST-0154.

Two independent measurements:
  (a) unit state across a simulated NTP step (wall jumps, monotonic does not)
  (b) static scan that elapsed computation does not read a wall-clock source

Negative control: the same classifier fed wall-clock timestamps fails both
jump directions. Both-states: a real timeout still fires on monotonic elapsed.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PKG = REPO / "tools" / "command-center"
if str(PKG) not in sys.path:
    sys.path.insert(0, str(PKG))

from elapsed import (  # noqa: E402
    Classification,
    FakeClock,
    UnitTimes,
    classify,
    wall_clock_hits,
)

TIMEOUT_S = 10.0
STALL_AFTER_S = 2.0
JUMP = 3600.0


@dataclass
class DualClock:
    """Wall time can NTP-step independently of monotonic elapsed."""

    monotonic: float = 0.0
    wall: float = 1_725_000_000.0

    def elapse(self, seconds: float) -> None:
        self.monotonic += float(seconds)
        self.wall += float(seconds)

    def ntp_step(self, wall_delta: float) -> None:
        self.wall += float(wall_delta)


def _running(clock: DualClock, uid: str = "running") -> tuple[UnitTimes, UnitTimes]:
    mono = UnitTimes(uid, clock.monotonic, clock.monotonic, TIMEOUT_S, STALL_AFTER_S)
    wall = UnitTimes(uid, clock.wall, clock.wall, TIMEOUT_S, STALL_AFTER_S)
    return mono, wall


def _stalled_pair(clock: DualClock, uid: str = "stalled") -> tuple[UnitTimes, UnitTimes]:
    started_m = clock.monotonic
    started_w = clock.wall
    clock.elapse(5.0)
    mono = UnitTimes(uid, started_m, started_m, 100.0, STALL_AFTER_S)
    wall = UnitTimes(uid, started_w, started_w, 100.0, STALL_AFTER_S)
    return mono, wall


def _row(label: str, prod: Classification, mutant: Classification) -> dict:
    return {
        "id": label,
        "production_state": prod.state,
        "wall_mutant_state": mutant.state,
        "production_elapsed_s": prod.elapsed_s,
        "wall_mutant_elapsed_s": mutant.elapsed_s,
        "production_idle_s": prod.idle_s,
        "wall_mutant_idle_s": mutant.idle_s,
    }


def measure_clock_jumps() -> dict:
    """Signal (a): state across backward and forward wall jumps."""
    rows: list[dict] = []

    c = DualClock()
    run_m, run_w = _running(c)
    c.elapse(1.0)
    before = classify(run_m, c.monotonic)
    c.ntp_step(-JUMP)
    after_back = classify(run_m, c.monotonic)
    mutant_back = classify(run_w, c.wall)
    rows.append({**_row("running-backward-jump", after_back, mutant_back), "pre_jump_state": before.state})

    c = DualClock()
    run_m, run_w = _running(c)
    c.elapse(1.0)
    c.ntp_step(+JUMP)
    after_fwd = classify(run_m, c.monotonic)
    mutant_fwd = classify(run_w, c.wall)
    rows.append(_row("running-forward-jump", after_fwd, mutant_fwd))

    c = DualClock()
    st_m, st_w = _stalled_pair(c)
    pre_stall = classify(st_m, c.monotonic)
    c.ntp_step(-JUMP)
    stall_back = classify(st_m, c.monotonic)
    mutant_stall_back = classify(st_w, c.wall)
    rows.append({**_row("stalled-backward-jump", stall_back, mutant_stall_back), "pre_jump_state": pre_stall.state})

    c = DualClock()
    st_m, st_w = _stalled_pair(c)
    c.ntp_step(+JUMP)
    stall_fwd = classify(st_m, c.monotonic)
    mutant_stall_fwd = classify(st_w, c.wall)
    rows.append(_row("stalled-forward-jump", stall_fwd, mutant_stall_fwd))

    running_survives_back = after_back.state == "RUNNING"
    running_survives_fwd = after_fwd.state == "RUNNING"
    stalled_survives_back = stall_back.state == "STALLED"
    stalled_survives_fwd = stall_fwd.state == "STALLED"
    production_survives = all(
        [running_survives_back, running_survives_fwd, stalled_survives_back, stalled_survives_fwd]
    )

    wall_fails_forward = mutant_fwd.state == "TIMED_OUT"
    wall_fails_backward = mutant_stall_back.state == "RUNNING"
    wall_fails_both = wall_fails_forward and wall_fails_backward

    # Both-states timeout: keep stall_after above the mid-point so the unit is
    # still RUNNING at 3s, then TIMED_OUT after monotonic elapsed crosses 10s
    # while wall jumps both ways. Progress is refreshed so stall is not the path.
    c = DualClock()
    to_m = UnitTimes("timeout", 0.0, 0.0, TIMEOUT_S, stall_after_s=100.0)
    to_w = UnitTimes("timeout", c.wall, c.wall, TIMEOUT_S, stall_after_s=100.0)
    c.elapse(3.0)
    to_m = UnitTimes("timeout", 0.0, c.monotonic, TIMEOUT_S, stall_after_s=100.0)
    c.ntp_step(-JUMP)
    mid = classify(to_m, c.monotonic)
    c.elapse(8.0)
    to_m = UnitTimes("timeout", 0.0, c.monotonic, TIMEOUT_S, stall_after_s=100.0)
    c.ntp_step(+JUMP)
    fired = classify(to_m, c.monotonic)
    mutant_at_fire = classify(to_w, c.wall)
    timeout_still_fires = mid.state == "RUNNING" and fired.state == "TIMED_OUT"

    passed = production_survives and wall_fails_both and timeout_still_fires
    return {
        "probe": "clock-jump",
        "pass": passed,
        "production_survives_jumps": production_survives,
        "running_survives_backward": running_survives_back,
        "running_survives_forward": running_survives_fwd,
        "stalled_survives_backward": stalled_survives_back,
        "stalled_survives_forward": stalled_survives_fwd,
        "wall_mutant_fails_both_directions": wall_fails_both,
        "wall_mutant_running_forward_is_timed_out": wall_fails_forward,
        "wall_mutant_stalled_backward_is_fresh": wall_fails_backward,
        "both_states_timeout_still_fires": timeout_still_fires,
        "both_states_early_not_timeout": mid.state != "TIMED_OUT",
        "timeout_mid_state": mid.state,
        "timeout_fired_state": fired.state,
        "timeout_mutant_state": mutant_at_fire.state,
        "jump_s": JUMP,
        "timeout_s": TIMEOUT_S,
        "stall_after_s": STALL_AFTER_S,
        "rows": rows,
    }


def measure_static() -> dict:
    """Signal (b): no elapsed computation reads a wall-clock source."""
    elapsed_path = REPO / "tools" / "command-center" / "elapsed.py"
    heartbeat_path = REPO / "tools" / "plugin" / "heartbeat.py"
    longrun_sh = REPO / "scripts" / "longrun.sh"
    longrun_ps1 = REPO / "scripts" / "longrun.ps1"

    elapsed_src = elapsed_path.read_text(encoding="utf-8")
    hb_src = heartbeat_path.read_text(encoding="utf-8")
    sh_src = longrun_sh.read_text(encoding="utf-8") if longrun_sh.is_file() else ""
    ps_src = longrun_ps1.read_text(encoding="utf-8") if longrun_ps1.is_file() else ""

    elapsed_hits = wall_clock_hits(elapsed_src, "tools/command-center/elapsed.py")
    hb_hits = wall_clock_hits(hb_src, "tools/plugin/heartbeat.py")

    hb_hang_uses_monotonic = "time.monotonic()" in hb_src and "hang_timeout_sec" in hb_src
    hb_uses_time_time = "time.time()" in hb_src
    sh_delegates = "heartbeat.py" in sh_src
    ps_delegates = "heartbeat.py" in ps_src
    sh_no_date = "date +" not in sh_src and "$(date" not in sh_src
    ps_no_utcnow = "UtcNow" not in ps_src and "Get-Date" not in ps_src

    planted = "elapsed = time.time() - started\n"
    planted_hits = wall_clock_hits(planted, "<planted-wall-clock>")
    detector_fires_on_bad = any(h.get("attr") == "time" for h in planted_hits)
    detector_silent_on_good = len(elapsed_hits) == 0

    passed = (
        detector_silent_on_good
        and hb_hang_uses_monotonic
        and not hb_uses_time_time
        and sh_delegates
        and ps_delegates
        and sh_no_date
        and ps_no_utcnow
        and detector_fires_on_bad
    )
    return {
        "probe": "static-wall-clock",
        "pass": passed,
        "elapsed_wall_hits": elapsed_hits,
        "heartbeat_wall_hits": hb_hits,
        "heartbeat_hang_uses_monotonic": hb_hang_uses_monotonic,
        "heartbeat_uses_time_time": hb_uses_time_time,
        "longrun_sh_delegates_heartbeat": sh_delegates,
        "longrun_ps1_delegates_heartbeat": ps_delegates,
        "longrun_sh_no_date": sh_no_date,
        "longrun_ps1_no_utcnow": ps_no_utcnow,
        "detector_fires_on_planted_wall_clock": detector_fires_on_bad,
        "detector_silent_on_elapsed_py": detector_silent_on_good,
        "files_scanned": [
            "tools/command-center/elapsed.py",
            "tools/plugin/heartbeat.py",
            "scripts/longrun.sh",
            "scripts/longrun.ps1",
        ],
    }


def measure_all() -> dict:
    jumps = measure_clock_jumps()
    static = measure_static()
    clock = FakeClock(0.0)
    unit = UnitTimes("fake", 0.0, 0.0, 10.0, 2.0)
    clock.sleep(1.0)
    early = classify(unit, clock.now())
    clock.sleep(10.0)
    late = classify(unit, clock.now())
    fake_ok = early.state == "RUNNING" and late.state == "TIMED_OUT"
    passed = bool(jumps["pass"] and static["pass"] and fake_ok)
    return {
        "pass": passed,
        "clock_jumps": jumps,
        "static": static,
        "fake_clock_timeout": {
            "early": asdict(early),
            "late": asdict(late),
            "ok": fake_ok,
        },
    }


def dump(doc: dict) -> None:
    print(json.dumps(doc, indent=2, sort_keys=True, default=str))
