#!/usr/bin/env python3
"""Named probe 2: numbered migration up then down restores original bytes.

Independent of probe1's workspace. Rehearses the accepted path: freeze,
apply a numbered migration whose down-step is executable, confirm up then
down is byte-identical to the pre-up corpus, then apply_accepted and confirm
a later in-place edit is still refused.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_roundtrip_scenario  # noqa: E402

ART = REPO / "command-center/receipts/IMP-0477.json"
SENTINEL = "SENTINEL:IMP-0477:MIGRATIONS-VERSIONED"
NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def _check_artifact() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0477-probe2 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:IMP-0477-probe2 unparseable {exc}")
        return 1
    if SENTINEL not in text:
        print("FAILED:IMP-0477-probe2 sentinel absent")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:IMP-0477-probe2 self-declared:{st}")
        return 1
    mig = doc.get("accepted_migration") or {}
    if mig.get("round_trip_byte_identical") is not True:
        print("FAILED:IMP-0477-probe2 receipt did not claim round-trip")
        return 1
    if mig.get("up_executed") is not True or mig.get("down_executed") is not True:
        print("FAILED:IMP-0477-probe2 receipt missing executed up/down")
        return 1
    return 0


def main() -> int:
    if _check_artifact() != 0:
        return 1
    with tempfile.TemporaryDirectory(prefix="imp0477-p2-") as tmp:
        rt = run_roundtrip_scenario(Path(tmp))

    payload = {
        "probe": "probe2-roundtrip",
        "unit_id": "IMP-0477",
        "roundtrip": rt,
        "pass": bool(rt.get("pass")),
    }
    print(json.dumps(payload, sort_keys=True))
    if not rt.get("pass"):
        print("FAILED:IMP-0477-probe2 round-trip")
        return 1
    if not rt.get("byte_identical"):
        print("FAILED:IMP-0477-probe2 original bytes not restored")
        return 1
    if rt.get("original_sha256") != rt.get("restored_sha256"):
        print("FAILED:IMP-0477-probe2 sha mismatch after down")
        return 1
    print(
        "roundtrip=%s files=%s orig=%s restored=%s accepted=%s"
        % (
            rt.get("round_trip_ok"),
            rt.get("files_compared"),
            rt.get("original_sha256"),
            rt.get("restored_sha256"),
            rt.get("accepted_ok"),
        )
    )
    print("SUCCESS:IMP-0477-probe2 up then down restored original bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
