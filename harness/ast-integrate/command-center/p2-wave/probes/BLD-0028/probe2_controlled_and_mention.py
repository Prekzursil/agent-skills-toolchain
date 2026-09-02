#!/usr/bin/env python3
"""Probe 2: controlled zero is not flagged; quoted 'no findings' is not harvested."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import harvest as H  # noqa: E402
import reviewer as R  # noqa: E402

CTRL = "CTRL-ZERO"
MENTION = "DOC-MENTION"


def main() -> int:
    mixed = H.harvest_fixture_dir("mixed")
    print(
        json.dumps(
            {
                "probe": "probe2-controlled-and-mention",
                "zeros": mixed["zeros_harvested"],
                "uncontrolled_ids": mixed["uncontrolled_ids"],
                "controlled_ids": mixed["controlled_ids"],
                "mentioned_not_harvested": mixed["mentioned_not_harvested"],
            },
            sort_keys=True,
        )
    )
    ctrl = [row for row in mixed["inventory"] if row["producer"] == CTRL]
    if not ctrl:
        print("FAILED:BLD-0028-probe2 controlled zero was not harvested as a zero")
        return 1
    if any(row["verdict"] != "controlled" for row in ctrl):
        print("FAILED:BLD-0028-probe2 controlled zero was flagged UNCONTROLLED-ZERO")
        return 1
    if any(CTRL in i for i in mixed["uncontrolled_ids"]):
        print("FAILED:BLD-0028-probe2 controlled producer leaked into requeue set")
        return 1

    mention_rows = [
        row
        for row in mixed["inventory"]
        if row["producer"] == MENTION or "mention" in row["source"].lower()
    ]
    if mention_rows:
        print("FAILED:BLD-0028-probe2 quoted 'no findings' was harvested", mention_rows)
        return 1
    if mixed["mentioned_not_harvested"] < 1:
        print("FAILED:BLD-0028-probe2 mention control did not observe a quoted phrase")
        return 1

    files = sorted(p for p in (H.FIXTURES / "mixed").rglob("*") if p.is_file())
    review = R.grade_paths(files)
    if any(CTRL in i and "uncontrolled" in str(review["uncontrolled_ids"]) for i in review["uncontrolled_ids"]):
        print("FAILED:BLD-0028-probe2 reviewer flagged controlled zero")
        return 1
    if any(MENTION in i for i in review["uncontrolled_ids"] + review["controlled_ids"]):
        print("FAILED:BLD-0028-probe2 reviewer harvested the quoted mention")
        return 1
    print(
        f"controlled_not_flagged={len(ctrl)} mention_harvested=0 "
        f"mentions_seen={mixed['mentioned_not_harvested']}"
    )
    print("SUCCESS:BLD-0028-probe2 controlled zero kept; mention not harvested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
