"""Refuses a zero shipped-scan unless the planted control is recorded (IMP-0468)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import case_collision as cc  # noqa: E402

PLANTED = HERE / "fixtures" / "planted-collision.json"


def main() -> int:
    # planted control first: a zero scan is untrusted until this has fired
    planted = cc.detect_file(PLANTED, repo=REPO)
    planted_ok = bool(planted["walk_hits"])
    assert planted_ok, "planted control must fire before any zero result is trusted"

    # live shipped-surface rescan (mechanically different from probe1)
    shipped = cc.scan_shipped(REPO)
    assert shipped["files_scanned_count"] > 0, "shipped scan saw nothing"
    # refuse a suspicious zero WITHOUT the control (simulate by checking both)
    if shipped["collision_count"] == 0:
        assert planted_ok, "zero shipped result without planted control is untrusted"

    # non-case-distinct fixture stays silent
    non_case = cc.detect_file(HERE / "fixtures" / "non-case-distinct.json", repo=REPO)
    assert not non_case["walk_hits"], non_case["walk_hits"]

    # controls battery passes end-to-end
    controls = cc.run_required_controls()
    assert controls["all_passed"] is True

    print(json.dumps({
        "probe": "probe2-non-case-and-live-rescan",
        "unit_id": "IMP-0468",
        "planted_control_recorded": planted_ok,
        "shipped_files_scanned": shipped["files_scanned_count"],
        "shipped_collision_count": shipped["collision_count"],
        "non_case_silent": True,
        "controls_all_passed": True,
        "zero_result_gated_on_control": True,
        "sentinel": "SENTINEL:IMP-0468:CASE-COLLISION-SCANNED",
    }, indent=2))
    print("SUCCESS:IMP-0468-probe2 zero scan gated on planted control; live rescan done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
