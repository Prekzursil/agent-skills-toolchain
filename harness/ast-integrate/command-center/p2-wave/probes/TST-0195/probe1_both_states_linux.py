#!/usr/bin/env python3
"""Probe 1: both-states control + live Linux exact-miss on Skills/ vs skills/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402
import lookup as L  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0195-probe1 {msg}")
    return 1


def main() -> int:
    doc = H.measure()
    host = doc["host"]
    linux = doc["linux"]
    windows = doc["windows"]
    contract = doc["contract"]

    if host["system"] != "Linux":
        return fail(f"expected Linux host, got {host['system']}")
    if "skills" not in host["listdir"] or "Skills" in host["listdir"]:
        return fail(f"fixture listing {host['listdir']}")
    if not host["live_os_exists_skills"]:
        return fail("live Path.exists('./skills/') is False — fixture missing")
    if host["live_os_exists_Skills"]:
        return fail("live Path.exists('./Skills/') is True — host is not case-sensitive")
    if not host["case_sensitive_skills_dir"]:
        return fail("host case-sensitive census failed")

    if linux["exact"]["ok"] is not True or linux["exact"]["warnings"]:
        return fail(f"linux exact not silent {linux['exact']}")
    if linux["mismatch"]["ok"] is not False or linux["mismatch"]["reason"] != "exact-miss":
        return fail(f"linux mismatch must exact-miss {linux['mismatch']}")
    if linux["exact_file"]["ok"] is not True:
        return fail(f"linux exact file {linux['exact_file']}")
    if linux["mismatch_file"]["ok"] is not False:
        return fail(f"linux mismatch file must miss {linux['mismatch_file']}")

    if windows["exact"]["ok"] is not True or windows["exact"]["warnings"]:
        return fail(f"windows exact not silent {windows['exact']}")
    if not contract["both_states_exact_silent"]:
        return fail(f"both-states {contract['both_states_why']}")
    if not contract["mismatch_declared"]:
        return fail(f"mismatch contract {contract['mismatch_why']}")

    live = L.live_os_exists(H.ROOT, H.MISMATCH)
    policy = linux["mismatch"]["ok"]
    if live is True or policy is True:
        return fail("linux live OS and policy must both miss Skills/")
    if live != policy:
        return fail("linux policy disagrees with live Path.exists")

    print(
        json.dumps(
            {
                "probe": "probe1-both-states-linux",
                "host_case_sensitive": True,
                "linux_exact_silent": True,
                "linux_Skills_exact_miss": True,
                "linux_live_os_agrees": True,
                "windows_exact_silent": True,
                "both_states": contract["both_states_why"],
                "mismatch_contract": contract["mismatch_why"],
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0195-probe1 both-states control and Linux exact-miss")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
