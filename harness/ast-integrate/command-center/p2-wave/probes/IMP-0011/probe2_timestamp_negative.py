#!/usr/bin/env python3
"""Named probe 2: NEGATIVE CONTROL — timestamp in one build goes red.

Also: digest mismatch is not retried, and a pack-2-copies-pack-1 workflow is
rejected (reviewer cached-first-build control).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "tools" / "plugin"))

from plugin import repro_gate as G  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0011.json"
SENTINEL = "SUCCESS:IMP-0011"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:IMP-0011-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0011-probe2 sentinel-absent")
        return 1
    doc = json.loads(text)
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0011-probe2 self-declared", st)
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0011-p2-") as tmp:
        result = G.negative_control(Path(tmp) / "dist")

    if not result.get("went_red"):
        print("FAILED:IMP-0011-probe2 timestamp injection did not go red")
        return 1
    if result.get("compare_calls") != 1 or not result.get("never_retried"):
        print("FAILED:IMP-0011-probe2 mismatch was retried")
        return 1
    if result["mismatch"]["a"] == result["mismatch"]["b"]:
        print("FAILED:IMP-0011-probe2 digests unexpectedly equal")
        return 1

    cheat = G.inspect_cheat_copy_is_rejected()
    if not cheat.get("rejected"):
        print("FAILED:IMP-0011-probe2 cheat copy accepted")
        return 1

    exc = G.DigestMismatch("00", "ff")
    if not getattr(exc, "never_retry", False):
        print("FAILED:IMP-0011-probe2 DigestMismatch missing never_retry")
        return 1

    summary = {
        "probe": "probe2-timestamp-negative",
        "unit_id": "IMP-0011",
        "went_red": True,
        "compare_calls": result["compare_calls"],
        "never_retried": True,
        "cheat_copy_rejected": True,
        "never_retry_flag": True,
        "pass": True,
    }
    print(json.dumps(summary, sort_keys=True))
    print("SUCCESS:IMP-0011-probe2 timestamp injection goes red, no retry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
