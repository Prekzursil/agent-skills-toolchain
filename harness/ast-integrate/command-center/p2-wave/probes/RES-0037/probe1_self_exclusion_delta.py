#!/usr/bin/env python3
"""Probe 1: OS process table, self-exclusion proof, start/stop delta.

Rail A is /proc/*/cmdline. A naive substring on RES-0037 matches this probe;
the token matcher does not. Starting one known stdio stand-in must move the
count by +1 and stopping it must return to baseline.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as M  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0037-probe1 {msg}")
    return 1


def main() -> int:
    try:
        delta = M.start_stop_delta()
        decoy = M.self_exclusion_with_decoy()
        transport = M.per_transport_counts()
        fleet = M.fleet_snapshot()
    except Exception as exc:
        return fail(f"exception:{type(exc).__name__}:{exc}")

    if not delta.get("pass"):
        return fail(f"start-stop or self-exclusion failed {delta}")
    if not decoy.get("pass"):
        return fail(f"decoy self-exclusion failed {decoy}")
    if not transport.get("pass"):
        return fail(f"per-transport process table failed {transport}")
    if delta["observed_start_delta"] != 1:
        return fail(f"start delta {delta['observed_start_delta']} != 1")
    if delta["observed_stop_delta"] != 0:
        return fail(f"stop delta {delta['observed_stop_delta']} != 0")
    if delta["naive_matcher_includes_probe"] is not True:
        return fail("naive matcher did not include probe (control silent)")
    if delta["actual_matcher_includes_probe_after_start"] is not False:
        return fail("token matcher matched the probe")
    if TOKEN_LEAK():
        return fail("token leaked onto probe argv")

    expected = M.N_SESSIONS * M.N_STDIO_SERVERS
    if transport["stdio_process_table"] != expected:
        return fail(f"stdio count {transport['stdio_process_table']} != {expected}")
    if transport["http_process_table"] != 1:
        return fail(f"http count {transport['http_process_table']} != 1")

    payload = {
        "probe": "probe1-self-exclusion-delta",
        "unit_id": "RES-0037",
        "rail": "/proc/*/cmdline exact-argv token",
        "self_match_proof": {
            "naive_pattern": "RES-0037",
            "naive_includes_probe": True,
            "token": M.TOKEN_STDIO,
            "token_absent_from_probe_argv": True,
            "actual_includes_probe": False,
            "stated_proof": (
                "While this probe is running, a substring match for 'RES-0037' "
                "includes this process because the script path contains that id. "
                "The production matcher requires an exact argv element "
                f"{M.TOKEN_STDIO!r} which is not on this probe's command line, "
                "so this PID is excluded. A start/stop of one known stand-in "
                "moves the token count by +1 then 0."
            ),
        },
        "start_stop_delta": delta,
        "decoy": decoy,
        "per_transport_process_count": {
            "stdio_os_processes": transport["stdio_process_table"],
            "http_os_processes": transport["http_process_table"],
            "sessions": transport["sessions"],
            "stdio_servers_per_session": transport["stdio_servers_per_session"],
            "processes_per_stdio_server_per_session": transport[
                "processes_per_stdio_server_per_session"
            ],
            "shared_http_processes": 1,
        },
        "fleet_naive_mcp_count": fleet["naive_substring_mcp_count"],
        "fleet_argv_exact_mcp_count": fleet["argv_exact_mcp_count"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "delta=+1/-0 naive_self=True token_self=False "
        f"stdio={transport['stdio_process_table']} http={transport['http_process_table']}"
    )
    print(
        "SUCCESS:RES-0037-probe1 process-table self-exclusion and start/stop delta"
    )
    return 0


def TOKEN_LEAK() -> bool:
    argv = M.read_cmdline(os_getpid()) or []
    return M.TOKEN_STDIO in argv or M.TOKEN_HTTP in argv


def os_getpid() -> int:
    import os

    return os.getpid()


if __name__ == "__main__":
    raise SystemExit(main())
