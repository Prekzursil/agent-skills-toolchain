#!/usr/bin/env python3
"""Probe 1: grammar-derived campaign reports semantic reach-rate; byte-level does not."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from campaign import test_semantic_reach_rate_is_reported  # noqa: E402


def main() -> int:
    result = test_semantic_reach_rate_is_reported()
    g = result["grammar"]
    b = result["byte"]
    print(
        json.dumps(
            {
                "probe": "probe1-semantic-reach-rate",
                "ok": result["ok"],
                "grammar_generated": g["generated"],
                "grammar_semantic_layer_count": g["semantic_layer_count"],
                "grammar_reach_rate": g["reach_rate"],
                "byte_semantic_layer_count": b["semantic_layer_count"],
                "byte_reach_rate": b["reach_rate"],
                "repro_same_seed": result["repro_same_seed"],
                "grammar_sha256": g["grammar_sha256"],
                "hung": g["hung"],
                "crashed": g["crashed"],
            },
            sort_keys=True,
        )
    )
    if not result["ok"]:
        print("FAILED:TST-0118-probe1 reach-rate missing, low, or unreproducible")
        return 1
    print(
        f"grammar_reach={g['reach_rate']:.3f} "
        f"semantic={g['semantic_layer_count']}/{g['generated']} "
        f"byte_reach={b['reach_rate']:.3f}"
    )
    print("SUCCESS:TST-0118-probe1 semantic reach-rate reported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
