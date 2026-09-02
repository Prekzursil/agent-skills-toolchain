#!/usr/bin/env python3
"""Named probe 2: live shell round-trip; apostrophe-inline FAIL vs file-path SUCCESS."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from helpers import OUT_REL, REPO, SENTINEL, UNIT  # noqa: E402
from roundtrip import run_roundtrips  # noqa: E402

ART = REPO / OUT_REL


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:AUD-0086-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != UNIT:
        print("FAILED:AUD-0086-probe2 unit_id", doc.get("unit_id"))
        return 1
    if SENTINEL not in text:
        print("FAILED:AUD-0086-probe2 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:AUD-0086-probe2 self-declared", doc.get("state"))
        return 1

    live = run_roundtrips()
    if not live.get("control_pass"):
        print("FAILED:AUD-0086-probe2 round-trip control")
        print(json.dumps(live.get("control"), sort_keys=True))
        return 1
    if not live["control"].get("inline_apostrophe_failed"):
        print("FAILED:AUD-0086-probe2 naive apostrophe wrap did not fail")
        return 1
    if not live["control"].get("file_path_succeeded"):
        print("FAILED:AUD-0086-probe2 file-path argv did not succeed")
        return 1

    recorded = (doc.get("roundtrip") or {}).get("control") or {}
    if recorded.get("inline_apostrophe_failed") is not True:
        print("FAILED:AUD-0086-probe2 artifact missing inline-fail control")
        return 1
    if recorded.get("file_path_succeeded") is not True:
        print("FAILED:AUD-0086-probe2 artifact missing file-path success control")
        return 1

    posix = live.get("posix_apostrophe") or []
    if len(posix) < 1:
        print("FAILED:AUD-0086-probe2 no POSIX shell available")
        return 1

    summary = {
        "probe": "probe2-roundtrip",
        "unit_id": UNIT,
        "pass": True,
        "shells_run": [r["shell"] for r in posix],
        "inline_apostrophe_failed": True,
        "file_path_succeeded": True,
        "pwsh_present": live.get("pwsh_present"),
        "git_bash_present": live.get("git_bash_present"),
        "procsubst": live.get("procsubst"),
        "independent_of_pattern_scan": True,
    }
    print(json.dumps(summary, sort_keys=True, default=str))
    print("SUCCESS:AUD-0086-probe2 roundtrip")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
