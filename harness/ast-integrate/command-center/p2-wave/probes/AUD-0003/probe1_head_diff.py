#!/usr/bin/env python3
"""Probe 1: git diff <head> main --name-only limited to files the PR touched."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

OUT = HERE / "probe1-head-diff.json"


def main() -> int:
    world, census, _control, live = C.run_world()
    errors = C.expected_rows_ok(census)
    commands = []
    for row in census["rows"]:
        commands.append(
            {
                "pr": row["number"],
                "command": row["probe1_command"],
                "touched": row["touched_files"],
                "unlimited_name_only": row["unlimited_diff_name_only"],
                "limited_missing": row["probe1_limited_missing"],
            }
        )
    payload = {
        "probe": "probe1-head-diff",
        "unit_id": C.UNIT,
        "instrument": "git diff <head> main --name-only, intersected with files the PR touched",
        "fixture_pr_count": census["pr_count"],
        "absent_count": census["absent_count"],
        "commands": commands,
        "rows": census["rows"],
        "live_owner_census": {
            "live_pr_count": live["live_pr_count"],
            "not_checked_reason": live["not_checked_reason"],
        },
        "limit_is_load_bearing": any(
            row["number"] == 10 and row["unlimited_diff_count"] > 0 and not row["missing_files"]
            for row in census["rows"]
        ),
        "errors": errors,
        "pass": not errors,
        "fixture_repo": world["repo"],
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        print("FAILED:AUD-0003-probe1 " + "; ".join(errors))
        return 1
    if not payload["limit_is_load_bearing"]:
        print("FAILED:AUD-0003-probe1 unlimited vs limited diff did not discriminate")
        return 1
    print(
        "fully-merged PR#10 missing=0 closed-without-merge PR#11 missing="
        + str(next(r["missing_files"] for r in census["rows"] if r["number"] == 11))
    )
    print("SUCCESS:AUD-0003-probe1 git diff <head> main --name-only limited to PR-touched files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
