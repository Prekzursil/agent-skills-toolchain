#!/usr/bin/env python3
"""Probe 1: load-set measured in a proven-clean sandboxed profile."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import loadset as L  # noqa: E402

RAW = HERE / "probe1-clean-profile.raw.json"


def main() -> int:
    control = L.both_states_cleanliness_control(REPO)
    with L.make_empty_home() as home_s:
        home = Path(home_s)
        cleanliness = L.harness_load_roots_status(home)
        measured = L.measure(home, REPO)
    payload = {
        "probe": "probe1-clean-profile",
        "unit_id": "AUD-0096",
        "method": "sandboxed-empty-HOME-plus-repo-load-roots",
        "substrate": "linux",
        "windows_user_profile_available": False,
        "sandbox_used": True,
        "cleanliness_control": control,
        "sandbox_clean_before_measure": cleanliness["clean"],
        "counts": measured["counts"],
        "user_keys": measured["user_keys"],
        "project_keys": measured["project_keys"],
        "items": measured["items"],
        "cleanliness_roots": cleanliness["roots"],
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not control["pass"]:
        print("FAILED:AUD-0096-probe1 cleanliness both-states control did not discriminate")
        return 1
    if not cleanliness["clean"]:
        print("FAILED:AUD-0096-probe1 sandbox was not proven clean before measure")
        return 1
    if measured["counts"]["user"] != 0:
        print("FAILED:AUD-0096-probe1 clean sandbox still has user-profile loadables")
        return 1
    print(
        "clean_user={0} project={1} skills={2} hooks={3} rules={4} plugins={5} mcp={6}".format(
            measured["counts"]["user"],
            measured["counts"]["project"],
            measured["counts"]["skill"],
            measured["counts"]["hook"],
            measured["counts"]["rule"],
            measured["counts"]["plugin"],
            measured["counts"]["mcp"],
        )
    )
    print("SUCCESS:AUD-0096-probe1 clean-profile load set with both-states cleanliness control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
