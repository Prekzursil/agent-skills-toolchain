#!/usr/bin/env python3
"""Probe 1: soundness differential over >=100 mutations.

Known-good: coverage-map selector miss_list is empty (every mutation the
full suite catches, the subset also catches). Known-broken: filename-only
selector produces a miss list naming the file each missed mutation touched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import engine as E  # noqa: E402
import product as P  # noqa: E402

UNIT = "TST-0337"


def main() -> int:
    P.dump_coverage_map()
    live = E.run()
    sound = live["sound"]
    unsound = live["unsound_filename_only"]
    graph = live["dependency_graph"]
    bs = live["both_states"]
    miss_files = sorted({row["file"] for row in unsound["miss_list"]})
    payload = {
        "probe": "probe1-soundness-differential",
        "unit_id": UNIT,
        "n_mutations": sound["n_mutations"],
        "caught_by_full_suite": sound["caught_by_full_suite"],
        "caught_by_subset": sound["caught_by_subset"],
        "sound_miss_count": sound["miss_count"],
        "sound_miss_list": sound["miss_list"],
        "graph_miss_count": graph["miss_count"],
        "unsound_miss_count": unsound["miss_count"],
        "unsound_miss_files": miss_files,
        "unsound_miss_list_head": unsound["miss_list"][:8],
        "time_saved": sound["time_saved"],
        "both_states_discriminates": bs["discriminates"],
        "pass": bool(live["ok"] and sound["sound"] and bs["discriminates"]),
    }
    print(json.dumps(payload, sort_keys=True))

    if sound["n_mutations"] < 100:
        print(f"FAILED:{UNIT}-probe1 corpus size {sound['n_mutations']} < 100")
        return 1
    if sound["caught_by_full_suite"] < 100:
        print(
            f"FAILED:{UNIT}-probe1 full suite caught "
            f"{sound['caught_by_full_suite']} < 100"
        )
        return 1
    if sound["miss_count"] != 0:
        print(f"FAILED:{UNIT}-probe1 coverage-map selector is unsound")
        return 1
    if graph["miss_count"] != 0:
        print(f"FAILED:{UNIT}-probe1 dependency-graph selector is unsound")
        return 1
    if unsound["miss_count"] <= 0:
        print(f"FAILED:{UNIT}-probe1 filename-only control produced no misses")
        return 1
    if not miss_files:
        print(f"FAILED:{UNIT}-probe1 miss list has no files")
        return 1
    if not bs["discriminates"]:
        print(f"FAILED:{UNIT}-probe1 both-states control silent")
        return 1
    if sound["caught_by_subset"] != sound["caught_by_full_suite"]:
        print(f"FAILED:{UNIT}-probe1 subset catch count drifted from full suite")
        return 1
    print(
        f"SUCCESS:{UNIT}-probe1 n={sound['n_mutations']} "
        f"full={sound['caught_by_full_suite']} subset={sound['caught_by_subset']} "
        f"misses=0 unsound_misses={unsound['miss_count']} "
        f"files={','.join(miss_files[:6])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
