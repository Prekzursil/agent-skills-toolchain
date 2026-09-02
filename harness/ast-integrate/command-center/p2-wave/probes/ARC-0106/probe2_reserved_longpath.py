#!/usr/bin/env python3
"""Probe 2: reserved-name (NUL via extended-length analogue), long path >260, case.

Asserts the live tooling handles or explicitly refuses reserved names rather
than crashing, exercises a path beyond 260 characters, and records the
failure mode. Case-insensitive collisions are planted as a second path axis.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import hostility as H  # noqa: E402

OUT = HERE / "probe2-hostility.raw.json"


def main() -> int:
    snap = H.measure_probe2()
    OUT.write_text(json.dumps(snap, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    reserved = snap["reserved_name"]
    longp = snap["long_path"]
    casec = snap["case_collision"]
    if not reserved.get("handled_or_refused_without_crash"):
        print("FAILED:ARC-0106-probe2 reserved-name crashed or was not exercised")
        return 1
    if not (reserved.get("created") or {}).get("NUL", {}).get("created"):
        print("FAILED:ARC-0106-probe2 NUL file was not created")
        return 1
    if reserved.get("unit_manifest", {}).get("crashed"):
        print("FAILED:ARC-0106-probe2 unit_manifest crashed on NUL")
        return 1
    if not longp.get("beyond_win_max_path"):
        print("FAILED:ARC-0106-probe2 path not beyond 260", longp.get("relative_len"))
        return 1
    if not longp.get("failure_mode"):
        print("FAILED:ARC-0106-probe2 long-path failure mode not recorded")
        return 1
    if longp.get("created") and longp.get("unit_manifest", {}).get("crashed"):
        print("FAILED:ARC-0106-probe2 unit_manifest crashed on long path")
        return 1
    if casec.get("linux_distinct_files", 0) < 2:
        print("FAILED:ARC-0106-probe2 case collision not planted")
        return 1
    if not casec.get("casefold_collisions"):
        print("FAILED:ARC-0106-probe2 casefold collision not detected")
        return 1
    print(
        "nul_created="
        + str(reserved["created"]["NUL"]["created"])
        + " nul_extended="
        + str(reserved["created"]["NUL"]["windows_extended_prefix"][:32])
        + " um_nul_handled="
        + str(reserved["unit_manifest"].get("handled"))
        + " long_rel_len="
        + str(longp.get("relative_len"))
        + " long_failure_mode="
        + str(longp.get("failure_mode"))
        + " case_files="
        + str(casec.get("linux_distinct_files"))
        + " casefold_collisions="
        + str(list(casec.get("casefold_collisions") or {}))
        + " contracts_present="
        + str(sum(1 for c in snap["contracts"] if c["present"]))
    )
    print("SUCCESS:ARC-0106-probe2 reserved-longpath-case")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
