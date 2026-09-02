#!/usr/bin/env python3
"""Independent D recompute for TST-0259 evidence verifier (not probe1)."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from divergence import floor_value, score_from_raw  # noqa: E402
from simulate import run_named  # noqa: E402


def main() -> int:
    fl = floor_value()
    sc = score_from_raw(run_named("collapsed")["participants"])
    sd = score_from_raw(run_named("differentiated")["participants"])
    print(f"collapsed_D={sc['D']:.12f} panel={sc['panel']}")
    print(f"differentiated_D={sd['D']:.12f} panel={sd['panel']}")
    print(f"floor={fl:.12f}")
    if not (sc["D"] < fl <= sd["D"] and sc["panel"] == "FAIL" and sd["panel"] == "PASS"):
        print("FAILED:TST-0259-recompute")
        return 1
    print("RECOMPUTE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
