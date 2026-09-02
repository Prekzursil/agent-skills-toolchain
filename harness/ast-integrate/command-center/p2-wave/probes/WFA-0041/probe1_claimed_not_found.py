#!/usr/bin/env python3
"""Probe 1: claimed benchmark with no run record → CLAIMED-NOT-FOUND.

Both-states: the CITABLE twin (same claim shape, locatable run record) stays
CITABLE. Probe 2 independently re-locates run records and forbids scores.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from classify import CLAIMED_NOT_FOUND, CITABLE, manufactured_score  # noqa: E402
from extract import load_fixture_corpus  # noqa: E402
from run_records import locate  # noqa: E402

ART = HERE.parents[3] / "command-center/wfa/WFA-0041-extract-benchmark-evidence.json"


def _by_id(rows: list[dict], cid: str) -> dict:
    for row in rows:
        if row.get("id") == cid:
            return row
    raise SystemExit(f"FAILED:WFA-0041-probe1 missing {cid}")


def main() -> int:
    corp = load_fixture_corpus()
    rows = corp["rows"]
    claimed = _by_id(rows, "cand.fixture.claimed-no-record")
    citable = _by_id(rows, "cand.fixture.citable")
    missing = locate(
        {"benchmark": "fixtures/run-records/MISSING-never-ran.json"},
        [HERE, HERE / "fixtures"],
    )
    present = locate(
        {"benchmark": "fixtures/run-records/citable-run.json"},
        [HERE, HERE / "fixtures"],
    )
    report = {
        "claimed_status": claimed.get("status"),
        "citable_status": citable.get("status"),
        "missing_found": missing["found"],
        "present_found": present["found"],
        "claimed_score": manufactured_score(claimed),
        "citable_score": manufactured_score(citable),
    }
    print(json.dumps(report, sort_keys=True))
    if claimed.get("status") != CLAIMED_NOT_FOUND:
        print("FAILED:WFA-0041-probe1 claimed twin was not CLAIMED-NOT-FOUND")
        return 1
    if missing["found"] is not False:
        print("FAILED:WFA-0041-probe1 missing run record was located")
        return 1
    if citable.get("status") != CITABLE:
        print("FAILED:WFA-0041-probe1 citable twin was not CITABLE")
        return 1
    if present["found"] is not True:
        print("FAILED:WFA-0041-probe1 planted run record not located")
        return 1
    if claimed.get("id") == citable.get("id"):
        print("FAILED:WFA-0041-probe1 twins collapsed")
        return 1
    if ART.is_file():
        doc = json.loads(ART.read_text(encoding="utf-8"))
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print("FAILED:WFA-0041-probe1 artifact self-declared", doc.get("state"))
            return 1
        if "SUCCESS:WFA-0041" not in ART.read_text(encoding="utf-8"):
            print("FAILED:WFA-0041-probe1 sentinel absent")
            return 1
    print("SUCCESS:WFA-0041-probe1 claimed-without-run-record downgraded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
