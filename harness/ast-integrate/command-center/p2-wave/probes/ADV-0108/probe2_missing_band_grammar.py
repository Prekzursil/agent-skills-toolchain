#!/usr/bin/env python3
"""Probe 2: grammar detector for unbanded forward-looking claims.

Finds predictions by modal/hedge pattern, not by scanning for Sherman-Kent tokens.
Independently re-derives the planted overclaim and missing-band cases from fixture
bytes rather than from probe 1's report.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import probe2_result  # noqa: E402


def main() -> int:
    result = probe2_result()
    print(json.dumps(result, sort_keys=True))
    ctrl = result["controls"]
    print(
        "n_forward={n} missing_live={m} planted_missing={p} "
        "unbanded={u} looks={lf} likely={lk} past={ps} mention={mn} good={g}".format(
            n=result["n_forward"],
            m=result["n_missing_live"],
            p=result["n_missing_planted"],
            u=ctrl["planted_unbanded_fires"],
            lf=ctrl["looks_fine_fires"],
            lk=ctrl["likely_fine_fires"],
            ps=ctrl["past_measurement_silent"],
            mn=ctrl["mention_silent"],
            g=ctrl["good_banded_not_missing"],
        )
    )
    if not result["pass"]:
        print("FAILED:ADV-0108-probe2 grammar controls failed")
        return 1
    print("SUCCESS:ADV-0108-probe2 missing-band grammar detector; reviewer re-derived from raw fixtures")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
