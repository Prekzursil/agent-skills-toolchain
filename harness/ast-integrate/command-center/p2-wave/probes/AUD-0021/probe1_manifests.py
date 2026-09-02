#!/usr/bin/env python3
"""Probe 1: parse every package.json into prod/dev/peer/optional classes.

Cross-check: os.walk vs find(1) with the same prune set. Headline count is
refused if the two populations disagree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402

OUT = HERE / "probe1-manifests.json"


def main() -> int:
    payload = I.inventory_manifests()
    OUT.write_text(
        json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8"
    )
    summary = {
        "walk_count": payload["walk_count"],
        "find_count": payload["find_count"],
        "find_exit_code": payload["find_exit_code"],
        "walk_vs_find_agreed": payload["walk_vs_find_agreed"],
        "totals_by_class": payload["totals_by_class"],
        "parse_errors": len(payload["parse_errors"]),
        "only_on_walk": payload["only_on_walk"],
        "only_on_find": payload["only_on_find"],
        "multi_spec_packages": len(
            payload["dependencies_declared_at_more_than_one_version"]
        ),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if not payload["find_available"]:
        print("FAILED:AUD-0021-probe1 find(1) unavailable; cannot cross-check population")
        return 1
    if not payload["walk_vs_find_agreed"]:
        print(
            "FAILED:AUD-0021-probe1 os.walk vs find disagree "
            f"only_walk={payload['only_on_walk']} only_find={payload['only_on_find']}"
        )
        return 1
    print(
        "SUCCESS:AUD-0021-probe1 manifests={0} prod={1} dev={2} peer={3} optional={4} walk_vs_find_agreed=True".format(
            payload["walk_count"],
            payload["totals_by_class"]["dependencies"],
            payload["totals_by_class"]["devDependencies"],
            payload["totals_by_class"]["peerDependencies"],
            payload["totals_by_class"]["optionalDependencies"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
