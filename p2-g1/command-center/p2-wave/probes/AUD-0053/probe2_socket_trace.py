#!/usr/bin/env python3
"""Probe 2: socket-level trace on an unblocked run, naming destination hosts.

Independent of probe 1's blocked-vs-unblocked outcome table. This probe never
installs the block hook; it only traces. Tests that merely TOUCH the network
show up here even when their outcome does not change under the block.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import socket

import time

from engine import (  # noqa: E402
    GET_PIP_HOST,
    SUITE_BUDGET,
    collect_product_files,
    control_files,
    destinations,
    install_hooks,
    run_file_child,
    uninstall_hooks,
)

CONNECT = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_connect_attempt.py"
)
HERMETIC = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_hermetic_noop.py"
)
GETPIP = (
    "command-center/p2-wave/probes/AUD-0053/controls/test_deliberate_fetch.py"
)


def fail(msg: str) -> int:
    print(f"FAILED:AUD-0053-probe2 {msg}")
    return 1


def live_trace_control_host() -> dict:
    """Fresh unblocked connect; do not consult the block hook."""
    install_hooks("trace")
    try:
        try:
            sock = socket.create_connection((GET_PIP_HOST, 443), timeout=2.0)
            sock.close()
            result = "connected"
            exc = None
        except Exception as err:  # noqa: BLE001
            result = type(err).__name__
            exc = str(err)
        dest = destinations(include_loopback=True)
    finally:
        uninstall_hooks()
    hosts = [d["host"] for d in dest]
    return {
        "result": result,
        "exception": exc,
        "hosts": hosts,
        "named_control_host": GET_PIP_HOST in hosts,
        "destinations": dest,
    }


def main() -> int:
    live = live_trace_control_host()

    specs = list(control_files())
    specs.extend(collect_product_files()["files"])
    traces = []
    hosts: dict[str, list[str]] = {}
    started = time.time()
    budget_hit = False
    for spec in specs:
        if time.time() - started > SUITE_BUDGET:
            budget_hit = True
            break
        rel = spec["repo_path"]
        traced = run_file_child(rel, "trace")
        traces.append(
            {
                "path": rel,
                "outcome": traced.get("outcome"),
                "egress_hosts": traced.get("egress_hosts") or [],
                "loopback_hosts": traced.get("loopback_hosts") or [],
                "touched_egress": bool(traced.get("touched_egress")),
                "destinations": traced.get("destinations") or [],
            }
        )
        for host in traced.get("egress_hosts") or []:
            hosts.setdefault(host, []).append(rel)

    by_path = {t["path"]: t for t in traces}
    connect = by_path.get(CONNECT)
    hermetic = by_path.get(HERMETIC)
    getpip = by_path.get(GETPIP)

    payload = {
        "pass": False,
        "probe": "probe2-socket-trace",
        "unit_id": "AUD-0053",
        "independent": True,
        "starts_from_blocked_outcome_table": False,
        "live_control_trace": live,
        "n_files_traced": len(traces),
        "budget_hit": budget_hit,
        "n_touch": sum(1 for t in traces if t["touched_egress"]),
        "destination_hosts": {h: sorted(set(p)) for h, p in sorted(hosts.items())},
        "touch_paths": [t["path"] for t in traces if t["touched_egress"]],
    }

    if connect is None or hermetic is None or getpip is None:
        print(json.dumps(payload, sort_keys=True))
        return fail("planted controls missing from trace rows")
    if GET_PIP_HOST not in (connect.get("egress_hosts") or []):
        print(json.dumps(payload, sort_keys=True))
        return fail("connect-attempt trace did not name bootstrap.pypa.io")
    if GET_PIP_HOST not in (getpip.get("egress_hosts") or []):
        print(json.dumps(payload, sort_keys=True))
        return fail("get-pip trace did not name bootstrap.pypa.io")
    if hermetic.get("touched_egress") or hermetic.get("egress_hosts"):
        print(json.dumps(payload, sort_keys=True))
        return fail("hermetic control showed egress in the socket trace")
    if not live.get("named_control_host"):
        print(json.dumps(payload, sort_keys=True))
        return fail("live unblocked trace did not name bootstrap.pypa.io")
    if "EgressBlocked" in str(live.get("result")):
        print(json.dumps(payload, sort_keys=True))
        return fail("probe2 still in block mode; this probe must only trace")

    payload["planted"] = {
        "connect_attempt_hosts": connect.get("egress_hosts"),
        "get_pip_hosts": getpip.get("egress_hosts"),
        "hermetic_hosts": hermetic.get("egress_hosts"),
    }
    payload["pass"] = True
    print(json.dumps(payload, sort_keys=True))
    print(
        "SUCCESS:AUD-0053-probe2 "
        f"touch={payload['n_touch']} hosts={len(hosts)} "
        f"control_host={GET_PIP_HOST}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
