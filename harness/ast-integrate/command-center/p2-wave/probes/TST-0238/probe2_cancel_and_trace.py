#!/usr/bin/env python3
"""Probe 2: OS-level process-creation trace + cancelled slow render.

Independent of the PATH shim: strace process-clones (clone without
CLONE_THREAD) over the same render. Injecting one spawn must move BOTH the
shim count and the clone count.

Regression seed: a slow render is CANCELLED, so the second helper never
launches. Spawn count (not wall-clock) is the budget.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))

from tools.hud.spawn_measure import install_shims, run_statusline  # noqa: E402
from tools.hud.statusline import SPAWN_CEILING  # noqa: E402

UID = "TST-0238"
PAYLOAD = HERE / "fixtures" / "payload.json"


def _run(tmp: Path, tag: str, extra: list[str], *, trace: bool) -> dict:
    shim_dir = tmp / f"shim-{tag}"
    log_path = tmp / f"spawn-{tag}.log"
    install_shims(shim_dir, log_path)
    strace_out = tmp / f"strace-{tag}.log" if trace else None
    args = [
        "--payload",
        str(PAYLOAD),
        "--state-dir",
        str(tmp / f"st-{tag}"),
        "--debounce-ms",
        "0",
        *extra,
    ]
    return run_statusline(
        REPO,
        extra_args=args,
        shim_dir=shim_dir,
        log_path=log_path,
        strace_out=strace_out,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0238-p2-") as tmp_s:
        tmp = Path(tmp_s)
        production = _run(tmp, "prod", [], trace=True)
        injected = _run(tmp, "inj", ["--inject-spawn", "true"], trace=True)
        cancelled = _run(tmp, "can", ["--slow", "--cancel-ms", "40"], trace=True)
        uncancelled = _run(
            tmp, "noc", ["--slow", "--no-cancel"], trace=True
        )

    def clones(row: dict) -> int:
        return int((row.get("strace") or {}).get("process_clones") or 0)

    p_sh, i_sh = int(production["shim_count"]), int(injected["shim_count"])
    p_cl, i_cl = clones(production), clones(injected)
    c_sh, u_sh = int(cancelled["shim_count"]), int(uncancelled["shim_count"])
    strace_ok = bool(production["strace"].get("available")) and bool(
        injected["strace"].get("available")
    )

    shim_moved = i_sh == p_sh + 1
    clones_moved = strace_ok and i_cl > p_cl
    cancel_fewer = c_sh < u_sh and c_sh >= 1 and u_sh >= 2
    cancelled_flag = "CANCELLED" in cancelled["stdout"]
    uncancelled_not = "CANCELLED" not in uncancelled["stdout"]
    prod_under = p_sh <= SPAWN_CEILING
    independent = strace_ok and shim_moved and clones_moved

    payload = {
        "probe": "probe2-os-trace-and-slow-cancel",
        "unit_id": UID,
        "reviewer_id": "TST-0238-probe2-os-trace-and-slow-cancel",
        "starts_from": "tests (named probes), not author summary",
        "pass": bool(
            independent
            and cancel_fewer
            and cancelled_flag
            and uncancelled_not
            and prod_under
            and production["exit_code"] == 0
            and injected["exit_code"] == 0
            and cancelled["exit_code"] == 0
            and uncancelled["exit_code"] == 0
        ),
        "independent_signals": {
            "a_shim_spawn_log": {
                "production": p_sh,
                "injected": i_sh,
                "incremented": shim_moved,
            },
            "b_strace_process_clones": {
                "available": strace_ok,
                "production": p_cl,
                "injected": i_cl,
                "moved": clones_moved,
                "production_execves": production["strace"].get("execves"),
                "injected_execves": injected["strace"].get("execves"),
            },
            "proc_stat_processes_delta": {
                "production": production.get("proc_stat_delta"),
                "injected": injected.get("proc_stat_delta"),
            },
        },
        "slow_render": {
            "cancelled_shim_count": c_sh,
            "uncancelled_shim_count": u_sh,
            "cancelled_fewer_spawns": cancel_fewer,
            "cancelled_stdout_marker": cancelled_flag,
            "uncancelled_completed": uncancelled_not,
            "cancelled_names": cancelled["shim_names"],
            "uncancelled_names": uncancelled["shim_names"],
            "budget": "spawn-count (slow helper cancelled; remaining helper not launched)",
        },
        "ceiling": SPAWN_CEILING,
        "production_under_ceiling": prod_under,
        "production_stdout": production["stdout"].strip(),
    }
    print(json.dumps(payload, sort_keys=True))
    if not strace_ok:
        print("FAILED:TST-0238-probe2 strace process-creation trace unavailable")
        return 1
    if not shim_moved:
        print("FAILED:TST-0238-probe2 shim did not increment on injected spawn")
        return 1
    if not clones_moved:
        print(
            f"FAILED:TST-0238-probe2 strace clones did not move "
            f"prod={p_cl} inj={i_cl}"
        )
        return 1
    if not cancel_fewer:
        print(
            f"FAILED:TST-0238-probe2 cancel spawn {c_sh} not < uncancelled {u_sh}"
        )
        return 1
    if not cancelled_flag or not uncancelled_not:
        print("FAILED:TST-0238-probe2 CANCELLED marker missing or leaked")
        return 1
    if not prod_under:
        print("FAILED:TST-0238-probe2 production spawn count exceeds ceiling")
        return 1
    print(
        f"shim {p_sh}->{i_sh} clones {p_cl}->{i_cl} "
        f"cancel {c_sh}<{u_sh} ceiling={SPAWN_CEILING}"
    )
    print("SUCCESS:TST-0238-probe2 OS-level trace and cancelled slow render")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
