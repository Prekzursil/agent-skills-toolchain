#!/usr/bin/env python3
"""Probe 2: independent recount. Re-tabulate fixtures without tally_author.

A disagreement in any count, naive fraction, or blocking_code blocks the unit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import consensus as C  # noqa: E402

OUT = REPO / "command-center/design/council/CNL-0069-what-number-is-0-95-consensus.md"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0069-probe2 {msg}")
    return 1


def main() -> int:
    fx = C.fixtures()
    mismatches = []
    rows = []
    for fid, fixture in fx.items():
        author = C.tally_author(fixture)
        reviewer = C.tally_reviewer(fixture)
        ok, why = C.counts_match(author, reviewer)
        print(
            f"recount id={fid} author={author['naive_fraction']} "
            f"reviewer={reviewer['naive_fraction']} "
            f"author_ok={author['stopping_ok']} reviewer_ok={reviewer['stopping_ok']} "
            f"author_codes={author['blocking_codes']} "
            f"reviewer_codes={reviewer['blocking_codes']} match={ok}"
        )
        if not ok:
            mismatches.append(f"{fid}:{why}")
        rows.append((fid, author, reviewer, ok))

    if mismatches:
        return fail("recount disagreement " + " | ".join(mismatches))

    pair = (
        C.tally_reviewer(fx["naive-095-silent"]),
        C.tally_reviewer(fx["naive-095-reasoned-dissent"]),
    )
    if pair[0]["naive_fraction"] != pair[1]["naive_fraction"]:
        return fail("reviewer naive fractions diverged; they must both be 19/20")
    if pair[0]["naive_fraction"] != "19/20":
        return fail(f"reviewer naive {pair[0]['naive_fraction']} != 19/20")
    if pair[0]["blocking_codes"] == pair[1]["blocking_codes"]:
        return fail("reviewer could not distinguish silent vs reasoned dissent")

    doc = json.loads(OUT.read_text(encoding="utf-8"))
    recorded = {
        row["id"]: row
        for row in (doc.get("fixture_results") or [])
        if isinstance(row, dict)
    }
    for fid, _author, reviewer, _ok in rows:
        rec = recorded.get(fid)
        if not isinstance(rec, dict):
            return fail(f"artifact missing fixture_results[{fid}]")
        ok, why = C.counts_match(reviewer, rec)
        if not ok:
            return fail(f"artifact disagrees with reviewer recount {fid}: {why}")

    method = str((doc.get("reviewer") or {}).get("method") or "")
    if "recount" not in method.lower() and "re-tabulat" not in method.lower():
        return fail("artifact reviewer.method does not claim mechanical recount")
    if (doc.get("reviewer") or {}).get("independent") is not True:
        return fail("artifact reviewer.independent is not true")

    print("reviewer_independent=True disagreements=0")
    print("SUCCESS:CNL-0069-probe2 independent recount agrees")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
