#!/usr/bin/env python3
"""Probe 1: re-check controls (mutated snapshot → CHANGED; unchanged → UNCHANGED).

Also proves SOURCE-CHANGED is distinct from CLAIM-WAS-WRONG.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center" / "lib"))

from evidence_snapshot import run_local_recheck_controls  # noqa: E402
from evidence_snapshot.targets import ARTIFACT_REL, COMPLETION_SENTINEL  # noqa: E402

ART = REPO / ARTIFACT_REL
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _fail(msg: str) -> int:
    print(f"FAILED:RES-0004-probe1 {msg}")
    return 1


def main() -> int:
    controls = run_local_recheck_controls()
    print(json.dumps({"probe": "probe1-recheck-controls", "unit_id": "RES-0004", **controls}, sort_keys=True))
    if not controls.get("ok"):
        return _fail("local re-check controls did not all pass")

    by_id = {c["id"]: c for c in controls["cases"]}
    mut = by_id.get("mutated-stored-snapshot-byte") or {}
    unch = by_id.get("unchanged-source") or {}
    if mut.get("got") != "CHANGED" or not mut.get("ok"):
        return _fail("mutated stored snapshot byte did not report CHANGED")
    if unch.get("got") != "UNCHANGED" or not unch.get("ok"):
        return _fail("unchanged source reported CHANGED (false positive)")
    claim = by_id.get("claim-was-wrong-source-unchanged") or {}
    src = by_id.get("source-changed-not-claim-was-wrong") or {}
    if not claim.get("ok") or not src.get("ok"):
        return _fail("SOURCE-CHANGED vs CLAIM-WAS-WRONG distinction failed")

    if not ART.is_file() or ART.stat().st_size < 200:
        return _fail("receipt missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in NOT_DELIVERING:
        return _fail(f"self-declared {doc.get('state')}")
    if "SUCCESS:RES-0004" not in text or COMPLETION_SENTINEL not in text:
        return _fail("sentinel absent")
    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    for tid in (
        "recheck-mutated-snapshot-reports-CHANGED",
        "recheck-unchanged-source-reports-UNCHANGED",
        "source-changed-distinct-from-claim-was-wrong",
    ):
        if (tests.get(tid) or {}).get("result") != "PASS":
            return _fail(f"receipt test {tid} not PASS")
    print("SUCCESS:RES-0004-probe1 re-check controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
