#!/usr/bin/env python3
"""Named probe 2: negative control — unshuffled order raises linkage above chance.

Names stay masked and timing/tokens/style stay stripped. Only seating order
leaks. The order-channel attack must then beat chance by a wide margin, proving
the detector can go red and that order is a real linking channel.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scenario import CHANCE, run_unshuffled_control  # noqa: E402


def main() -> int:
    result = run_unshuffled_control()
    print(json.dumps(result, sort_keys=True))
    acc = result["order_accuracy"]
    if acc < result["min_threshold"]:
        print(
            f"FAILED:IMP-0276-probe2 unshuffled accuracy={acc:.4f} "
            f"below min={result['min_threshold']:.4f} chance={CHANCE:.4f}"
        )
        return 1
    if acc <= CHANCE + 0.50:
        print(
            f"FAILED:IMP-0276-probe2 unshuffled accuracy={acc:.4f} "
            f"not distinguishable from chance={CHANCE:.4f}"
        )
        return 1
    print(
        f"unshuffled_order_accuracy={acc:.4f} chance={CHANCE:.4f} "
        f"min={result['min_threshold']:.4f}"
    )
    print("SUCCESS:IMP-0276-probe2 unshuffled order raises linkage above chance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
