#!/usr/bin/env python3
"""Probe 1: every live suite is GATED or UNGATED; ungated suites listed by path."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from join import (  # noqa: E402
    REPO,
    assert_every_suite_classified,
    assert_ungated_listed_by_path,
    live_census,
)

ART = REPO / "command-center" / "receipts" / "TST-0124.json"
SENTINEL = "SUCCESS:TST-0124"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0124-probe1 {msg}")
    return 1


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0124":
        return fail(f"unit_id {doc.get('unit_id')}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {st}")

    live = live_census()
    try:
        assert_every_suite_classified(live)
        assert_ungated_listed_by_path(live)
    except AssertionError as exc:
        return fail(str(exc))

    art_join = doc.get("join_table") or []
    live_join = [
        {"suite": r["suite"], "classification": r["classification"]}
        for r in live["join"]
    ]
    art_pairs = [
        {"suite": r.get("suite"), "classification": r.get("classification")}
        for r in art_join
    ]
    if art_pairs != live_join:
        return fail("receipt join_table drifted from live census")
    if int(doc.get("ungated_count", -1)) != live["ungated_count"]:
        return fail("ungated_count mismatch")
    listed = doc.get("ungated_suites") or []
    if listed != live["invariants"]["ungated_suites"]:
        return fail("ungated_suites list mismatch")
    if live["suite_count"] < 1:
        return fail("no suites enumerated")

    summary = {
        "probe": "probe1-classify-and-list",
        "unit_id": "TST-0124",
        "suite_count": live["suite_count"],
        "gated_count": live["gated_count"],
        "ungated_count": live["ungated_count"],
        "ungated_suites": live["invariants"]["ungated_suites"],
        "every_suite_classified": True,
        "workflow_dir_present": live["gates"]["workflow_dir_present"],
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        f"classified={live['suite_count']} gated={live['gated_count']} "
        f"ungated={live['ungated_count']}"
    )
    print("SUCCESS:TST-0124-probe1 every suite classified; ungated listed by path")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
