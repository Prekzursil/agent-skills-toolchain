#!/usr/bin/env python3
"""Named probe 1: planted missing/empty/directory controls must still fire."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from controls import (  # noqa: E402
    control_directory_requires_member,
    control_missing_is_absent,
    control_zero_byte_is_empty,
)

ART = REPO / "command-center/receipts/BLD-0016.json"
NEEDED = {
    "manifest-nonexistent-path-absent",
    "zero-byte-file-empty-never-present",
    "directory-requires-named-member",
}


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:BLD-0016-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:BLD-0016" not in text:
        print("FAILED:BLD-0016-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "BLD-0016":
        print("FAILED:BLD-0016-probe1 unit_id", doc.get("unit_id"))
        return 1
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:BLD-0016-probe1 self-declared", doc.get("state"))
        return 1

    c1 = control_missing_is_absent()
    c2 = control_zero_byte_is_empty()
    c3 = control_directory_requires_member()
    live = [c1, c2, c3]
    if not all(c["pass"] for c in live):
        print("FAILED:BLD-0016-probe1 control did not pass")
        print(json.dumps(live, indent=2)[:3000])
        return 1

    recorded = {
        c.get("id")
        for c in (doc.get("controls") or [])
        if c.get("pass") is True
    }
    missing = NEEDED - recorded
    if missing:
        print("FAILED:BLD-0016-probe1 receipt missing passing controls", sorted(missing))
        return 1

    payload = {
        "probe": "probe1-planted-controls",
        "unit_id": "BLD-0016",
        "pass": True,
        "missing_is_absent": True,
        "zero_byte_is_empty": True,
        "directory_requires_member": True,
        "receipt_control_pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "missing=ABSENT empty=EMPTY dir_member=required "
        "receipt_controls=True"
    )
    print("SUCCESS:BLD-0016-probe1 planted-absent-empty-dir")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
