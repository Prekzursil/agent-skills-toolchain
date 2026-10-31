#!/usr/bin/env python3
"""WFA-0110 probe 2: both-states on anchors, credits, licence, id-only rollback."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "workflow_foundry" / "tests"))

from test_fusion_lineage import run_both_states_suite  # noqa: E402

UNIT = "WFA-0110"
ART = REPO / "command-center" / "wfa" / "WFA-0110-fusion-lineage-and-rollback.json"
SENTINEL = "SUCCESS:WFA-0110"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    result = run_both_states_suite()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        st = str(doc.get("state") or "").upper()
        if st in NOT_DELIVERING:
            print(f"FAILED:{UNIT}-probe2 self-declared {st}")
            return 1
        if SENTINEL not in text:
            print(f"FAILED:{UNIT}-probe2 sentinel-absent")
            return 1
    both = result.get("both_states") or {}
    if not result.get("pass"):
        print(f"FAILED:{UNIT}-probe2 both-states")
        return 1
    if not (
        both.get("good_silent")
        and both.get("anchor_strip_fires")
        and both.get("credit_drop_fires")
        and both.get("licence_loosen_fires")
        and both.get("id_only_rollback_fires")
    ):
        print(f"FAILED:{UNIT}-probe2 planted controls")
        return 1
    print(
        f"good_silent={both['good_silent']} "
        f"anchor_strip={both['anchor_strip_fires']} "
        f"credit_drop={both['credit_drop_fires']} "
        f"licence_loosen={both['licence_loosen_fires']} "
        f"id_only={both['id_only_rollback_fires']}"
    )
    print(f"SUCCESS:{UNIT}-probe2 both-states: honest silent, four plants fire")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
