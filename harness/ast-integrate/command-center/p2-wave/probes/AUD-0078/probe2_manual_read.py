#!/usr/bin/env python3
"""Named probe 2: contextual read of highest-risk files (not a second regex)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from review import review_scan  # noqa: E402

ART = REPO / "command-center/audit/AUD-0078-corpus-bundle-privacy-scan.json"
SENTINEL = (
    "SUCCESS:AUD-0078 emitted only when the artifact at output_path exists, "
    "is non-empty, parses against output_schema, and both named probes are "
    "recorded with their verbatim output"
)


def _check_artifact() -> None:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("unit_id") != "AUD-0078":
        raise SystemExit(f"FAILED:AUD-0078-probe2 unit_id {doc.get('unit_id')}")
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        raise SystemExit(f"FAILED:AUD-0078-probe2 self-declared:{doc.get('state')}")
    if SENTINEL not in text:
        raise SystemExit("FAILED:AUD-0078-probe2 sentinel absent")


def main() -> int:
    _check_artifact()
    reviewed = review_scan()
    if not reviewed.get("control_ok"):
        print(json.dumps({"control_ok": False}, sort_keys=True))
        print("FAILED:AUD-0078-probe2 include-list control")
        return 1
    public = {
        "probe": "probe2-contextual-read",
        "method": reviewed["method"],
        "not_method": reviewed["not_method"],
        "files_read": reviewed["files_read"],
        "tallies": reviewed["tallies"],
        "confirmed_paths": reviewed["confirmed_paths"],
        "reviews": [
            {
                "path": r["path"],
                "hit_count": r["hit_count"],
                "classes": r["classes"],
                "sample_verdicts": [s["verdict"] for s in r["samples"]],
            }
            for r in reviewed["reviews"]
        ],
        "never_prints_values": True,
    }
    print(json.dumps(public, sort_keys=True))
    print(
        "files_read={0} confirmed={1} overflag={2} mention={3}".format(
            reviewed["files_read"],
            reviewed["tallies"].get("CONFIRMED", 0),
            reviewed["tallies"].get("OVER-FLAG", 0),
            reviewed["tallies"].get("MENTION", 0),
        )
    )
    print("SUCCESS:AUD-0078-probe2 contextual read of highest-risk files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
