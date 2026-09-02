#!/usr/bin/env python3
"""Probe 2: negative control — overturn without marking, scan FIRE.

Both-states: unmarked overturn FIRE; marked overturn SILENT. The scan is
not a tautology that always returns fired=True. Starts from the tests,
not from an author summary (IMP-0351 reviewer_requirement).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(HERE))

from fixture import NEWER, OLDER, QUESTION, seeded_log  # noqa: E402
from tools.council.outcomes.lineage_export import (  # noqa: E402
    STATUS_LIVE,
    append_binding,
    commit_overturn,
    empty_log,
    sample_binding,
    scan_live_contradictions,
)


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0351-probe2 {msg}")
    return 1


def main() -> int:
    empty = empty_log()
    silent_empty = scan_live_contradictions(empty)
    print(f"empty_scan_fired={silent_empty.fired} live={silent_empty.live_count}")
    if silent_empty.fired:
        return fail("scan FIRED on an empty log (tautological detector)")

    same_q = sample_binding(
        "DEC-OTHER",
        "council-other",
        "Should telemetry leave the machine without owner opt-in?",
        "no",
    )
    unrelated = empty_log()
    append_binding(unrelated, OLDER)
    append_binding(unrelated, same_q)
    other_scan = scan_live_contradictions(unrelated)
    print(f"unrelated_scan_fired={other_scan.fired} live={other_scan.live_count}")
    if other_scan.fired:
        return fail("scan FIRED on two LIVE rows about different questions")

    unmarked = seeded_log()
    newer = commit_overturn(
        unmarked, NEWER, unmarked["entries"][0]["decision_id"], mark=False
    )
    older = unmarked["entries"][0]
    if older.get("status") != STATUS_LIVE:
        return fail("unmarked predecessor was altered")
    if older.get("superseded_by") is not None:
        return fail("unmarked predecessor acquired superseded_by")
    if newer.get("status") != STATUS_LIVE:
        return fail("unmarked successor is not LIVE")
    fired = scan_live_contradictions(unmarked)
    print(json.dumps({"unmarked_scan": fired.as_dict()}, sort_keys=True))
    if not fired.fired:
        return fail("contradiction scan stayed SILENT on unmarked overturn")
    ids = {(p.left_id, p.right_id) for p in fired.pairs} | {
        (p.right_id, p.left_id) for p in fired.pairs
    }
    if ("DEC-0351-A", "DEC-0351-B") not in ids:
        return fail(f"scan pairs did not list DEC-0351-A vs DEC-0351-B: {ids}")

    marked = seeded_log()
    commit_overturn(marked, NEWER, marked["entries"][0]["decision_id"], mark=True)
    quiet = scan_live_contradictions(marked)
    print(json.dumps({"marked_scan": quiet.as_dict()}, sort_keys=True))
    if quiet.fired:
        return fail("scan FIRED after marked overturn (both-states broken)")

    healed = seeded_log()
    commit_overturn(healed, NEWER, healed["entries"][0]["decision_id"], mark=False)
    from tools.council.outcomes.lineage_export import mark_predecessor

    mark_predecessor(healed, "DEC-0351-A", "DEC-0351-B")
    healed_scan = scan_live_contradictions(healed)
    print(f"healed_scan_fired={healed_scan.fired}")
    if healed_scan.fired:
        return fail("marking the older row after the fact did not silence the scan")

    print(
        json.dumps(
            {
                "question": QUESTION,
                "unmarked_fired": fired.fired,
                "marked_fired": quiet.fired,
                "empty_fired": silent_empty.fired,
                "pair_count": len(fired.pairs),
                "reviewer": "IMP-0351-probe2-contradiction-scan",
                "verdict": "PASS",
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0351-probe2 unmarked overturn contradiction scan FIRES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
