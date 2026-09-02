#!/usr/bin/env python3
"""Probe 1: process count scales as designed, not multiplicatively.

Opens N sessions against M servers under the eager (fault) policy and the
shared (designed) policy. Evidence is the OS process table, not the spawn
config. The eager run is the both-states control: the designed assertion
(count == M) is false on eager counts, so a stuck-green counter is impossible.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

SESSIONS = 3
SERVERS = H.SERVERS


def _fail(msg: str) -> int:
    print(f"FAILED:TST-0102-probe1 {msg}")
    return 1


def main() -> int:
    n = SESSIONS
    m = len(SERVERS)
    eager_token = H.make_token("eager")
    shared_token = H.make_token("shared")
    tmp = Path(tempfile.mkdtemp(prefix="tst0102-p1-"))
    cfg = H.new_config(SERVERS, enabled=True)
    H.write_config(tmp, cfg)
    try:
        H.spawn_sessions(cfg, n_sessions=n, mode="eager", token=eager_token)
        eager_rows = H.census(eager_token)
        eager_n = len(eager_rows)
        per_server_eager = {name: H.count_server(eager_token, name) for name in SERVERS}

        H.spawn_sessions(cfg, n_sessions=n, mode="shared", token=shared_token)
        shared_rows = H.census(shared_token)
        shared_n = len(shared_rows)
        per_server_shared = {name: H.count_server(shared_token, name) for name in SERVERS}

        verdict = H.designed_not_multiplicative(eager_n, shared_n, n, m)
        if not verdict["eager_is_multiplicative"]:
            return _fail(
                f"eager process-table count {eager_n} != N*M={n*m}; "
                "counter is not seeing per-session duplication"
            )
        if not verdict["shared_is_server_count"]:
            return _fail(f"shared process-table count {shared_n} != M={m}")
        if not verdict["shared_is_not_multiplicative"]:
            return _fail("shared count is multiplicative; designed policy did not hold")
        if not verdict["designed_ok"]:
            return _fail("designed_ok false")
        if not verdict["broken_policy_fails_designed_check"]:
            return _fail("both-states: eager counts still satisfy designed check")
        if any(c != n for c in per_server_eager.values()):
            return _fail(f"eager per-server {per_server_eager} want {n} each")
        if any(c != 1 for c in per_server_shared.values()):
            return _fail(f"shared per-server {per_server_shared} want 1 each")

        # Self-exclusion: this probe's pid must not appear in the worker census.
        import os

        me = os.getpid()
        if any(int(r["pid"]) == me for r in eager_rows + shared_rows):
            return _fail("census matched the probe process")

        payload = {
            "probe": "probe1-process-count-scales",
            "unit_id": "TST-0102",
            "instrument": "os-process-table",
            "config_path": str(tmp / "mcp-config.json"),
            "sessions": n,
            "servers": m,
            "server_names": list(SERVERS),
            "eager_count": eager_n,
            "shared_count": shared_n,
            "multiplicative_product": n * m,
            "per_server_eager": per_server_eager,
            "per_server_shared": per_server_shared,
            "verdict": verdict,
            "pass": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        print(
            f"eager={eager_n} shared={shared_n} product={n*m} "
            f"designed_ok={verdict['designed_ok']} both_states_red_on_eager=True"
        )
        print("SUCCESS:TST-0102-probe1 process-count-scales-as-designed")
        return 0
    finally:
        H.kill_token(eager_token)
        H.kill_token(shared_token)


if __name__ == "__main__":
    raise SystemExit(main())
