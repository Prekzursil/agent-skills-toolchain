#!/usr/bin/env python3
"""TST-0225 probe 1: network:none fails at the network layer and is logged OOB.

Signal (a): the unit's socket.connect result (no declaration check in-process).
Signal (b): TUN sidecar log of the TCP SYN to the same destination.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "lib"))

import workspace as ws  # noqa: E402


def main() -> int:
    with ws.ephemeral_listener() as (host, port):
        denied = ws.run_canary(network="none", host=host, port=port, timeout=1.5)
        logged = ws.blocked_attempt_logged(denied, host, port)
        unit = denied.get("unit") or {}
        ifaces = list(denied.get("interfaces") or [])
        host_ifaces = ws.link_names()
        doc = {
            "probe": "probe1-network-none-blocked",
            "unit_id": "TST-0225",
            "host": host,
            "port": port,
            "denied": denied,
            "oob_hits": logged,
            "network_layer_failure": ws.network_layer_failure(unit),
            "tun_in_ns": "tun0" in ifaces,
            "ens3_absent_in_ns": "ens3" not in ifaces,
            "host_has_ens3": "ens3" in host_ifaces,
            "host_firewall_touched": denied.get("host_firewall_touched"),
            "checked_declaration": unit.get("checked_declaration"),
        }
        ok = (
            denied.get("network") == "none"
            and denied.get("substrate") == "unshare-net+tun-blackhole"
            and denied.get("host_firewall_touched") is False
            and unit.get("connected") is False
            and unit.get("checked_declaration") is False
            and ws.network_layer_failure(unit)
            and logged["ok"]
            and "tun0" in ifaces
            and "ens3" not in ifaces
        )
        doc["pass"] = bool(ok)
        print(json.dumps(doc, indent=2, sort_keys=True, default=str))
        if not ok:
            print("FAILED:TST-0225-probe1 network:none was not substrate-enforced")
            return 1
        print(
            "SUCCESS:TST-0225-probe1 network:none connect failed at the "
            f"network layer errno={unit.get('errno')} oob_hits={logged['count']}"
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
