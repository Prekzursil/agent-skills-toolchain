#!/usr/bin/env python3
"""Probe 1: second requester's returned conflict object (signal a).

Also the both-states control: non-overlapping paths lease independently.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenarios import concurrent_conflict, independent_paths, overlapping_conflict  # noqa: E402

ART = REPO / "command-center/receipts/TST-0161.json"
SENTINEL = "SUCCESS:TST-0161"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def fail(msg: str) -> int:
    print(f"FAILED:TST-0161-probe1 {msg}")
    return 1


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0161-p1-") as tmp:
        root = Path(tmp)
        independent = independent_paths(root / "ind")
        conflict = overlapping_conflict(root / "cf")
        concurrent = concurrent_conflict(root / "cc")

    print(json.dumps(independent, sort_keys=True, default=str))
    print(json.dumps(conflict, sort_keys=True, default=str))
    print(
        json.dumps(
            {
                "ok": concurrent.get("ok"),
                "trials": concurrent.get("trials"),
                "double_grants": concurrent.get("double_grants"),
                "silent_or_untyped": concurrent.get("silent_or_untyped"),
                "sample_loser_conflict": concurrent.get("sample_loser_conflict"),
            },
            sort_keys=True,
            default=str,
        )
    )

    if not independent.get("ok") or not independent.get("both_granted"):
        return fail("non-overlapping paths did not both grant")
    second = conflict.get("second_conflict") or {}
    if not conflict.get("ok"):
        return fail("overlapping acquire did not surface an explicit conflict")
    if second.get("kind") != "LEASE_CONFLICT" or second.get("ok") is not False:
        return fail(f"second requester object is not LEASE_CONFLICT: {second}")
    if second.get("holder") != "sess-A" or second.get("requester") != "sess-B":
        return fail("conflict object missing holder/requester")
    if not concurrent.get("ok"):
        return fail(
            f"concurrent acquire double_grants={concurrent.get('double_grants')} "
            f"silent={concurrent.get('silent_or_untyped')}"
        )

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("live receipt absent")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if SENTINEL not in text:
        return fail("sentinel absent")
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        return fail(f"self-declared:{st}")
    report = doc.get("report") or {}
    live_conflict = ((report.get("conflict") or {}).get("second_conflict")) or {}
    if live_conflict.get("kind") != "LEASE_CONFLICT":
        return fail("receipt report.conflict.second_conflict.kind != LEASE_CONFLICT")
    if not (report.get("independent") or {}).get("both_granted"):
        return fail("receipt independent.both_granted is not true")

    print(
        json.dumps(
            {
                "probe": "probe1-conflict",
                "unit_id": "TST-0161",
                "pass": True,
                "conflict_kind": second.get("kind"),
                "holder": second.get("holder"),
                "requester": second.get("requester"),
                "both_granted_independent": True,
                "concurrent_trials": concurrent.get("trials"),
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:TST-0161-probe1 explicit LEASE_CONFLICT + independent grants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
