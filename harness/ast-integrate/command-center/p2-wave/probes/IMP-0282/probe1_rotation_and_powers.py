#!/usr/bin/env python3
"""Named probe 1: rotation order, chair powers, recognition distribution.

Live API, not a receipt-presence check. Also runs the independent
submission-presence check and a mutant that drops unrecognised rows.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import RECEIPT, evaluate_probe1  # noqa: E402

ART = REPO / RECEIPT


def main() -> int:
    result = evaluate_probe1()
    print(json.dumps(result, indent=2, sort_keys=True, default=str))
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0282-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:IMP-0282" not in text:
        print("FAILED:IMP-0282-probe1 sentinel absent")
        return 1
    if not result["pass"]:
        print("FAILED:IMP-0282-probe1 rotation/powers/distribution")
        return 1
    rot = result["rotation"]["observed"]
    print(
        f"chairs={rot} counts={result['recognition_counts']} "
        f"presence={result['presence']['journal_count']}"
    )
    print("SUCCESS:IMP-0282-probe1 rotation, chair powers, recognition distribution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
