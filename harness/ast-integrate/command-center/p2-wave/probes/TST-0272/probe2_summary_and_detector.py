#!/usr/bin/env python3
"""Named probe 2 (reviewer): summary-path leak vs honest withhold.

Starts from the search contract, not from an author summary. Forces a
moderator summary of B-WITHHELD. Honest delivery keeps the summary out of
seat-a's readable set (zero hits). The naive summary that copies the
withheld body is found by the same search (leakage attempt reproduced).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.partition import (  # noqa: E402
    HONEST,
    NAIVE_PARAPHRASE,
    NAIVE_SCRATCHPAD,
    NAIVE_SUMMARY,
    NAIVE_TOOL,
    SEAT_A,
    WITHHELD_ID,
    require_real_search,
    run_fixture,
    search_seat,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0272-probe2 {msg}")
    return 1


def main() -> int:
    honest = run_fixture(HONEST)
    token = honest.withheld_canary
    summary_path = f"derived/moderator_summary/{WITHHELD_ID}"
    summary = next(a for a in honest.artifacts if a.path == summary_path)
    if token not in summary.body:
        return fail("forced moderator summary does not contain the withheld token")
    if SEAT_A in summary.visible_to:
        return fail("honest summary is readable by the partitioned seat")

    honest_report = search_seat(SEAT_A, token, honest.artifacts)
    try:
        require_real_search(honest_report)
    except Exception as exc:  # noqa: BLE001
        return fail(f"honest search not attributable: {exc}")
    if honest_report.hit_count != 0:
        return fail(f"honest forced-summary leaked: {honest_report.as_dict()}")
    if summary_path in honest_report.paths_searched:
        return fail("honest summary was in the partitioned seat's searchable set")

    naive = run_fixture(NAIVE_SUMMARY)
    naive_report = search_seat(SEAT_A, naive.withheld_canary, naive.artifacts)
    try:
        require_real_search(naive_report)
    except Exception as exc:  # noqa: BLE001
        return fail(f"naive-summary search not attributable: {exc}")
    if naive_report.hit_count < 1:
        return fail("naive summary was not found; leakage attempt not reproduced")
    if summary_path not in {h.path for h in naive_report.hits}:
        return fail(f"naive hits missed summary path: {naive_report.as_dict()}")

    extra = {}
    for mode in (NAIVE_SCRATCHPAD, NAIVE_TOOL, NAIVE_PARAPHRASE):
        rnd = run_fixture(mode)
        rep = search_seat(SEAT_A, rnd.withheld_canary, rnd.artifacts)
        require_real_search(rep)
        extra[mode] = {"hit_count": rep.hit_count, "hit_paths": [h.path for h in rep.hits]}
        if rep.hit_count < 1:
            return fail(f"{mode} did not reproduce a leak")

    paraphrase = next(
        a
        for a in honest.artifacts
        if a.path == f"derived/moderator_paraphrase/{WITHHELD_ID}"
    )
    if token in paraphrase.body:
        return fail("honest public paraphrase still carries the withheld token")

    payload = {
        "probe": "probe2-summary-and-detector",
        "unit_id": "TST-0272",
        "independent": True,
        "starts_from_search_contract": True,
        "canary_token": token,
        "honest_paths_searched": list(honest_report.paths_searched),
        "honest_hit_count": honest_report.hit_count,
        "naive_summary_hit_count": naive_report.hit_count,
        "naive_summary_hit_paths": [h.path for h in naive_report.hits],
        "forced_moderator_summary": True,
        "other_naive_carriers": extra,
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True, indent=1))
    print(
        f"canary={token} honest_hits=0 naive_summary_hits={naive_report.hit_count} "
        f"searched={len(honest_report.paths_searched)}"
    )
    print(
        "SUCCESS:TST-0272-probe2 honest forced-summary withholds; "
        "naive summary leak reproduced"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
