#!/usr/bin/env python3
"""Named probe 1: end-to-end restoration rehearsal plus both-states gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engine as E  # noqa: E402


def main() -> int:
    result = E.process_scenario()
    if not E.gate_holds(result):
        print("FAILED:WFA-0076-probe1 gate does not hold")
        print(json.dumps(result["gate"], sort_keys=True))
        print(json.dumps(result["rehearsal"], sort_keys=True))
        return 1
    rehearsal = result["rehearsal"]
    if not rehearsal.get("ok") or not rehearsal.get("end_to_end"):
        print("FAILED:WFA-0076-probe1 restoration rehearsal did not complete")
        return 1
    if rehearsal.get("bytes", 0) < 1:
        print("FAILED:WFA-0076-probe1 restoration wrote zero bytes")
        return 1
    squash = result["squash"]
    if squash["recorded"] or not squash["squash_merge_rejected"]:
        print("FAILED:WFA-0076-probe1 squash-merge claim was recorded")
        return 1
    if not squash["naive_ancestry_would_accept"]:
        print("FAILED:WFA-0076-probe1 naive ancestry control did not fire")
        return 1
    happy_retire = next(r for r in result["rows"] if r["role"] == "happy-retire")
    happy_reject = next(r for r in result["rows"] if r["role"] == "happy-reject")
    missing = next(r for r in result["rows"] if r["role"] == "missing-negative")
    mismatch = next(r for r in result["rows"] if r["role"] == "mismatch-negative")
    if not happy_retire["recorded"] or not happy_reject["recorded"]:
        print("FAILED:WFA-0076-probe1 happy-path terminal rows not recorded")
        return 1
    if missing["recorded"] or mismatch["recorded"]:
        print("FAILED:WFA-0076-probe1 negative rows were recorded")
        return 1
    payload = {
        "probe": "probe1-restoration-rehearsal",
        "unit_id": "WFA-0076",
        "pass": True,
        "rehearsal_ok": True,
        "rehearsal_bytes": rehearsal["bytes"],
        "rehearsal_record_id": rehearsal["record_id"],
        "recorded_ids": result["recorded_ids"],
        "refused_ids": result["refused_ids"],
        "squash_refused": True,
        "naive_would_accept_squash": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"rehearsal_ok=True record={rehearsal['record_id']} "
        f"bytes={rehearsal['bytes']} recorded={result['recorded_count']} "
        f"refused={result['refused_count']}"
    )
    print("SUCCESS:WFA-0076-probe1 restoration rehearsal both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
