#!/usr/bin/env python3
"""Named probe 2: census of program-state control planes.

Live monitorcore + this probe tree must introduce zero extra dispatchers
(answer remains one: the command-center program ledger). A planted
RivalWorkUnitDispatcher in a fixture file must raise the count to two.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "monitorcore"))

from monitorcore.census import (  # noqa: E402
    PROGRAM_LEDGER_PLANE_ID,
    census_program_planes,
)
from monitorcore.cockpit import EXISTING_PANE_IDS, PROGRAM_PANE_ID  # noqa: E402

MONITORCORE = REPO / "tools" / "monitorcore" / "monitorcore"

RIVAL_SOURCE = '''
class RivalWorkUnitDispatcher:
    """Planted second control plane for the census negative control."""

    def dispatch_unit(self, unit_id: str) -> None:
        path = "command-center/events/EVENTS.jsonl"
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(unit_id + "\\n")
'''


def main() -> int:
    if not MONITORCORE.is_dir():
        print("FAILED:IMP-0450-probe2 monitorcore package missing")
        return 1

    after = census_program_planes([MONITORCORE], repo_root=REPO)
    if after.control_plane_count != 1 or not after.is_single_plane:
        print("FAILED:IMP-0450-probe2 live census is not single-plane")
        print(json.dumps(after.as_dict(), indent=2)[:4000])
        return 1
    if after.introduced_count != 0:
        print("FAILED:IMP-0450-probe2 program pane introduced a mutator")
        print(json.dumps(after.as_dict(), indent=2)[:4000])
        return 1
    if after.existing_plane_id != PROGRAM_LEDGER_PLANE_ID:
        print("FAILED:IMP-0450-probe2 existing plane id drifted")
        return 1

    before = census_program_planes([], repo_root=REPO)
    if before.control_plane_count != 1:
        print("FAILED:IMP-0450-probe2 before-census (empty scan) is not 1")
        print(json.dumps(before.as_dict(), indent=2))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0450-p2-") as tmp:
        rival = Path(tmp) / "rival_dispatcher.py"
        rival.write_text(RIVAL_SOURCE, encoding="utf-8", newline="\n")
        planted = census_program_planes([rival], repo_root=Path(tmp))
        if planted.control_plane_count < 2:
            print("FAILED:IMP-0450-probe2 planted dispatcher not detected")
            print(json.dumps(planted.as_dict(), indent=2)[:4000])
            return 1
        kinds = {m.kind for m in planted.introduced}
        if "dispatcher-class" not in kinds:
            print("FAILED:IMP-0450-probe2 dispatcher-class marker missing")
            print(json.dumps(planted.as_dict(), indent=2)[:4000])
            return 1

    result = {
        "probe": "probe2-census",
        "unit_id": "IMP-0450",
        "pass": True,
        "before_count": before.control_plane_count,
        "after_count": after.control_plane_count,
        "answer_is_one": True,
        "existing_plane_id": after.existing_plane_id,
        "introduced_count": after.introduced_count,
        "scanned_files": after.scanned_files,
        "planted_count": planted.control_plane_count,
        "planted_detected": True,
        "inherited_pane_count": len(EXISTING_PANE_IDS),
        "added_pane": PROGRAM_PANE_ID,
        "second_dispatcher_introduced": False,
    }
    print(json.dumps(result, sort_keys=True))
    print(
        f"before={before.control_plane_count} after={after.control_plane_count} "
        f"planted={planted.control_plane_count} single_plane=True"
    )
    print("SUCCESS:IMP-0450-probe2 census remains one plane; planted rival fires")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
