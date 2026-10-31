#!/usr/bin/env python3
"""Named probe 1: power conservation on 100 random graphs and constructed fixtures."""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from checks import run_probe1_body  # noqa: E402


def main() -> int:
    require_receipt = "--no-receipt" not in sys.argv
    result = run_probe1_body(require_receipt=require_receipt)
    print(json.dumps(result, sort_keys=True))
    if result["pass"]:
        cons = result["checks"]["conservation_100"]
        extra = ""
        if require_receipt:
            extra = f" receipt_bytes={result['checks']['receipt']['bytes']}"
        print(
            f"conserved_100={cons.get('n_trials')} cyclic_random={cons.get('n_cyclic_graphs')}"
            f"{extra}"
        )
        print("SUCCESS:IMP-0304-probe1 conservation and inbound-to-cycle retention")
        return 0
    print("FAILED:IMP-0304-probe1")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
