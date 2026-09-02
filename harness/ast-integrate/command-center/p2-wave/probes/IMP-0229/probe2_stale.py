#!/usr/bin/env python3
"""Probe 2: hit/miss counters measured; stale cache cannot mask a fixed package."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scenario import run_seven_key_mutations, run_stale_fixed_package  # noqa: E402


def main() -> int:
    stale = run_stale_fixed_package()
    keys = run_seven_key_mutations()
    print(json.dumps({"stale": stale, "key_mutations": keys}, sort_keys=True))
    if not stale.get("pass"):
        print("FAILED:IMP-0229-probe2 stale cache still masks a fixed package")
        return 1
    if not keys.get("pass"):
        print("FAILED:IMP-0229-probe2 cache key is not sensitive to all seven inputs")
        return 1
    print(
        "hits={h} misses={m} stale_rejects={s} mutant_masked={mm} keys_7_8={n}".format(
            h=stale["hits_measured"],
            m=stale["misses_measured"],
            s=stale["stale_rejects_measured"],
            mm=stale["name_only_mutant_still_served_v1"],
            n=keys["distinct_count"],
        )
    )
    print(
        "SUCCESS:IMP-0229-probe2 counters measured; stale entry never masks a fixed artifact"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
