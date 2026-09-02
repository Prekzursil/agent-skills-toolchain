#!/usr/bin/env python3
"""Probe 2: patch ONE call site to skip condition 8; the differential goes red.

The monitor judge is patched via evaluate(..., skip={8}). Only the
SYNTH-C08 row (isolate-fail of condition 8) may diverge: the patched
site PASSes that row; the other six still FAIL with failing-condition-id 8.
Every other row stays byte-identical across all seven sites.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from call_sites import SITE_IDS  # noqa: E402
from matrix import replay  # noqa: E402

PATCHED_SITE = "monitor"
SKIPPED_CONDITION = 8
DIVERGING_ROW = "SYNTH-C08"


def main() -> int:
    clean = replay()
    patched = replay(skip_by_site={PATCHED_SITE: {SKIPPED_CONDITION}})
    print(
        json.dumps(
            {
                "clean_hashes_agree": clean["hashes_agree"],
                "patched_site": PATCHED_SITE,
                "skipped_condition": SKIPPED_CONDITION,
                "patched_hashes_agree": patched["hashes_agree"],
                "patched_column_hashes": patched["column_hashes"],
                "disagreements": patched["disagreements"],
                "clean_column_hash": next(iter(set(clean["column_hashes"].values()))),
            },
            indent=2,
            sort_keys=True,
        )
    )
    if clean["hashes_agree"] is not True:
        print("FAILED:TST-0003-probe2 clean replay already disagrees")
        return 1
    if patched["hashes_agree"] is True or not patched["disagreements"]:
        print("FAILED:TST-0003-probe2 skip-C8 patch did not turn the differential red")
        return 1
    if len(patched["disagreements"]) != 1:
        print(
            f"FAILED:TST-0003-probe2 expected exactly 1 disagreeing row, "
            f"got {len(patched['disagreements'])}"
        )
        return 1
    d = patched["disagreements"][0]
    if d["row_id"] != DIVERGING_ROW:
        print(f"FAILED:TST-0003-probe2 diverged on {d['row_id']}, not {DIVERGING_ROW}")
        return 1
    by_site = d["failing_condition_by_site"]
    verdicts = d["verdict_by_site"]
    if verdicts.get(PATCHED_SITE) != "PASS" or by_site.get(PATCHED_SITE) is not None:
        print(f"FAILED:TST-0003-probe2 patched site did not PASS C8 isolate: {d}")
        return 1
    others = [s for s in SITE_IDS if s != PATCHED_SITE]
    for site in others:
        if verdicts.get(site) != "FAILED" or by_site.get(site) != SKIPPED_CONDITION:
            print(f"FAILED:TST-0003-probe2 site {site} did not stay FAIL/8: {d}")
            return 1
    patched_hash = patched["column_hashes"][PATCHED_SITE]
    other_hashes = {patched["column_hashes"][s] for s in others}
    if len(other_hashes) != 1 or patched_hash in other_hashes:
        print("FAILED:TST-0003-probe2 expected exactly one column hash to diverge")
        return 1
    print(
        f"patched={PATCHED_SITE} skip={SKIPPED_CONDITION} "
        f"diverging_row={DIVERGING_ROW} differential_red=True"
    )
    print("SUCCESS:TST-0003-probe2 skip-condition-8 patch turns the differential red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
