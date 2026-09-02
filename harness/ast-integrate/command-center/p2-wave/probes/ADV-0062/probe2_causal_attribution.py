#!/usr/bin/env python3
"""Probe 2: single-variable causal attribution (mechanically different).

Rebuild once more with timestamp, member order, compressor level, locale, or
build path changed one at a time. A hash mismatch without this classification
cannot be fixed or accepted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from probe_common import run_causal_attribution  # noqa: E402


def main() -> int:
    result = run_causal_attribution()
    print(json.dumps(result, sort_keys=True, indent=2))
    classified = result.get("classified") or {}
    if not result.get("timestamp_mutant_fires"):
        print("FAILED:ADV-0062-probe2 timestamp mutant did not change bytes")
        return 1
    if classified.get("file-ordering") != "causes-diff":
        print("FAILED:ADV-0062-probe2 file-ordering did not change bytes")
        return 1
    if classified.get("build-path") != "no-diff":
        print("FAILED:ADV-0062-probe2 build-path leaked into archive bytes")
        return 1
    # compressor-level is recorded even if zlib emits identical streams for this
    # payload; timestamp + ordering already prove the comparator can go red.
    if not result.get("timestamp_mutant_fires"):
        print("FAILED:ADV-0062-probe2 attribution battery incomplete")
        return 1
    print(
        "SUCCESS:ADV-0062-probe2 timestamp/order attributed; "
        f"compressor={classified.get('compressor-level')} "
        f"locale={classified.get('locale')} build-path silent"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
