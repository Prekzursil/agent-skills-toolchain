#!/usr/bin/env python3
"""Probe 2: suite-green claim blocked when a quarantined test is in the path.

Mechanically independent of probe 1: builds a fresh planted suite and
recomputes quarantine from raw outcomes, then asks suite_green_claim.

Both-states (known-present / FIRE first):
  FIRE  — claimed_green=True with planted.coin_flip in the path, even
          though that test's LAST run passed.
  SILENT — claimed_green=True with only planted.always_pass in the path.

A report that dropped quarantined rows would fail quarantine_still_in_report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
LIB = REPO / "command-center" / "lib"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(LIB))

from flake_quarantine.ledger import (  # noqa: E402
    FLAKY,
    independent_ratios,
    suite_green_claim,
)
from scenario import ALWAYS_FAIL, ALWAYS_PASS, COIN_FLIP, N, RARE_FLAKE, run_planted  # noqa: E402

UNIT = "TST-0032"
RAW = HERE / "probe2-green-claim-blocked.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0032-probe2 {msg}")
    return 1


def main() -> int:
    ledger = run_planted()
    recomputed = independent_ratios(ledger["rows"])
    if recomputed[COIN_FLIP]["class"] != FLAKY:
        return fail("independent recompute did not mark coin_flip FLAKY")
    if not recomputed[COIN_FLIP]["quarantined"]:
        return fail("independent recompute did not quarantine coin_flip")

    by_id = {r["id"]: r for r in ledger["rows"]}
    if not by_id[COIN_FLIP]["outcomes"][-1]:
        return fail("coin_flip last run failed; this control needs last-run PASS")

    # Known-present first: FIRE on quarantined-in-path.
    bad = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, COIN_FLIP],
        ledger=ledger,
    )
    if (not bad["blocked"]) or bad["allowed"]:
        return fail(f"quarantined-in-path did not block: {bad}")
    if COIN_FLIP not in bad["quarantined_in_path"]:
        return fail(f"coin_flip missing from quarantined_in_path: {bad}")
    if "quarantined-in-path" not in bad["blocked_by"]:
        return fail(f"blocked_by {bad['blocked_by']}")
    if not bad["quarantine_still_in_report"]:
        return fail("quarantined tests were hidden from the report")

    rare_path = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, RARE_FLAKE],
        ledger=ledger,
    )
    if not rare_path["blocked"] or RARE_FLAKE not in rare_path["quarantined_in_path"]:
        return fail(f"rare_flake in path did not block: {rare_path}")

    # SILENT on a path that contains only DETERMINISTIC passing tests.
    good = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS],
        ledger=ledger,
    )
    if good["blocked"] or not good["allowed"]:
        return fail(f"always_pass-only path was blocked: {good}")
    if good["quarantined_in_path"]:
        return fail(f"false quarantine on clean path: {good}")

    broken_path = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, ALWAYS_FAIL],
        ledger=ledger,
    )
    if not broken_path["blocked"] or "broken-in-path" not in broken_path["blocked_by"]:
        return fail(f"BROKEN in path did not block: {broken_path}")

    hidden = dict(ledger)
    hidden["rows"] = [r for r in ledger["rows"] if not r["quarantined"]]
    hidden_check = suite_green_claim(
        claimed_green=True,
        tests_in_path=[ALWAYS_PASS, COIN_FLIP],
        ledger=hidden,
    )
    if hidden_check["quarantine_still_in_report"]:
        return fail("hiding quarantined rows still reported quarantine_still_in_report")

    payload = {
        "broken_in_path_blocked": True,
        "clean_path_allowed": True,
        "coin_flip_last_run_passed": True,
        "hidden_rows_detected": True,
        "known_present_run_first": True,
        "n": N,
        "pass": True,
        "probe": "probe2-green-claim-blocked",
        "quarantined_in_path_blocked": True,
        "quarantine_still_in_report": True,
        "rare_flake_in_path_blocked": True,
        "sha": ledger["sha"],
        "unit_id": UNIT,
    }
    RAW.write_text(json.dumps(payload, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    print(
        "quarantined_in_path_blocked=True clean_path_allowed=True "
        "known_present_first=True last_run_passed=True"
    )
    print("SUCCESS:TST-0032-probe2 green claim blocked when quarantined test in path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
