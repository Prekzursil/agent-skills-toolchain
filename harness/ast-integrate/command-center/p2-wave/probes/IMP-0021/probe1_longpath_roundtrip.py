#!/usr/bin/env python3
"""Probe 1: 300-character path created, written, read, deleted through the helper.

Signal 1 is the helper round-trip.
Signal 2 is an out-of-band existence check of that exact path (Get-Item
-LiteralPath when pwsh is present; otherwise independent stat/find/python -c
open that does not import plugin.longpath_fs). A helper that silently
truncated would pass signal 1 alone if it only re-read through itself.
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

from plugin.longpath_fs import (  # noqa: E402
    EXTENDED_PREFIX,
    WIN32_MAX_PATH,
    round_trip_long_path,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0021-p1-") as tmp:
        rec = round_trip_long_path(tmp, min_chars=300)
        oob = rec.get("oob") or {}
        ok = (
            rec.get("nchars") == 300
            and rec.get("read_ok") is True
            and rec.get("deleted") is True
            and rec.get("oob_after_exists") is False
            and oob.get("exists") is True
            and oob.get("nchars") == 300
            and oob.get("payload_match") is True
            and rec.get("unique_payload_file") is True
            and rec.get("win32_nchars", 0) >= WIN32_MAX_PATH
            and rec.get("needs_extended") is True
            and str(rec.get("extended") or "").startswith(EXTENDED_PREFIX)
            and (oob.get("same_path") is True or (oob.get("find") or {}).get("exact") is True)
        )
        payload = {
            "probe": "probe1-longpath-roundtrip",
            "unit_id": "IMP-0021",
            "nchars": rec.get("nchars"),
            "win32_nchars": rec.get("win32_nchars"),
            "needs_extended": rec.get("needs_extended"),
            "extended_prefix": str(rec.get("extended") or "")[:8],
            "read_ok": rec.get("read_ok"),
            "deleted": rec.get("deleted"),
            "oob_exists": oob.get("exists"),
            "oob_nchars": oob.get("nchars"),
            "oob_same_path": oob.get("same_path"),
            "oob_payload_match": oob.get("payload_match"),
            "oob_get_item_ran": oob.get("get_item_ran"),
            "oob_pwsh": oob.get("pwsh"),
            "unique_payload_file": rec.get("unique_payload_file"),
            "pass": ok,
        }
        print(json.dumps(payload, sort_keys=True))
        print(
            f"nchars={rec.get('nchars')} win32={rec.get('win32_nchars')} "
            f"read_ok={rec.get('read_ok')} oob={oob.get('exists')} "
            f"get_item_ran={oob.get('get_item_ran')} unique={rec.get('unique_payload_file')}"
        )
        if not ok:
            print("FAILED:IMP-0021-probe1 300-char round trip")
            print(json.dumps({k: rec.get(k) for k in ("path", "oob", "grep_hits")}, default=str)[:4000])
            return 1
        print("SUCCESS:IMP-0021-probe1 300-char path round trip and independent confirm")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
