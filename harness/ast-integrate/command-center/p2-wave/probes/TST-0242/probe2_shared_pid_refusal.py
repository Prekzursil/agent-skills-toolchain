#!/usr/bin/env python3
"""Probe 2: detector control — shared-service PID is refused; mutant selects it.

Presents the production guard with a LIVE shared-service PID taken from the
OS process table (not the pool's internal dict). Audits the candidate-
selection list against the shared-service PID set. The kill-based mutant
(:11328) is the broken state: it selects the same PID.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

import mcp_activation as act  # noqa: E402
import pressure_guard as pg  # noqa: E402
from harness import wait_agree  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0242.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0242-probe2 {msg}")
    return 1


def main() -> int:
    mark = f"t242p2-{os.getpid()}-{time.time_ns() % 10**9}"
    with tempfile.TemporaryDirectory(prefix="tst0242-p2-") as tmp:
        pool = act.make_pool(act.Mode.SHARED_HTTP, mark, Path(tmp) / "rt")
        try:
            handle = pool.open_session("sess-live")
            ping = handle.call("shared-0", {"op": "ping"})
            snap = wait_agree(mark, expected=1)
            shared_pids = list(snap["procfs_pids"])
            if len(shared_pids) != 1:
                return fail(f"want one shared pid, got {shared_pids}")
            shared_pid = int(shared_pids[0])
            if int(ping.get("pid") or -1) != shared_pid:
                return fail(f"health pid {ping.get('pid')} != table pid {shared_pid}")

            # Adversarial presentation: kind=UNKNOWN, session dead — try to
            # disguise the shared PID as an orphan. Production must still spare.
            procs = [
                pg.Proc(
                    pid=shared_pid,
                    kind=pg.Kind.UNKNOWN,
                    session_id=None,
                    session_alive=False,
                    cmdline="disguised-shared",
                    name="shared-0",
                ),
                pg.Proc(
                    pid=8_000_001,
                    kind=pg.Kind.SESSION_CHILD,
                    session_id="dead-sess",
                    session_alive=False,
                    cmdline="orphan",
                ),
                pg.Proc(
                    pid=8_000_002,
                    kind=pg.Kind.SESSION_CHILD,
                    session_id="live-sess",
                    session_alive=True,
                    cmdline="live-child",
                ),
            ]

            good = pg.production_guard(shared_pids=[shared_pid], process_ceiling=5)
            good_decisions = good.select_candidates(procs)
            good_audit = pg.audit_kill_set(good_decisions, [shared_pid])
            if good_audit["shared_selected"]:
                return fail(f"production selected shared pid: {good_audit}")
            if shared_pid not in good_audit["spared"]:
                return fail(f"shared pid not spared: {good_audit}")
            by_pid = {d.pid: d for d in good_decisions}
            if by_pid[shared_pid].action != "spare":
                return fail(f"shared action {by_pid[shared_pid]}")
            if by_pid[shared_pid].reason != "shared-service-allowlist":
                return fail(f"shared reason {by_pid[shared_pid].reason}")
            if not by_pid[8_000_001].selected_for_kill:
                return fail("proven orphan was not a reap candidate")
            if by_pid[8_000_002].selected_for_kill:
                return fail("live session child was selected")
            if good.apply(good_decisions) != []:
                return fail("production apply() sent signals")

            mutant = pg.kill_based_mutant(shared_pids=[shared_pid], process_ceiling=5)
            bad_decisions = mutant.select_candidates(procs)
            bad_audit = pg.audit_kill_set(bad_decisions, [shared_pid])
            if not bad_audit["shared_selected"]:
                return fail(f"mutant did not select shared pid (silent bad state): {bad_audit}")
            if shared_pid not in bad_audit["kill_set"]:
                return fail(f"mutant kill set {bad_audit}")

            # Both-states: detector silent on good, fires on mutant.
            fired_on_bad = bool(bad_audit["shared_selected"])
            silent_on_good = not bool(good_audit["shared_selected"])
            if not (fired_on_bad and silent_on_good):
                return fail("detector does not discriminate both states")

            # Shared service still answers; we never killed it.
            ping2 = handle.call("shared-0", {"op": "health-after-select"})
            still = wait_agree(mark, expected=1)
            if still["procfs_n"] != 1 or shared_pid not in still["procfs_pids"]:
                return fail(f"shared service gone after select: {still}")
            if int(ping2.get("pid") or -1) != shared_pid:
                return fail(f"health after select pid {ping2.get('pid')}")
        finally:
            pool.close()

        if ART.is_file():
            text = ART.read_text(encoding="utf-8")
            if "SUCCESS:TST-0242" not in text:
                return fail("receipt sentinel absent")

        payload = {
            "probe": "probe2_shared_pid_refusal",
            "shared_pid": shared_pid,
            "production_audit": good_audit,
            "mutant_audit": bad_audit,
            "production_decisions": [
                {
                    "pid": d.pid,
                    "action": d.action,
                    "reason": d.reason,
                    "selected_for_kill": d.selected_for_kill,
                }
                for d in good_decisions
            ],
            "fired_on_bad": fired_on_bad,
            "silent_on_good": silent_on_good,
            "shared_survived": True,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"shared_pid={shared_pid} spared={good_audit['spared']} "
            f"mutant_overlap={bad_audit['overlap']} both_states=True"
        )
        print("SUCCESS:TST-0242-probe2 shared-pid-refusal")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
