#!/usr/bin/env python3
"""Probe 1: planted known incumbent is found; disjoint goal is empty-honest.

Detector control: a goal whose incumbent is planted in the catalog must
surface that incumbent as ADOPT. Both-states: a disjoint goal must not.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402


def main() -> int:
    present_out, present_receipt = S.scout(S.KNOWN_GOAL)
    absent_out, _absent_receipt = S.scout(S.ABSENT_GOAL)

    ranked = present_out.get("ranked") or []
    ids = [str(r.get("id")) for r in ranked]
    top = ranked[0] if ranked else {}
    found = S.INCUMBENT_ID in ids
    adopt = str(top.get("id")) == S.INCUMBENT_ID and top.get("verdict") == "ADOPT"
    sources_hit = sorted(
        {
            str(r.get("source_class"))
            for r in (present_out.get("ranked") or []) + (present_out.get("skipped") or [])
            if r.get("source_class")
        }
    )
    five_classes = set(S.SOURCE_CLASSES).issubset(set(sources_hit))

    absent_ids = [str(r.get("id")) for r in (absent_out.get("ranked") or [])]
    absent_honest = bool(absent_out.get("empty_honest")) and S.INCUMBENT_ID not in absent_ids

    doc = {
        "probe": "probe1-planted-incumbent",
        "unit_id": "IMP-0209",
        "incumbent_id": S.INCUMBENT_ID,
        "found": found,
        "top_id": top.get("id"),
        "top_verdict": top.get("verdict"),
        "adopt_incumbent": adopt,
        "ranked_ids": ids,
        "source_classes_hit": sources_hit,
        "five_source_classes": five_classes,
        "absent_empty_honest": absent_honest,
        "absent_ids": absent_ids,
        "both_states": found and adopt and absent_honest,
        "runtime_engine": present_receipt.get("engine"),
        "workflow_id": (present_receipt.get("workflow") or {}).get("id"),
        "pass": found and adopt and absent_honest and five_classes,
    }
    (HERE / "probe1-planted-incumbent.raw.json").write_text(
        json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: doc[k] for k in ("found", "adopt_incumbent", "absent_empty_honest", "five_source_classes", "top_id", "top_verdict")}, sort_keys=True))
    if not doc["pass"]:
        print(f"FAILED:IMP-0209-probe1 {doc}")
        return 1
    print(
        f"incumbent={S.INCUMBENT_ID} found={found} adopt={adopt} "
        f"absent_honest={absent_honest} sources={sources_hit}"
    )
    print("SUCCESS:IMP-0209-probe1 planted incumbent found; disjoint goal empty-honest")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
