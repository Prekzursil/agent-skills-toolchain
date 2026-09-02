#!/usr/bin/env python3
"""Probe 1: scratch-history controls for BLD-0018.

1. Renamed capability (same mechanism, new cap_id/label) is NOT a drop.
2. Planted quiet drop is caught as UNAPPROVED-DROP.
3. Drops with owner decision ids classify APPROVED-DROP, separately.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    scratch = E.load_scratch(REPO, HERE)
    ctl = E.control_report(scratch)
    print(json.dumps(ctl, indent=2, sort_keys=True))
    print(
        "rename_ids={0} approved={1} unapproved={2} kept={3}".format(
            ctl["rename_ids"],
            ctl["approved_drop_ids"],
            ctl["unapproved_drop_ids"],
            ctl["kept_ids"],
        )
    )
    if not ctl["rename_not_reported_as_drop"]:
        print("FAILED:BLD-0018-probe1 renamed capability was reported as a drop")
        return 1
    if not ctl["planted_unapproved_caught"]:
        print("FAILED:BLD-0018-probe1 planted drop not caught as UNAPPROVED-DROP")
        return 1
    if not ctl["approved_classified_separately"]:
        print("FAILED:BLD-0018-probe1 approved drops not classified separately")
        return 1
    if not ctl["kept_not_reported"]:
        print("FAILED:BLD-0018-probe1 kept capability reported as a drop")
        return 1
    if not ctl["pass"]:
        print("FAILED:BLD-0018-probe1 control bundle")
        return 1
    print("SUCCESS:BLD-0018-probe1 scratch-history rename/planted/approved controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
