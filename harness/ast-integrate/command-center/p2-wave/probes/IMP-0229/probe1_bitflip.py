#!/usr/bin/env python3
"""Probe 1: bit-flipped CAS entry is detected and refetched; clean entry is a hit."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario import run_bitflip_both_states  # noqa: E402


def main() -> int:
    result = run_bitflip_both_states()
    print(json.dumps(result, sort_keys=True))
    if not result.get("pass"):
        print("FAILED:IMP-0229-probe1 bit-flip served or both-states unpaid")
        return 1
    print(
        "clean_hit={hits} corrupt_refetch={cr} served_flipped={sf}".format(
            hits=result["counters_after_clean_hit"]["hits"],
            cr=result["counters_after_corrupt"]["corrupt_refetches"],
            sf=result["served_flipped"],
        )
    )
    print("SUCCESS:IMP-0229-probe1 bit-flip detected and refetched (both-states)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
