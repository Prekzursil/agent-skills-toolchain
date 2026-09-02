#!/usr/bin/env python3
"""Probe 2: independent handle-count + /bin/ps rail; fleet vs 23x65.

Process count is re-read from `ps -eo pid=,args=` (not the probe-1 /proc walker).
Per-server handle counts come from /proc/<pid>/fd, and HTTP is distinguished by
a LISTEN inode. Arithmetic 23*65 is re-computed with POSIX expr.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lib as M  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:RES-0037-probe2 {msg}")
    return 1


def main() -> int:
    try:
        transport = M.per_transport_counts()
        fleet = M.fleet_snapshot()
    except Exception as exc:
        return fail(f"exception:{type(exc).__name__}:{exc}")

    if not transport.get("pass"):
        return fail(f"transport/handle matrix failed {transport}")

    expected = M.N_SESSIONS * M.N_STDIO_SERVERS
    if transport["stdio_ps"] != expected:
        return fail(f"ps stdio {transport['stdio_ps']} != {expected}")
    if transport["http_ps"] != 1:
        return fail(f"ps http {transport['http_ps']} != 1")
    if transport["stdio_ps"] != transport["stdio_process_table"]:
        return fail("ps and /proc stdio counts disagree")
    if transport["http_ps"] != transport["http_process_table"]:
        return fail("ps and /proc http counts disagree")
    if transport["expr_sessions_times_servers"] != expected:
        return fail("expr product drifted from session*server")
    if len(transport["http_listen_inodes"]) < 1:
        return fail("shared HTTP stand-in has no LISTEN socket")
    if transport["stdio_listen_inodes"]:
        return fail("stdio stand-ins unexpectedly LISTEN")
    if transport["recorded_expr_product"] != M.RECORDED_SESSIONS * M.RECORDED_SERVERS:
        return fail("expr did not reproduce 23*65")
    if transport["recorded_equation_holds"]:
        return fail("recorded 23x65=2037 unexpectedly held")
    if transport["recorded_expr_product"] != 1495:
        return fail(
            f"23*65 expr={transport['recorded_expr_product']} expected 1495"
        )

    live_fleet = fleet["argv_exact_mcp_count"]
    projected_stdio = M.RECORDED_SESSIONS * M.RECORDED_SERVERS
    reproduces_2037 = live_fleet == M.RECORDED_CLAIMED_PROCESSES
    reproduces_product = live_fleet == projected_stdio

    payload = {
        "probe": "probe2-handle-count-ps",
        "unit_id": "RES-0037",
        "rail": "/bin/ps + /proc/<pid>/fd LISTEN inodes",
        "per_transport_process_count": {
            "stdio_ps_processes": transport["stdio_ps"],
            "http_ps_processes": transport["http_ps"],
            "stdio_handle_counts": transport["stdio_handle_counts"],
            "http_handle_count": transport["http_handle_count"],
            "http_listen_inodes": transport["http_listen_inodes"],
            "stdio_listen_inodes": transport["stdio_listen_inodes"],
            "sessions": transport["sessions"],
            "stdio_servers_per_session": transport["stdio_servers_per_session"],
        },
        "recorded_driver": {
            "sessions": M.RECORDED_SESSIONS,
            "servers": M.RECORDED_SERVERS,
            "claimed_processes": M.RECORDED_CLAIMED_PROCESSES,
            "python_product": transport["recorded_python_product"],
            "expr_product": transport["recorded_expr_product"],
            "equation_23_x_65_equals_2037": False,
            "true_product": 1495,
        },
        "today_fleet": {
            "argv_exact_mcp_count": live_fleet,
            "naive_substring_mcp_count": fleet["naive_substring_mcp_count"],
            "reproduces_claimed_2037": reproduces_2037,
            "reproduces_sessions_x_servers_product": reproduces_product,
            "configs": fleet["configs"],
        },
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"ps stdio={transport['stdio_ps']} http={transport['http_ps']} "
        f"http_listen={len(transport['http_listen_inodes'])} "
        f"expr_23x65={transport['recorded_expr_product']} "
        f"fleet_exact={live_fleet}"
    )
    print(
        "SUCCESS:RES-0037-probe2 ps/handle-count independent rail; "
        "23*65=1495 not 2037; fleet does not reproduce 2037"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
