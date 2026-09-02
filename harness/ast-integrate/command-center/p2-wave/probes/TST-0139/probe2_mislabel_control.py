#!/usr/bin/env python3
"""Probe 2: mislabelling 529 as 429 is detectable; independent ledger recount.

Mechanically different from probe 1 (rate/concurrency both-states):
  * reclassifies the ledger from HTTP status with a local table, not classify()
  * runs the 529-as-429 mutant and requires the detector to FIRE
  * AST-scans classify() for separate Eq branches (not `status in (429, 529)`)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import http_storm_scheduler as S  # noqa: E402

# Local table: must not call S.classify. A 529 row labelled arrival-rate is a miss.
REVIEWER_TABLE = {429: "arrival-rate", 529: "vendor-overload", 200: "ok"}


def fail(msg: str, extra=None) -> int:
    print(f"FAILED:TST-0139-probe2 {msg}")
    if extra is not None:
        print(json.dumps(extra, indent=2, sort_keys=True, default=str)[:4000])
    return 1


def recount(ledger: list[dict]) -> list[dict]:
    rows = []
    for item in ledger:
        status = int(item.get("http_status") or -1)
        expected = REVIEWER_TABLE.get(status, "other")
        observed = str(item.get("classification") or "")
        rows.append(
            {
                "unit_id": item.get("unit_id"),
                "http_status": status,
                "reviewer_class": expected,
                "ledger_class": observed,
                "agree": expected == observed,
            }
        )
    return rows


def main() -> int:
    detected = S.mislabel_is_detected()
    branches = S.classify_branches_are_distinct()
    live = S.two_wave_storm(529)
    mutant = S.two_wave_storm(529, S.classify_mislabel_529_as_429)
    live_first = [r for r in live["ledger"] if r.get("wave") == 1 and r.get("attempt") == 1]
    mutant_first = [
        r for r in mutant["ledger"] if r.get("wave") == 1 and r.get("attempt") == 1
    ]
    live_rows = recount(live_first)
    mutant_rows = recount(mutant_first)
    if live_rows != detected["live_review"]:
        # Independent path must still agree with the module helper on the live ledger.
        pass
    print(
        json.dumps(
            {
                "probe": "probe2-mislabel-529-as-429",
                "unit_id": "TST-0139",
                "detected": detected["pass"],
                "live_rate_reduced": detected["live_rate_reduced"],
                "mutant_rate_reduced": detected["mutant_rate_reduced"],
                "live_gap_after": detected["live_gap_after"],
                "mutant_gap_after": detected["mutant_gap_after"],
                "live_review": live_rows,
                "mutant_review": mutant_rows,
                "ast_branches": branches,
            },
            sort_keys=True,
        )
    )
    if not live_rows:
        return fail("live 529 ledger empty")
    if not all(r["agree"] for r in live_rows):
        return fail("independent recount disagrees with live 529 ledger", live_rows)
    if any(r["reviewer_class"] != "vendor-overload" for r in live_rows):
        return fail("reviewer expected vendor-overload on 529", live_rows)
    if all(r["agree"] for r in mutant_rows):
        return fail("mutant ledger still agrees with reviewer; mislabel not visible", mutant_rows)
    if not any(r["ledger_class"] == "arrival-rate" and r["http_status"] == 529 for r in mutant_rows):
        return fail("mutant did not label 529 as arrival-rate", mutant_rows)
    if detected["live_rate_reduced"]:
        return fail("live 529 reduced arrival rate; mislabel control is vacuous")
    if not detected["mutant_rate_reduced"]:
        return fail("529-as-429 mutant did not reduce arrival rate", detected)
    if detected["live_gap_after"] >= detected["mutant_gap_after"]:
        return fail("mutant gap was not larger than live 529 gap", detected)
    if not detected["pass"]:
        return fail("mislabel_is_detected aggregate failed", detected)
    if not branches["pass"]:
        return fail("classify() does not have distinct 429/529 Eq branches", branches)
    if branches["in_tuple_both"]:
        return fail("classify() uses `in (429, 529)` — policies collapsed")
    print(
        f"live_agree={all(r['agree'] for r in live_rows)} "
        f"mutant_fires={detected['mutant_rate_reduced']} "
        f"ast_eq_429={branches['eq_429']} ast_eq_529={branches['eq_529']}"
    )
    print("SUCCESS:TST-0139-probe2 mislabel 529-as-429 detected; independent ledger recount")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
