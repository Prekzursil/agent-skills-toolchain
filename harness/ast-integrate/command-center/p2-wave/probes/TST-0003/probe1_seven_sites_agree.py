#!/usr/bin/env python3
"""Probe 1: all seven call sites emit byte-identical verdicts on every corpus row.

Equality is proven by SHA-256 column hashes, not by eyeballing the table.
Also asserts the seven judges bind the same evaluate object.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from call_sites import SITE_IDS  # noqa: E402
from corpus import all_rows  # noqa: E402
from matrix import replay  # noqa: E402
from reducer import evaluate  # noqa: E402


def main() -> int:
    rows = all_rows()
    if len(rows) != 13:
        print(f"FAILED:TST-0003-probe1 expected 13 corpus rows, got {len(rows)}")
        return 1
    expected_fail = list(range(1, 13))
    got_fail = []
    for row in rows[:-1]:
        v = evaluate(row)
        cid = v.get("failing-condition-id")
        if v.get("verdict") != "FAILED" or not isinstance(cid, int):
            print(f"FAILED:TST-0003-probe1 isolate row {row.get('unit_id')} -> {v}")
            return 1
        got_fail.append(cid)
    if got_fail != expected_fail:
        print(f"FAILED:TST-0003-probe1 isolate ids {got_fail} != {expected_fail}")
        return 1
    pass_v = evaluate(rows[-1])
    if pass_v.get("verdict") != "PASS" or pass_v.get("failing-condition-id") is not None:
        print(f"FAILED:TST-0003-probe1 PASS row -> {pass_v}")
        return 1
    report = replay()
    print(
        json.dumps(
            {
                "n_rows": report["n_rows"],
                "n_sites": report["n_sites"],
                "site_ids": report["site_ids"],
                "row_ids": report["row_ids"],
                "column_hashes": report["column_hashes"],
                "hashes_agree": report["hashes_agree"],
                "distinct_column_hash_count": report["distinct_column_hash_count"],
                "disagreements": report["disagreements"],
                "identity_ok": report["identity_ok"],
                "evaluate_is_shared": report["evaluate_is_shared"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if len(SITE_IDS) != 7:
        print(f"FAILED:TST-0003-probe1 expected 7 sites, got {len(SITE_IDS)}")
        return 1
    if report["identity_ok"] is not True or report["evaluate_is_shared"] is not True:
        print("FAILED:TST-0003-probe1 call sites do not bind the shared evaluate object")
        return 1
    if report["hashes_agree"] is not True or report["disagreements"]:
        print("FAILED:TST-0003-probe1 column hashes disagree")
        return 1
    unique = set(report["column_hashes"].values())
    if len(unique) != 1:
        print(f"FAILED:TST-0003-probe1 {len(unique)} distinct column hashes")
        return 1
    print(
        f"sites={len(SITE_IDS)} rows={report['n_rows']} "
        f"column_sha256={next(iter(unique))} agree=True identity_ok=True"
    )
    print("SUCCESS:TST-0003-probe1 seven call sites agree per row by column hash")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
