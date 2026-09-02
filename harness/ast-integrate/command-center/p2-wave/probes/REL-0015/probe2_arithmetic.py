#!/usr/bin/env python3
"""Named probe 2: live arithmetic, isolation, both-states, observed build strings."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from matrix import run_matrix  # noqa: E402
from renderer import arithmetic_from_doc  # noqa: E402
from smoke import IsolationError, OWNER_HOME, assert_isolated  # noqa: E402

ART = REPO / "command-center/receipts/REL-0015.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 2048:
        print("FAILED:REL-0015-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "REL-0015" or "SUCCESS:REL-0015" not in json.dumps(doc):
        print("FAILED:REL-0015-probe2 sentinel/unit_id")
        return 1

    live = run_matrix()
    arith = live["rendered"]["arithmetic"]
    print(json.dumps({"arithmetic": arith, "isolation": live["isolation"], "both": {k: live["both_states"].get(k) for k in ("discriminates", "listing_passes_both_states", "good_status", "bad_status")}}, indent=2))

    if not arith["holds"]:
        print("FAILED:REL-0015-probe2 arithmetic identity broken")
        return 1
    if arith["published_cells"] != len(live["specs"]):
        print("FAILED:REL-0015-probe2 published != declared cells")
        return 1
    if arith["executed_receipts"] != len(live["executed_receipts"]):
        print("FAILED:REL-0015-probe2 receipt count mismatch")
        return 1
    if arith["not_checked_entries"] != len(live["not_checked_entries"]):
        print("FAILED:REL-0015-probe2 NOT-CHECKED count mismatch")
        return 1
    if arith["executed_receipts"] < 1:
        print("FAILED:REL-0015-probe2 zero executed cells")
        return 1

    for rec in live["executed_receipts"]:
        obs = rec.get("observed_client_build_string") or ""
        if len(obs) < 8:
            print("FAILED:REL-0015-probe2 executed receipt missing observed build string")
            print(json.dumps(rec, indent=2)[:1500])
            return 1

    art_arith = arithmetic_from_doc(doc)
    if (
        art_arith.get("published_cells") != arith["published_cells"]
        or art_arith.get("executed_receipts") != arith["executed_receipts"]
        or art_arith.get("not_checked_entries") != arith["not_checked_entries"]
        or art_arith.get("holds") is not True
    ):
        print("FAILED:REL-0015-probe2 artifact arithmetic disagrees with live re-run")
        print("artifact", art_arith)
        print("live", arith)
        return 1

    refused = False
    try:
        assert_isolated(OWNER_HOME)
    except IsolationError:
        refused = True
    if not refused or not live["isolation"].get("refused"):
        print("FAILED:REL-0015-probe2 isolation did not refuse owner home")
        return 1

    both = live["both_states"]
    if not both.get("discriminates"):
        print("FAILED:REL-0015-probe2 both-states does not discriminate")
        return 1
    if not both.get("listing_passes_both_states"):
        print("FAILED:REL-0015-probe2 listing check does not pass in both states (cannot disqualify it)")
        return 1
    if both.get("good_status") != "PASS" or both.get("bad_status") != "FAIL":
        print("FAILED:REL-0015-probe2 expected good=PASS bad=FAIL")
        return 1

    # Neighbour inference: a NOT-CHECKED cell must carry its own reason, not a copy of a PASS neighbour.
    pass_ids = {c["cell_id"] for c in live["rendered"]["published"] if c["status"] == "PASS"}
    for skip in live["not_checked_entries"]:
        reason = skip.get("reason") or ""
        if not reason or "inferred" in reason.lower() and "not inferred" not in reason.lower():
            print("FAILED:REL-0015-probe2 skip reason missing or inferred")
            print(skip)
            return 1
        if any(pid in reason for pid in pass_ids):
            print("FAILED:REL-0015-probe2 skip reason cites a PASS neighbour")
            print(skip)
            return 1

    print("SUCCESS:REL-0015-probe2 arithmetic isolation both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
