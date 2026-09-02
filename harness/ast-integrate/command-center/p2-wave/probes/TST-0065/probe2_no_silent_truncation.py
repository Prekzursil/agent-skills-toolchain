#!/usr/bin/env python3
"""Named probe 2: no production writer silently truncates the path.

Records per-writer outcomes at 250, 270 and 400 characters. The planted
path-truncator and the Win32 MAX_PATH simulation prove the detector
distinguishes silent truncation from a loud ENAMETOOLONG.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from harness import (  # noqa: E402
    planted_rows,
    production_rows,
    run_matrix,
    win32_rows,
)


def fail(msg: str) -> int:
    print(f"FAILED:TST-0065-probe2 {msg}")
    return 1


def _rows(rows: list[dict], writer: str) -> list[dict]:
    return sorted((r for r in rows if r["writer"] == writer), key=lambda r: r["length"])


def main() -> int:
    matrix = run_matrix()
    prod = production_rows(matrix)
    planted = planted_rows(matrix)
    win32 = win32_rows(matrix)

    truncated = [r for r in prod if r["verdict"] == "SILENT_TRUNCATE"]
    if truncated:
        return fail(
            "production silent truncate: "
            + "; ".join(f"{r['writer']}@{r['length']}" for r in truncated)
        )

    truncator = _rows(planted, "planted.silent_truncate_path")
    if [r["length"] for r in truncator] != [250, 270, 400]:
        return fail(f"truncator lengths { [r['length'] for r in truncator] }")
    if truncator[0]["verdict"] != "CORRECT":
        return fail(
            f"truncator at 250 must be CORRECT (under MAX_PATH), got {truncator[0]['verdict']}"
        )
    for row in truncator[1:]:
        if row["verdict"] != "SILENT_TRUNCATE":
            return fail(
                f"truncator at {row['length']} must be SILENT_TRUNCATE, got {row['verdict']}"
            )
        if row["on_disk_len"] is None or row["on_disk_len"] > 260:
            return fail(
                f"truncator at {row['length']} did not land on a <=260 path: {row['on_disk_len']}"
            )
        if row["exception_text"]:
            return fail("truncator raised; that is LOUD, not silent")

    capped = _rows(win32, "win32.capped_no_prefix")
    extended = _rows(win32, "win32.extended_length_prefix")
    if capped[0]["verdict"] != "CORRECT":
        return fail(f"win32 capped at 250: {capped[0]['verdict']}")
    for row in capped[1:]:
        if row["verdict"] != "LOUD":
            return fail(f"win32 capped at {row['length']} must be LOUD, got {row['verdict']}")
        text = row["exception_text"] or ""
        if "MAX_PATH=260" not in text and "too long" not in text.lower():
            return fail(f"win32 capped exception missing MAX_PATH text: {text}")
    for row in extended:
        if row["verdict"] != "CORRECT":
            return fail(
                f"extended-length prefix at {row['length']} must be CORRECT, got {row['verdict']}"
            )
        if not row["used_extended_prefix"]:
            return fail(f"extended writer at {row['length']} did not record the prefix")

    per_writer = {}
    for row in prod + planted + win32:
        per_writer.setdefault(row["writer"], {})[str(row["length"])] = {
            "verdict": row["verdict"],
            "intended_len": row["intended_len"],
            "on_disk_len": row["on_disk_len"],
            "exception_text": row["exception_text"],
            "bytes_written": row["bytes_written"],
        }

    payload = {
        "pass": True,
        "probe": "probe2-no-silent-truncation",
        "unit_id": "TST-0065",
        "per_writer": per_writer,
        "production_silent_truncate": 0,
        "planted_truncator": [
            {"length": r["length"], "verdict": r["verdict"], "on_disk_len": r["on_disk_len"]}
            for r in truncator
        ],
        "win32_capped": [
            {"length": r["length"], "verdict": r["verdict"], "exception_text": r["exception_text"]}
            for r in capped
        ],
        "win32_extended": [
            {"length": r["length"], "verdict": r["verdict"]} for r in extended
        ],
        "host": matrix["host"],
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "production_silent_truncate=0 planted_truncator=CORRECT/SILENT_TRUNCATE/SILENT_TRUNCATE "
        "win32_capped=CORRECT/LOUD/LOUD win32_extended=CORRECT/CORRECT/CORRECT"
    )
    print("SUCCESS:TST-0065-probe2 no writer silently truncates the path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
