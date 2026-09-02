#!/usr/bin/env python3
"""Probe 1: planted canary is caught; use-vs-mention quotes/rejects are silent."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import detect as D  # noqa: E402

FIX = HERE / "fixtures"
PLANT = FIX / "plant-canary.md"
QUOTE = FIX / "mention-quote.md"
REJECT = FIX / "mention-rejected.md"


def hits_for(path: Path, did: str = "DEC-PR-ONLY") -> list[dict]:
    return [h for h in D.scan_path(path, REPO, [did])]


def main() -> int:
    if not PLANT.is_file() or not QUOTE.is_file() or not REJECT.is_file():
        print("FAILED:BLD-0014-probe1 fixture missing")
        return 1

    plant = hits_for(PLANT)
    contra = [h for h in plant if h["classification"] == "CONTRADICTS"]
    print(
        json.dumps(
            {
                "probe": "probe1-planted-controls",
                "unit_id": "BLD-0014",
                "plant_hits": plant,
                "quote_hits": hits_for(QUOTE),
                "reject_hits": hits_for(REJECT),
            },
            indent=2,
        )
    )

    if not contra:
        print("FAILED:BLD-0014-probe1 planted canary not caught")
        return 1
    # Both sides: decision is PR-ONLY (catalog), opposite is the plant line.
    if not any("PRIVATE CANARY" in h["snippet"] or "canary channel" in h["snippet"].lower() for h in contra):
        print("FAILED:BLD-0014-probe1 plant snippet missing opposite assertion")
        return 1
    if contra[0]["line"] < 1 or not contra[0]["path"].endswith("plant-canary.md"):
        print("FAILED:BLD-0014-probe1 plant anchor malformed")
        return 1

    for label, path in (("quote", QUOTE), ("rejected", REJECT)):
        bad = [h for h in hits_for(path) if h["classification"] == "CONTRADICTS"]
        if bad:
            print(f"FAILED:BLD-0014-probe1 {label} use-vs-mention flagged: {bad}")
            return 1

    print("SUCCESS:BLD-0014-probe1 planted canary caught; quote/reject silent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
