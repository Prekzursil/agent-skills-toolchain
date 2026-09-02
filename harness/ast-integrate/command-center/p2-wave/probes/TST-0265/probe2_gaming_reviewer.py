#!/usr/bin/env python3
"""Probe 2: independent connected-components recount + gaming catch.

Uses BFS clustering, not the author's union-find. A number disagreement
blocks the unit. Reproduces the both-states control before sign-off.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import fixtures as F  # noqa: E402
import measure as M  # noqa: E402

ART = REPO / "command-center" / "receipts" / "TST-0265.json"
SENTINEL = "SUCCESS:TST-0265"


def main() -> int:
    U = M.U
    if not ART.is_file():
        print("FAILED:TST-0265-probe2 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))

    gamed = F.gamed_pad()
    distinct = F.distinct_ideas()
    bad_cc = U.unique_count_connected_components(gamed)
    good_cc = U.unique_count_connected_components(distinct)
    naive_bad = U.naive_unique(gamed)

    print("reviewer_algorithm=connected_components")
    print("executed_both_states=True")
    print(
        f"bad_cc_unique={bad_cc} naive_bad={naive_bad} "
        f"gate_ge_100={bad_cc >= U.UNIQUE_IDEAS_FLOOR}"
    )
    print(
        f"good_cc_unique={good_cc} "
        f"gate_ge_100={good_cc >= U.UNIQUE_IDEAS_FLOOR}"
    )

    if naive_bad < 100:
        print("FAILED:TST-0265-probe2 named failure not visible on naive count")
        return 1
    if bad_cc >= 100:
        print("FAILED:TST-0265-probe2 connected-components did not reject gamed corpus")
        return 1
    if good_cc != 100:
        print("FAILED:TST-0265-probe2 connected-components over-merged distinct corpus")
        return 1

    art_bad = int(doc["both_states"]["planted_bad"]["post_dedup_count"])
    art_good = int(doc["both_states"]["known_good"]["post_dedup_count"])
    if art_bad != bad_cc:
        print(f"FAILED:TST-0265-probe2 number disagreement bad art={art_bad} cc={bad_cc}")
        return 1
    if art_good != good_cc:
        print(f"FAILED:TST-0265-probe2 number disagreement good art={art_good} cc={good_cc}")
        return 1

    gaming = doc.get("gaming_simulation") or {}
    if int(gaming.get("post_dedup_count") or 999) >= 100:
        print("FAILED:TST-0265-probe2 gaming post-dedup still meets the floor")
        return 1
    if gaming.get("caught") is not True:
        print("FAILED:TST-0265-probe2 gaming_simulation.caught is not true")
        return 1

    # Independent recount of the gaming ledger texts.
    live = M.run()
    live_game = live["gaming_simulation"]
    cc_game = U.unique_count_connected_components(F.gamed_pad())
    if cc_game != live_game["post_dedup_count"]:
        print("FAILED:TST-0265-probe2 gaming author/reviewer disagree")
        return 1
    print(
        f"gaming_cc={cc_game} raw={live_game['raw_count']} "
        f"caught={live_game['caught']}"
    )

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:TST-0265-probe2 reviewer.independent is not true")
        return 1
    if rev.get("executed_both_states") is not True:
        print("FAILED:TST-0265-probe2 reviewer did not execute both-states")
        return 1
    if str(rev.get("verdict") or "").upper() != "PASS":
        print("FAILED:TST-0265-probe2 reviewer verdict is not PASS")
        return 1
    if int(rev.get("bad_unique") or -1) != bad_cc:
        print("FAILED:TST-0265-probe2 reviewer.bad_unique drift")
        return 1
    if int(rev.get("good_unique") or -1) != good_cc:
        print("FAILED:TST-0265-probe2 reviewer.good_unique drift")
        return 1

    if SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:TST-0265-probe2 sentinel absent")
        return 1
    print("SUCCESS:TST-0265-probe2 independent both-states recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
