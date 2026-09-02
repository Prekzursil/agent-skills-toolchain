#!/usr/bin/env python3
"""Named probe 1: every production write is CORRECT or LOUD.

Planted silent controls at 270 and 400 must be classified SILENT_* so a
vacuous always-CORRECT detector cannot pass.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    SILENT,
    planted_rows,
    production_rows,
    run_matrix,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0065-probe1 {msg}")
    return 1


def main() -> int:
    matrix = run_matrix()
    prod = production_rows(matrix)
    planted = planted_rows(matrix)
    if len(prod) != 21:
        return fail(f"expected 7 writers x 3 lengths = 21 production rows, got {len(prod)}")
    if len(planted) != 9:
        return fail(f"expected 3 planted x 3 lengths = 9 rows, got {len(planted)}")

    silent_prod = [r for r in prod if r["verdict"] in SILENT]
    if silent_prod:
        return fail(
            "production writer silent: "
            + "; ".join(
                f"{r['writer']}@{r['length']}={r['verdict']}" for r in silent_prod
            )
        )
    for row in prod:
        if row["verdict"] not in ("CORRECT", "LOUD"):
            return fail(f"unclassified {row['writer']}@{row['length']}={row['verdict']}")

    long_silent = [
        r
        for r in planted
        if r["length"] in (270, 400) and r["verdict"] in SILENT
    ]
    if len(long_silent) < 6:
        return fail(
            "detector is not live: planted silent controls at 270/400 "
            f"classified SILENT_* only {len(long_silent)} times"
        )
    by_writer = {}
    for row in long_silent:
        by_writer.setdefault(row["writer"], set()).add(row["verdict"])
    required = {
        "planted.silent_truncate_path": "SILENT_TRUNCATE",
        "planted.swallow_oserror": "SILENT_SWALLOW",
        "planted.partial_write": "SILENT_PARTIAL",
    }
    for writer, verdict in required.items():
        if writer not in by_writer or verdict not in by_writer[writer]:
            return fail(f"planted control {writer} did not yield {verdict} at 270/400")

    payload = {
        "pass": True,
        "probe": "probe1-correct-or-loud",
        "unit_id": "TST-0065",
        "production_count": len(prod),
        "production_verdicts": sorted({r["verdict"] for r in prod}),
        "planted_long_silent": [
            {
                "writer": r["writer"],
                "length": r["length"],
                "verdict": r["verdict"],
                "on_disk_len": r["on_disk_len"],
            }
            for r in long_silent
        ],
        "host": matrix["host"],
        "path_max": matrix["path_max"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"production={len(prod)} all CORRECT-or-LOUD; "
        f"planted_silent_270_400={len(long_silent)}"
    )
    print("SUCCESS:TST-0065-probe1 long-path write is either correct or loud")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
