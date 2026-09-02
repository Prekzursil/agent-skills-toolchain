#!/usr/bin/env python3
"""Probe 2 / detector control: skip invalidation; warm must resolve the WRONG version.

This is the reviewer surface: re-run the known-broken fixture and confirm the
probe fires. A reviewer who only re-reads the report has verified nothing.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0044-rollback-cache-coherence.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})
SENTINEL = (
    "SUCCESS:CNF-0044 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and the skip-invalidation "
    "control produced a resolution mismatch, establishing the probe can see "
    "the defect. Any other terminal state is FAILED:CNF-0044 <classification> "
    "with the diagnostic tail attached."
)


def main() -> int:
    run = S.skip_inv()
    printable = {k: run[k] for k in sorted(run) if k != "pass"}
    print(json.dumps(printable, sort_keys=True, default=str)[:4000])
    if not run.get("pass") or run.get("resolution_mismatch") is not True:
        print("FAILED:CNF-0044-probe2 skip-invalidation did not produce a resolution mismatch")
        return 1
    warm_v = (run.get("warm") or {}).get("version")
    cold_v = (run.get("cold") or {}).get("version")
    print(
        f"skip_inv warm={warm_v} (wrong) cold={cold_v} (restored) "
        f"mismatch={run.get('resolution_mismatch')}"
    )
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if str(doc.get("state") or "").upper() in NOT_DELIVERING:
            print(f"FAILED:CNF-0044-probe2 self-declared {doc.get('state')}")
            return 1
        if SENTINEL not in text:
            print("FAILED:CNF-0044-probe2 catalog sentinel absent from artifact")
            return 1
        ctrl = doc.get("detector_control") or {}
        if ctrl.get("fired") is not True:
            print("FAILED:CNF-0044-probe2 artifact detector_control.fired is not true")
            return 1
        skip = doc.get("skip_invalidation_control") or {}
        if skip.get("resolution_mismatch") is not True:
            print("FAILED:CNF-0044-probe2 artifact skip-invalidation mismatch not recorded")
            return 1
        if skip.get("warm_resolved_version") == skip.get("cold_resolved_version"):
            print("FAILED:CNF-0044-probe2 artifact skip-invalidation versions unexpectedly match")
            return 1
    print("SUCCESS:CNF-0044-probe2 skip-invalidation detector control fired")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
