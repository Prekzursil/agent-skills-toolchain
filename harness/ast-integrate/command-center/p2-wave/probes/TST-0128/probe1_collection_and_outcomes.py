#!/usr/bin/env python3
"""Probe 1: collection sets and outcomes identical across three entry points."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from parity import good_parity  # noqa: E402


def fail(msg: str) -> int:
    print(f"FAILED:TST-0128-probe1 {msg}")
    return 1


def main() -> int:
    result = good_parity()
    print(json.dumps(result, sort_keys=True))
    if not result["match_expected"]:
        return fail(f"node ids {result['sets']} != {result['expected_node_ids']}")
    if not result["sets_identical"]:
        return fail(f"collection sets differ {result['sets']}")
    if not result["outcomes_identical"]:
        return fail("outcomes differ across entry points")
    if not result["pass"]:
        return fail(f"exits={result['exits']} ok={result['ok_flags']}")
    print(
        "SUCCESS:TST-0128-probe1 collection-and-outcomes "
        f"n={len(result['expected_node_ids'])} sets-identical outcomes-identical"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
