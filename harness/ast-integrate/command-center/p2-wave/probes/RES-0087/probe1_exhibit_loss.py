#!/usr/bin/env python3
"""Probe 1: exhibit two-level loss. Label-only meta ≠ flattened member majority."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from nested import assert_example, flattened_member_majority, label_only_fanin  # noqa: E402

ART = (
    HERE.parents[3]
    / "command-center"
    / "research"
    / "RES-0087.json"
)


def main() -> int:
    report = assert_example()
    labels = label_only_fanin()
    flat = flattened_member_majority()
    if labels["conclusion"] == flat["conclusion"]:
        print("FAILED:RES-0087-probe1 no loss: meta matches flattened")
        return 1
    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        needles = (
            "SUCCESS:RES-0087 in the receipt AND a worked two-level example showing the loss plus the minimal forwarding set that fixes it",
            '"n_complete": 5',
            '"n_blocked": 4',
            "label-only-fan-in",
        )
        missing = [n for n in needles if n not in text]
        if missing:
            print("FAILED:RES-0087-probe1 artifact missing", missing)
            return 1
    out = {
        "probe": "probe1-exhibit-loss",
        "unit_id": "RES-0087",
        "pass": True,
        "label_only": labels["conclusion"],
        "flattened": flat["conclusion"],
        "child_labels": labels["child_labels"],
        "flat_counts": {
            "n_complete": flat["n_complete"],
            "n_blocked": flat["n_blocked"],
        },
        "lost_dissent": report["lost_dissent_member_ids"],
        "lost_unique_evidence": report["lost_unique_evidence_ids"],
        "meta_differs_from_full_evidence": True,
    }
    print(json.dumps(out, sort_keys=True))
    print("SUCCESS:RES-0087-probe1 two-level loss exhibited")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
