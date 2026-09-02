#!/usr/bin/env python3
"""Probe 1: three-way set comparison of relative paths across the skills trees."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_three_way_comparator as C  # noqa: E402

OUT = HERE / "probe1-path-sets.json"


def main() -> int:
    live = C.live_world()
    with tempfile.TemporaryDirectory(prefix="aud-0012-p1-") as tmp:
        control = C.path_set_control(Path(tmp))
    errors = list(control["errors"])
    payload = {
        "probe": "probe1-path-sets",
        "unit_id": C.UNIT,
        "instrument": "three-way set comparison of relative paths",
        "home": live["home"],
        "trees": live["trees"],
        "path_sets": live["path_sets"],
        "control": control,
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        print("FAILED:AUD-0012-probe1 " + "; ".join(errors))
        return 1
    counts = live["path_sets"]["counts"]
    print(
        "live only_repo={0} only_agents={1} only_claude={2} all_three={3} "
        "in_one_or_two={4}".format(
            counts["only_repo"],
            counts["only_agents"],
            counts["only_claude"],
            counts["all_three"],
            live["path_sets"]["in_one_or_two_count"],
        )
    )
    print(
        "SUCCESS:AUD-0012-probe1 three-way relative-path set comparison; "
        "seven-bucket plant holds"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
