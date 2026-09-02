#!/usr/bin/env python3
"""Named probe 1: clean-room HOME is actually empty (control before trusting the lane)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
from lane import (  # noqa: E402
    check_home_empty_control,
    inspect_home,
    plant_ambient_home,
    run_lane,
)

ART = REPO / "command-center/receipts/TST-0024.json"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0024-p1-neg-") as neg:
        planted = Path(neg) / "planted"
        insp = plant_ambient_home(planted)
        if insp.get("empty_of_profile"):
            print("FAILED:TST-0024-probe1 negative control treated planted HOME as empty")
            print(json.dumps(insp, indent=2, default=str)[:1500])
            return 1
        empty = Path(neg) / "empty"
        empty.mkdir()
        empty_insp = inspect_home(empty)
        if not empty_insp.get("empty_of_profile"):
            print("FAILED:TST-0024-probe1 empty tempfile HOME was not empty")
            print(json.dumps(empty_insp, indent=2, default=str)[:1500])
            return 1

    with tempfile.TemporaryDirectory(prefix="tst0024-p1-lane-") as tmp:
        lane = run_lane(Path(tmp))
        control = check_home_empty_control(lane)
        print(json.dumps(control, indent=2, sort_keys=True, default=str)[:4000])
        if not control["pass"]:
            print("FAILED:TST-0024-probe1 home-empty control")
            return 1
        clean_home = Path(lane["clean_room"]["home"]).resolve()
        dev_home = Path(lane["developer_home"]).resolve()
        print(
            f"clean_home={clean_home} developer_home={dev_home} "
            f"redirected={clean_home != dev_home} "
            f"empty_of_profile={lane['clean_home_is_empty']}"
        )
        if clean_home == dev_home:
            print("FAILED:TST-0024-probe1 clean-room HOME was the developer HOME")
            return 1

    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:TST-0024-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "TST-0024":
        print("FAILED:TST-0024-probe1 unit_id", doc.get("unit_id"))
        return 1
    if "SUCCESS:TST-0024" not in text:
        print("FAILED:TST-0024-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:TST-0024-probe1 self-declared", doc.get("state"))
        return 1
    print("SUCCESS:TST-0024-probe1 clean-room HOME is actually empty")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
