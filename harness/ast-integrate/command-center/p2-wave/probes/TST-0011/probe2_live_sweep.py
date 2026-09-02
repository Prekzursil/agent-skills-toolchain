#!/usr/bin/env python3
"""Named probe 2: live reverse sweep plus independent set-arithmetic recompute.

Requires the catalog artifact. Prints both Direction A and Direction B counts.
Disagreement between reverse_sweep and independent_path_sets is FAIL, not a
picked winner. Schema garbage must be rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from roundtrip import (  # noqa: E402
    discover_receipts,
    discover_rows,
    independent_path_sets,
    live_sweep,
    print_counts,
    reverse_sweep,
)
from schema_check import assert_not_vacuous, error_list  # noqa: E402

OUT = "command-center/receipts/TST-0011.json"
SENTINEL = "SUCCESS:TST-0011"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0011-probe2 {msg}")
    return 1


def extract_set_differences(doc: dict) -> dict | None:
    report = doc.get("report") if isinstance(doc.get("report"), dict) else {}
    if isinstance(doc.get("set_differences"), dict):
        return doc["set_differences"]
    if isinstance(report.get("set_differences"), dict):
        return report["set_differences"]
    obs = {
        o.get("name"): o.get("measured")
        for o in (report.get("observations") or [])
        if isinstance(o, dict)
    }
    if "orphan_row_count" in obs and "unregistered_file_count" in obs:
        return {
            "orphan_row_count": obs["orphan_row_count"],
            "unregistered_file_count": obs["unregistered_file_count"],
        }
    return None


def main() -> int:
    out = REPO / OUT
    if not out.is_file() or out.stat().st_size <= 0:
        return fail("artifact absent")
    try:
        text = out.read_text(encoding="utf-8")
        doc = json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return fail(f"unparseable:{type(exc).__name__}")
    if SENTINEL not in text:
        return fail("sentinel-absent")
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return fail(f"self-declared:{doc.get('state')}")

    try:
        assert_not_vacuous()
    except RuntimeError as exc:
        return fail(str(exc))
    errs = error_list(doc)
    if errs:
        print("FAILED:TST-0011-probe2 schema errors")
        for err in errs[:12]:
            print(" ", err)
        return 1

    diffs = extract_set_differences(doc)
    if not isinstance(diffs, dict):
        return fail("set_differences missing")
    if "orphan_row_count" not in diffs or "unregistered_file_count" not in diffs:
        return fail("set_differences missing a direction count")
    if not isinstance(diffs["orphan_row_count"], int) or not isinstance(
        diffs["unregistered_file_count"], int
    ):
        return fail("set_differences counts are not ints")
    if diffs.get("looks_consistent") is True and (
        "orphan_row_count" not in diffs or "unregistered_file_count" not in diffs
    ):
        return fail("looks_consistent without both direction counts")

    rows, errors = discover_rows(REPO)
    if errors:
        return fail(f"manifest-unreadable:{errors[:3]}")
    receipts = discover_receipts(REPO)
    signal1 = reverse_sweep(REPO, receipts, rows)
    signal2 = independent_path_sets(REPO, receipts, rows)
    live = live_sweep(REPO)
    print_counts("signal1", signal1)
    print_counts("signal2", signal2)
    print_counts("live", live)
    if signal1["orphan_row_count"] != signal2["orphan_row_count"]:
        return fail(
            f"signal-disagreement orphan {signal1['orphan_row_count']} "
            f"vs {signal2['orphan_row_count']}"
        )
    if signal1["unregistered_file_count"] != signal2["unregistered_file_count"]:
        return fail(
            f"signal-disagreement unregistered {signal1['unregistered_file_count']} "
            f"vs {signal2['unregistered_file_count']}"
        )
    if live["orphan_row_count"] != signal1["orphan_row_count"]:
        return fail("live_sweep drifted from reverse_sweep")
    if live["unregistered_file_count"] != signal1["unregistered_file_count"]:
        return fail("live_sweep drifted from reverse_sweep Direction B")

    recorded_tests = {t.get("id") for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for needed in (
        "test_close_writes_manifest_row",
        "test_orphan_manifest_row_detected",
        "test_unregistered_file_detected",
    ):
        if needed not in recorded_tests:
            return fail(f"tests missing {needed}")
        row = next(t for t in doc["tests"] if t.get("id") == needed)
        if row.get("result") != "PASS":
            return fail(f"{needed} result={row.get('result')}")

    print(
        json.dumps(
            {
                "pass": True,
                "probe": "probe2-live-sweep",
                "unit_id": "TST-0011",
                "orphan_row_count": live["orphan_row_count"],
                "unregistered_file_count": live["unregistered_file_count"],
                "receipt_count": live["receipt_count"],
                "manifest_row_count": live["manifest_row_count"],
                "manifest_file_count": live["manifest_file_count"],
                "emit_orphan_row_count": diffs["orphan_row_count"],
                "emit_unregistered_file_count": diffs["unregistered_file_count"],
            },
            sort_keys=True,
        )
    )
    print(
        "SUCCESS:TST-0011-probe2 live set differences "
        f"orphan_row_count={live['orphan_row_count']} "
        f"unregistered_file_count={live['unregistered_file_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
