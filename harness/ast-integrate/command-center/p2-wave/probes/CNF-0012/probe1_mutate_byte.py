#!/usr/bin/env python3
"""Probe 1: mutate-one-byte flips exactly one receipt; untouched flips none.

Re-derives the detector control from the engine. Does not trust the artifact's
conclusion until the live control matches the recorded flipped counts.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import mutate_one_byte_control, untouched_control  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0012-freshness-decay.json"
SENTINEL = "SUCCESS:CNF-0012 emitted only when the artifact at output_path exists"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNF-0012-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "CNF-0012":
        print("FAILED:CNF-0012-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNF-0012-probe1 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in text:
        print("FAILED:CNF-0012-probe1 sentinel-absent")
        return 1

    mutate = mutate_one_byte_control()
    untouched = untouched_control()
    print(f"mutate_pass={mutate['pass']} flipped={mutate['flipped_count']} ids={mutate['flipped_ids']}")
    print(f"untouched_pass={untouched['pass']} flipped={untouched['flipped_count']}")
    if not mutate["pass"] or mutate["flipped_count"] != 1:
        print("FAILED:CNF-0012-probe1 mutate-one-byte did not flip exactly one receipt")
        return 1
    if not untouched["pass"] or untouched["flipped_count"] != 0:
        print("FAILED:CNF-0012-probe1 untouched control flipped a receipt")
        return 1

    recorded = doc.get("detector_controls") or {}
    if recorded.get("mutate_one_byte_flipped") != 1:
        print("FAILED:CNF-0012-probe1 artifact mutate count drift")
        return 1
    if recorded.get("untouched_flipped") != 0:
        print("FAILED:CNF-0012-probe1 artifact untouched count drift")
        return 1
    print("SUCCESS:CNF-0012-probe1 mutate-one-byte flipped exactly one; untouched flipped none")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
