#!/usr/bin/env python3
"""WFA-0110 probe 1: lineage matches decomposition; rollback smoke green per operator."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "workflow_foundry" / "tests"))

from test_fusion_lineage import run_rehearsal_suite  # noqa: E402

UNIT = "WFA-0110"
ART = REPO / "command-center" / "wfa" / "WFA-0110-fusion-lineage-and-rollback.json"
SENTINEL = "SUCCESS:WFA-0110"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_rehearsal_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:{UNIT}-probe1 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print(f"FAILED:{UNIT}-probe1 sentinel-absent")
            return 1
        claimed_ops = list(doc.get("operators") or [])
        live_ops = list(result.get("operators") or [])
        if claimed_ops and claimed_ops != live_ops:
            print(f"FAILED:{UNIT}-probe1 artifact operators {claimed_ops} != live {live_ops}")
            return 1
    if not result.get("pass"):
        print(f"FAILED:{UNIT}-probe1 rehearsal")
        return 1
    if not result.get("all_lineage_match") or not result.get("all_rollback_green"):
        print(f"FAILED:{UNIT}-probe1 lineage/rollback")
        return 1
    if int(result.get("n_fusions") or 0) != 7:
        print(f"FAILED:{UNIT}-probe1 expected 7 operator rehearsals")
        return 1
    print(
        f"n_fusions={result['n_fusions']} lineage_match={result['all_lineage_match']} "
        f"rollback_green={result['all_rollback_green']} "
        f"splice_refused={result['splice_mismatch_refused']}"
    )
    print(f"SUCCESS:{UNIT}-probe1 lineage matches decomposition; rollback smoke green x7")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
