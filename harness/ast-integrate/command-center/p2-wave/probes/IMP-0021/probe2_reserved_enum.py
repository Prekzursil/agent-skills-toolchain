#!/usr/bin/env python3
"""Probe 2: NUL-named file enumerates; pre-fix enumerator raises.

Reviewer signal: errors are surfaced, never swallowed into an empty set.
NEGATIVE CONTROL: unsafe_enumerate (Windows-naive relpath) MUST raise on NUL.
Host os.path.relpath on Linux typically does *not* raise — that silence is
the wrong-reason green this control exists to prevent.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
TOOLS = REPO / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from plugin.longpath_fs import enumerate_both, plant_nul_fixture  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0021-p2-") as tmp:
        planted = plant_nul_fixture(Path(tmp) / "fx")
        both = enumerate_both(planted["root"])
        host = both.get("host_os_relpath") or {}
        err = str(both.get("naive_error") or "")
        ok = (
            both.get("naive_raised") is True
            and "NUL" in err
            and "mount" in err
            and both.get("naive_paths") is None
            and both.get("empty_safe") is False
            and both.get("keep_present") is True
            and bool(both.get("nul_rels"))
            and both.get("nested_present") is True
            and int(both.get("safe_count") or 0) >= 3
        )
        payload = {
            "probe": "probe2-reserved-enum",
            "unit_id": "IMP-0021",
            "naive_raised": both.get("naive_raised"),
            "naive_error": err,
            "safe_count": both.get("safe_count"),
            "nul_rels": both.get("nul_rels"),
            "keep_present": both.get("keep_present"),
            "nested_present": both.get("nested_present"),
            "empty_safe": both.get("empty_safe"),
            "host_os_relpath_raised": host.get("raised"),
            "host_platform": host.get("platform"),
            "pass": ok,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"naive_raised={both.get('naive_raised')} safe_count={both.get('safe_count')} "
            f"nul={both.get('nul_rels')} host_relpath_raised={host.get('raised')}"
        )
        if not ok:
            print("FAILED:IMP-0021-probe2 NUL enumeration / negative control")
            return 1
        print("SUCCESS:IMP-0021-probe2 NUL enumerates; pre-fix enumerator raises")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
