#!/usr/bin/env python3
"""Probe 2: same load-set measurement on the current profile, as a diff.

Also proves the leaked-profile identity: copying current user skills into a
sandbox makes the user-key sets identical; an empty sandbox does not.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import loadset as L  # noqa: E402

RAW = HERE / "probe2-current-diff.raw.json"


def main() -> int:
    current_home = Path(os.environ.get("HOME") or str(Path.home()))
    leak = L.leak_identity_control(current_home, REPO)
    with L.make_empty_home() as home_s:
        clean = L.measure(Path(home_s), REPO)
    current = L.measure(current_home, REPO)
    delta = L.diff_sets(clean, current)
    # left = clean, right = current
    payload = {
        "probe": "probe2-current-diff",
        "unit_id": "AUD-0096",
        "method": "current-HOME-vs-empty-sandbox-set-diff",
        "current_home_kind": "linux-HOME",
        "current_cleanliness": current["cleanliness"]["clean"],
        "clean_counts": clean["counts"],
        "current_counts": current["counts"],
        "only_in_clean": delta["only_left"],
        "only_in_current": delta["only_right"],
        "shared": delta["shared"],
        "only_in_clean_count": delta["only_left_count"],
        "only_in_current_count": delta["only_right_count"],
        "shared_count": delta["shared_count"],
        "identical": delta["identical"],
        "leak_identity_control": leak,
        "current_items_user": [
            i for i in current["items"] if i["scope"] == "user"
        ],
    }
    RAW.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not leak["pass"]:
        print("FAILED:AUD-0096-probe2 leaked-profile identity control did not hold")
        return 1
    if current["cleanliness"]["clean"] is False and delta["identical"]:
        print(
            "FAILED:AUD-0096-probe2 current profile is dirty but load sets are "
            "identical — detector cannot see local state"
        )
        return 1
    if delta["only_left_count"] != 0:
        print("FAILED:AUD-0096-probe2 clean-only keys should be empty (clean is a subset)")
        return 1
    print(
        "current_user={0} only_in_current={1} shared={2} identical={3} leak_ok={4}".format(
            current["counts"]["user"],
            delta["only_right_count"],
            delta["shared_count"],
            delta["identical"],
            leak["pass"],
        )
    )
    print("SUCCESS:AUD-0096-probe2 current-profile diff plus leaked-profile identity")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
