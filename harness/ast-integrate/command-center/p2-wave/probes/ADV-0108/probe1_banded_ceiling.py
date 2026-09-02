#!/usr/bin/env python3
"""Probe 1: evidence-type ceiling on every banded claim."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from engine import probe1_result  # noqa: E402


def main() -> int:
    result = probe1_result()
    print(json.dumps(result, sort_keys=True))
    ctrl = result["controls"]
    print(
        "n_banded={n} n_live={l} over_ceiling={o} non_lex={x} "
        "good={g} overclaim={v} infer={i}".format(
            n=result["n_banded"],
            l=result["n_live"],
            o=result["n_over_ceiling_live"],
            x=result["n_non_lexicon_live"],
            g=ctrl["good_banded_passes"],
            v=ctrl["overclaim_flagged"],
            i=ctrl["inference_within_ceiling"],
        )
    )
    if not result["pass"]:
        print("FAILED:ADV-0108-probe1 control or ceiling check failed")
        return 1
    print("SUCCESS:ADV-0108-probe1 banded claims classified against evidence-type ceiling")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
