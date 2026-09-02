#!/usr/bin/env python3
"""Probe 1: clean-install the published artifact into an empty profile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402


def main() -> int:
    result = H.run_clean_install()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    pc = result.get("plugin_json_postcondition") or {}
    if not result.get("pass"):
        print("FAILED:TST-0070-probe1 clean install postcondition not met")
        return 1
    print(
        "empty_profile="
        + str((result.get("profile_before") or {}).get("empty"))
        + " plugin_json_exists="
        + str(pc.get("exists"))
        + " parses="
        + str(pc.get("parses"))
        + " bytes="
        + str(pc.get("bytes"))
        + " via="
        + str((result.get("install") or {}).get("via"))
        + " unpacked_is_repo_tools="
        + str(result.get("unpacked_is_repo_tools"))
    )
    print(
        "SUCCESS:TST-0070-probe1 clean install from packed artifact into empty "
        "profile; plugin.json exists AND parses AND meets min size"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
