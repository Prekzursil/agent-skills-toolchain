#!/usr/bin/env python3
"""Probe 2: GitHub merged_at plus merge_commit_sha reachability from main.

The two signals must agree on merged-ness before any absence is called
deliberate. Also runs the catalog negative control: fully-merged PR is
silent, then a local delete of one of its files reports exactly one.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as C  # noqa: E402

OUT = HERE / "probe2-merge-agreement.json"


def main() -> int:
    world, census, control, live = C.run_world()
    errors = C.expected_rows_ok(census)
    if not control["pass"]:
        errors.append(
            "negative control failed good={0} bad={1}".format(
                control["good_state_missing"], control["bad_state_missing"]
            )
        )
    agreement_rows = []
    for row in census["rows"]:
        agreement_rows.append(
            {
                "pr": row["number"],
                "github_merged_at": row["github_merged_at"],
                "merge_commit_sha": row["merge_commit_sha"],
                "reachable_from_main": row["merge_commit_reachable_from_main"],
                "mergedness_agrees": row["mergedness_agrees"],
                "missing_files": row["missing_files"],
                "loss": row["loss"],
                "deliberate": row["deliberate"],
                "reason": row["reason"],
            }
        )
    payload = {
        "probe": "probe2-merge-agreement",
        "unit_id": C.UNIT,
        "instrument": (
            "GitHub API merged_at plus git merge-base --is-ancestor "
            "<merge_commit_sha> main"
        ),
        "github_records": world["github"],
        "agreement_rows": agreement_rows,
        "negative_control": control,
        "live_owner_census": live,
        "deliberate_requires_agreement": all(
            (not row["deliberate"]) or row["mergedness_agrees"]
            for row in census["rows"]
        ),
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        print("FAILED:AUD-0003-probe2 " + "; ".join(errors))
        return 1
    if not payload["deliberate_requires_agreement"]:
        print("FAILED:AUD-0003-probe2 a deliberate label was applied without agreement")
        return 1
    print(
        "control good_missing={0} bad_missing={1} pass={2}".format(
            control["good_state_missing"],
            control["bad_state_missing"],
            control["pass"],
        )
    )
    print(
        "SUCCESS:AUD-0003-probe2 merged_at vs merge_commit reachability; "
        "local-delete control is both-states"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
