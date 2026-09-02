#!/usr/bin/env python3
"""Probe 2: LF-normalized sha256 3-way partition of paths present in all three trees.

A two-directional split is classified all_three_pairwise_distinct so it cannot be
read as one-directional deploy lag. Also runs the catalog one-byte plant.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_three_way_comparator as C  # noqa: E402

OUT = HERE / "probe2-content-partition.json"


def main() -> int:
    live = C.live_world()
    with tempfile.TemporaryDirectory(prefix="aud-0012-p2-") as tmp:
        base = Path(tmp)
        one_byte = C.one_byte_control(base / "one-byte")
        two_dir = C.two_directional_control(base / "two-dir")
    errors = list(one_byte["errors"]) + list(two_dir["errors"])
    payload = {
        "probe": "probe2-content-partition",
        "unit_id": C.UNIT,
        "instrument": (
            "sha256 of LF-normalized bytes per path per tree, reported as a "
            "3-way partition"
        ),
        "home": live["home"],
        "trees": live["trees"],
        "content": live["content"],
        "one_byte_control": one_byte,
        "two_directional_control": two_dir,
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        print("FAILED:AUD-0012-probe2 " + "; ".join(errors))
        return 1
    print(
        "live all_three={0} divergent={1} one_byte_bad={2} two_dir={3}".format(
            live["content"]["all_three_count"],
            live["content"]["divergent_count"],
            one_byte["bad_state_divergent"],
            two_dir["class_for_split"],
        )
    )
    print(
        "SUCCESS:AUD-0012-probe2 LF-normalized 3-way hash partition; "
        "one-byte plant is exactly one path; two-directional is not deploy-lag"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
