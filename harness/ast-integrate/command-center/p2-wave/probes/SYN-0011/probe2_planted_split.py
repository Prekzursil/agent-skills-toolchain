#!/usr/bin/env python3
"""Probe 2: planted split. Re-derive BEFORE reading the artifact conclusion.

Two candidates assert opposite readings of a file whose content is known.
The adjudicator must pick the side the file supports. Majority roster is
the wrong side on purpose; following the vote is a unit failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import adjudicate as A  # noqa: E402
import scenario as S  # noqa: E402

ART = S.REPO / S.OUT_REL
PLANTED = S.REPO / S.PLANTED_REL


def fail(msg: str) -> int:
    print(f"FAILED:SYN-0011-probe2 {msg}")
    return 1


def main() -> int:
    if not PLANTED.is_file():
        return fail("planted raw file missing")
    body = PLANTED.read_text(encoding="utf-8")
    if "DETECTOR_STATUS=BROKEN" not in body:
        return fail("planted file missing BROKEN token")
    if "DETECTOR_STATUS=HEALTHY" in body:
        return fail("planted file contains HEALTHY token")

    planted_div = next(d for d in S.divergences() if d["id"] == "D-PLANTED-DETECTOR")
    derived = A.settle(planted_div, S.REPO)
    vote_id = S.vote_pick(planted_div)

    if derived["winner_statement_id"] != "S-MIN-BROKEN":
        return fail(f"derived winner {derived['winner_statement_id']}")
    if derived["winner_statement_id"] == vote_id:
        return fail("derived winner is the vote pick")
    if not derived["minority_win"]:
        return fail("derived planted split is not a minority win")
    if derived["losing_disposition"] != "WRONG":
        return fail(f"derived disposition {derived['losing_disposition']}")

    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    recorded = next(
        (r for r in (doc.get("adjudications") or []) if r.get("id") == "D-PLANTED-DETECTOR"),
        None,
    )
    if recorded is None:
        return fail("artifact missing planted adjudication")
    if recorded.get("winner_statement_id") != derived["winner_statement_id"]:
        return fail("artifact winner != independently derived winner")
    if recorded.get("winner_statement_id") == vote_id:
        return fail("artifact followed the vote")
    if recorded.get("losing_disposition") != "WRONG":
        return fail("artifact planted disposition")

    anc = recorded.get("raw_anchor") or {}
    if str(anc.get("path") or "") != S.PLANTED_REL:
        return fail(f"planted anchor path {anc.get('path')}")
    line_no = int(anc.get("line") or 0)
    lines = body.splitlines()
    if line_no < 1 or line_no > len(lines):
        return fail("planted line oob")
    if "DETECTOR_STATUS=BROKEN" not in lines[line_no - 1]:
        return fail("planted cited line is not the BROKEN token")

    print(
        json.dumps(
            {
                "probe": "probe2-planted-split",
                "unit_id": "SYN-0011",
                "derived_winner": derived["winner_statement_id"],
                "vote_pick": vote_id,
                "file_supported_side": "S-MIN-BROKEN",
                "followed_vote": False,
                "served_conclusion_first": False,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:SYN-0011-probe2 planted split file-supported side")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
