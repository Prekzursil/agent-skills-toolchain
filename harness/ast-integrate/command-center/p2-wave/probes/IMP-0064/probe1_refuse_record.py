#!/usr/bin/env python3
"""Named probe 1: policy-violating spawn/write/network are refused and recorded.

Negative control: an allowed script performs the same classes of action in
the same run. Signal 1 is the refuse+record pair.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import DENY_EXIT, Scenario  # noqa: E402

ART = HERE.parents[3] / "command-center" / "receipts" / "IMP-0064.json"


def main() -> int:
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        blob = json.dumps(doc)
        if doc.get("unit_id") != "IMP-0064":
            print("FAILED:IMP-0064-probe1 unit_id", doc.get("unit_id"))
            return 1
        if "SUCCESS:IMP-0064" not in blob:
            print("FAILED:IMP-0064-probe1 sentinel absent")
            return 1
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:IMP-0064-probe1 self-declared", st)
            return 1

    sc = Scenario()
    try:
        allowed = sc.run_allowed()
        spawn = sc.run_spawn()
        write = sc.run_write()
        net = sc.run_net()
    finally:
        sc.close()

    if allowed.exit_code != 0 or "ALLOWED_OK" not in allowed.stdout:
        print("FAILED:IMP-0064-probe1 allowed script did not succeed", allowed.exit_code, allowed.stderr[-500:])
        return 1
    checks = [
        ("spawn", spawn, "FORBIDDEN_SPAWN"),
        ("write", write, "FORBIDDEN_WRITE"),
        ("network", net, "FORBIDDEN_NETWORK"),
    ]
    for name, result, code in checks:
        if not result.refused or result.exit_code != DENY_EXIT or code not in result.codes():
            print(f"FAILED:IMP-0064-probe1 {name} not refused+recorded", result.exit_code, result.codes(), result.stderr[-500:])
            return 1
        if f"UNREACHABLE_{name.upper()[:3]}" in result.stdout and name != "network":
            # spawn/write print UNREACHABLE_SPAWN / UNREACHABLE_WRITE
            pass
        if "UNREACHABLE_" in result.stdout:
            print(f"FAILED:IMP-0064-probe1 {name} continued after deny")
            return 1

    summary = {
        "probe": "probe1-refuse-record",
        "unit_id": "IMP-0064",
        "allowed_exit_code": allowed.exit_code,
        "spawn_refused": spawn.refused,
        "write_refused": write.refused,
        "network_refused": net.refused,
        "spawn_codes": spawn.codes(),
        "write_codes": write.codes(),
        "network_codes": net.codes(),
        "negative_control_allowed_ok": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0064-probe1 refuse-and-record plus allowed negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
