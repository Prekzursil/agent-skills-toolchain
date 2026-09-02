#!/usr/bin/env python3
"""Probe 1: three planted mutant shapes must be caught on the real corpus."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import control as C  # noqa: E402
import differ as D  # noqa: E402
import plant as P  # noqa: E402

OUT = HERE / "probe1-mutants.raw.json"


def fail(msg: str) -> int:
    print(f"FAILED:WFA-0096-probe1 {msg}")
    return 1


def main() -> int:
    live = C.run_control()
    if live["threshold"] != D.THRESHOLD:
        return fail(f"threshold drifted {live['threshold']} != {D.THRESHOLD}")
    if live["differ_sha256"] != D.module_fingerprint(HERE / "differ.py"):
        return fail("differ fingerprint mismatch; control must re-run on differ change")
    if live["toy_fixture"] or not live["planted_into_real_corpus"]:
        return fail("mutants were not planted into the real corpus")
    if live["base_count"] < 100:
        return fail(f"corpus too small base_count={live['base_count']}")
    if live["self_diff_failures"]:
        return fail(f"self-diff not empty {live['self_diff_failures'][:5]}")
    if not live["absent_versus_different"]["distinguished"]:
        return fail(f"ABSENT collapsed into PRESENT-BUT-DIFFERENT {live['absent_versus_different']}")
    if not live["never_fire_would_miss_mutants"]:
        return fail("threshold=1.01 negative control did not miss mutants")

    wanted = list(P.SHAPES)
    got = [row["shape"] for row in live["mutants"]]
    if got != wanted:
        return fail(f"shapes {got} != {wanted}")
    for row in live["mutants"]:
        print(
            f"mutant shape={row['shape']} plant={row['plant_id']} host={row['host_id']} "
            f"nearest={row['nearest_id']} score={row['nearest_score']} "
            f"detected={row['detected']} exclusive={row['exclusive_vs_host']}"
        )
        if not row["detected"]:
            return fail(f"{row['shape']} not detected at threshold {D.THRESHOLD}")
        if row["nearest_id"] != row["host_id"]:
            return fail(
                f"{row['shape']} nearest {row['nearest_id']} != host {row['host_id']}"
            )
        if row["independent_duplicate_vs_host"] is not True:
            return fail(f"{row['shape']} independent exclusive-count missed host")
    if not live["mutants_caught"]:
        return fail("mutants_caught flag false")

    OUT.write_text(json.dumps(live, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"caught={len(live['mutants'])} shapes={got} "
        f"base_count={live['base_count']} threshold={live['threshold']} "
        f"differ_sha256={live['differ_sha256'][:12]}"
    )
    print("SUCCESS:WFA-0096-probe1 three mutant shapes caught on real corpus")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
