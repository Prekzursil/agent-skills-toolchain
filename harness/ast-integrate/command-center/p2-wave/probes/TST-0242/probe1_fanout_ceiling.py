#!/usr/bin/env python3
"""Probe 1: 10x fan-out ceiling holds; eager multiplication and commit-refuse fire.

External monitor: /proc cmdline count AND `ps` count, plus Committed_AS from
/proc/meminfo (commit charge, not working set) and a per-stub RSS+swap proxy.
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
from harness import (  # noqa: E402
    BASE_SESSIONS,
    BoundedPool,
    EAGER_CONTROL_SESSIONS,
    FANOUT_MULT,
    FANOUT_SESSIONS,
    N_SERVERS,
    PROCESS_CEILING,
    SERVERS,
    live_pressure,
    wait_agree,
)

ART = REPO / "command-center" / "receipts" / "TST-0242.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0242-probe1 {msg}")
    return 1


def token() -> str:
    return f"t242p1-{os.getpid()}-{time.time_ns() % 10**9}"


def main() -> int:
    mark_sh = token() + "-sh"
    mark_eg = token() + "-eg"
    mark_bd = token() + "-bd"

    with tempfile.TemporaryDirectory(prefix="tst0242-p1-") as tmp:
        tmp_path = Path(tmp)

        # --- shared / lazy 10x fan-out: process count stays at N_SERVERS ---
        pool_sh = act.make_pool(act.Mode.LAZY_SHARED, mark_sh, tmp_path / "sh")
        guard_sh = pg.production_guard(shared_pids=set(), process_ceiling=PROCESS_CEILING)
        bounded = BoundedPool(pool_sh, guard_sh, SERVERS)
        try:
            base_mem = pg.read_commit_charge()
            first = bounded.open_and_use("base-0")
            if not first.ok:
                return fail(f"baseline session refused: {first}")
            base = wait_agree(mark_sh, expected=N_SERVERS)
            guard_sh.shared_pids = set(base["procfs_pids"])
            if base["procfs_n"] != N_SERVERS or base["ps_n"] != N_SERVERS:
                return fail(f"baseline shared count {base}")

            extra = FANOUT_SESSIONS - BASE_SESSIONS
            for i in range(extra):
                admit = bounded.open_and_use(f"fan-{i}")
                if not admit.ok:
                    return fail(f"10x session fan-{i} refused under shared mode: {admit}")
            fan = wait_agree(mark_sh, expected=N_SERVERS)
            if fan["procfs_n"] != N_SERVERS or fan["ps_n"] != N_SERVERS:
                return fail(f"10x shared multiplied: {fan}")
            if bounded.peak_procfs != N_SERVERS or bounded.peak_ps != N_SERVERS:
                return fail(
                    f"peak {bounded.peak_procfs}/{bounded.peak_ps} != {N_SERVERS}"
                )
            if bounded.refusals:
                return fail(f"shared 10x produced refusals {bounded.refusals}")
            if bounded.admits != FANOUT_SESSIONS:
                return fail(f"admits {bounded.admits} want {FANOUT_SESSIONS}")
            after_mem = pg.read_commit_charge()
        finally:
            pool_sh.close()

        # --- eager unbounded: N sessions × N servers (regression seed :11326) ---
        pool_eg = act.make_pool(act.Mode.EAGER_STDIO, mark_eg, tmp_path / "eg")
        try:
            for i in range(EAGER_CONTROL_SESSIONS):
                handle = pool_eg.open_session(f"eager-{i}")
                for sid in SERVERS:
                    handle.ensure_server(sid)
            want_eager = EAGER_CONTROL_SESSIONS * N_SERVERS
            eager = wait_agree(mark_eg, expected=want_eager)
            if eager["procfs_n"] != want_eager:
                return fail(f"eager seed did not multiply: {eager} want {want_eager}")
        finally:
            pool_eg.close()

        # --- eager WITH budget: second session refused before spawn (:11327) ---
        pool_bd = act.make_pool(act.Mode.EAGER_STDIO, mark_bd, tmp_path / "bd")
        guard_bd = pg.production_guard(shared_pids=set(), process_ceiling=PROCESS_CEILING)
        bounded_eg = BoundedPool(pool_bd, guard_bd, SERVERS)
        try:
            a0 = bounded_eg.open_and_use("budget-0")
            if not a0.ok:
                return fail(f"eager-below-ceiling refused: {a0}")
            below = wait_agree(mark_bd, expected=N_SERVERS)
            spawned_before = bounded_eg.spawn_attempts
            a1 = bounded_eg.open_and_use("budget-1")
            if a1.ok:
                return fail("eager second session was admitted past process ceiling")
            if a1.would_spawn:
                return fail("refuse still set would_spawn True")
            if a1.reason != "process-ceiling-refuse-new-work":
                return fail(f"wrong refuse reason {a1.reason}")
            if bounded_eg.spawn_attempts != spawned_before:
                return fail("spawn attempted after process-ceiling refuse")
            after_refuse = wait_agree(mark_bd, expected=N_SERVERS)
            if after_refuse["procfs_n"] != N_SERVERS:
                return fail(f"process created after refuse: {after_refuse}")
        finally:
            pool_bd.close()

        # --- synthetic commit exhaustion: refuse before spawn; cold admits ---
        hot = live_pressure(mark_sh, PROCESS_CEILING, synthetic_commit_ratio=0.97)
        hot_guard = pg.production_guard(set(), PROCESS_CEILING)
        hot_admit = hot_guard.admit_new_work(hot, projected_new_children=N_SERVERS)
        if hot_admit.ok or hot_admit.would_spawn:
            return fail(f"commit-hot admitted {hot_admit}")
        if hot_admit.reason != "commit-pressure-refuse-new-work":
            return fail(f"commit-hot reason {hot_admit.reason}")
        cold = live_pressure(mark_sh, PROCESS_CEILING, synthetic_commit_ratio=0.20)
        cold_admit = hot_guard.admit_new_work(cold, projected_new_children=N_SERVERS)
        if not cold_admit.ok or not cold_admit.would_spawn:
            return fail(f"commit-cold refused {cold_admit}")

        if ART.is_file():
            text = ART.read_text(encoding="utf-8")
            if "SUCCESS:TST-0242" not in text:
                return fail("receipt sentinel absent")
            doc = json.loads(text)
            if doc.get("unit_id") != "TST-0242":
                return fail("receipt unit_id")
            if str(doc.get("state") or "").upper() in {
                "BLOCKED",
                "FAILED",
                "SEVERED",
                "TIMEOUT",
            }:
                return fail(f"receipt self-declared {doc.get('state')}")

        payload = {
            "probe": "probe1_fanout_ceiling",
            "n_servers": N_SERVERS,
            "base_sessions": BASE_SESSIONS,
            "fanout_mult": FANOUT_MULT,
            "fanout_sessions": FANOUT_SESSIONS,
            "process_ceiling": PROCESS_CEILING,
            "shared_baseline": {
                "procfs_n": base["procfs_n"],
                "ps_n": base["ps_n"],
                "commit_proxy_bytes": base["commit_proxy_bytes"],
                "committed_as_kb": base["committed_as_kb"],
            },
            "shared_10x": {
                "procfs_n": fan["procfs_n"],
                "ps_n": fan["ps_n"],
                "commit_proxy_bytes": fan["commit_proxy_bytes"],
                "committed_as_kb": fan["committed_as_kb"],
                "peak_procfs": bounded.peak_procfs,
                "peak_ps": bounded.peak_ps,
                "peak_commit_proxy_bytes": bounded.peak_commit_proxy,
            },
            "eager_unbounded": {
                "sessions": EAGER_CONTROL_SESSIONS,
                "procfs_n": eager["procfs_n"],
                "ps_n": eager["ps_n"],
                "want": EAGER_CONTROL_SESSIONS * N_SERVERS,
            },
            "eager_budget_refuse": {
                "below_ceiling_n": below["procfs_n"],
                "after_refuse_n": after_refuse["procfs_n"],
                "reason": a1.reason,
                "spawn_attempts": bounded_eg.spawn_attempts,
                "would_spawn": a1.would_spawn,
            },
            "commit_control": {
                "hot_ok": hot_admit.ok,
                "hot_would_spawn": hot_admit.would_spawn,
                "cold_ok": cold_admit.ok,
                "committed_as_kb_before": base_mem.get("committed_as_kb"),
                "committed_as_kb_after": after_mem.get("committed_as_kb"),
                "commit_limit_kb": after_mem.get("commit_limit_kb"),
            },
            "ceiling_held": True,
            "pass": True,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            "shared_10x="
            f"{fan['procfs_n']} eager={eager['procfs_n']} "
            f"peak={bounded.peak_procfs} refuse={a1.reason}"
        )
        print("SUCCESS:TST-0242-probe1 fanout-ceiling")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
