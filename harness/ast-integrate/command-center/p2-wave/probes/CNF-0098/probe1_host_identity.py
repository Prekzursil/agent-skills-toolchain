#!/usr/bin/env python3
"""Named probe 1: live command signal (Darwin identity + failed provision).

Mechanically different from probe 2 (catalogue file-read + schema). Re-runs
uname/sw_vers/tart against the estate and checks the artifact fingerprint.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import estate as E  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0098-macos-reachability.json"
SENTINEL_PREFIX = "SUCCESS:CNF-0098"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0098-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0098":
        print("FAILED:CNF-0098-probe1 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL_PREFIX not in text:
        print("FAILED:CNF-0098-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:CNF-0098-probe1 self-declared", doc.get("state"))
        return 1

    live = E.signal_command()
    proofs = doc.get("two_signal_proof") or []
    cmd = next((p for p in proofs if p.get("method") == "command"), None)
    if cmd is None:
        print("FAILED:CNF-0098-probe1 no command signal in artifact")
        return 1
    if cmd.get("fingerprint") != live["fingerprint"]:
        print("FAILED:CNF-0098-probe1 command fingerprint drift")
        print("live", live["fingerprint"], live["observation"])
        print("art ", cmd.get("fingerprint"), cmd.get("observation"))
        return 1
    if live["this_host_darwin"] != bool(doc.get("this_host_darwin")):
        print("FAILED:CNF-0098-probe1 this_host_darwin drift")
        return 1
    if live["this_host_darwin"] and not doc.get("macos_reachable"):
        print("FAILED:CNF-0098-probe1 Darwin host but artifact says unreachable")
        return 1

    out = {
        "probe": "probe1-host-identity",
        "unit_id": "CNF-0098",
        "method": "command",
        "this_host_darwin": live["this_host_darwin"],
        "fingerprint": live["fingerprint"],
        "observation": live["observation"],
        "matches_artifact": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"this_host_darwin={live['this_host_darwin']} "
        f"sysname={live['observations']['sysname']} "
        f"sw_vers_exists={live['observations']['sw_vers'].get('exists')}"
    )
    print("SUCCESS:CNF-0098-probe1 Darwin identity and provision attempt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
