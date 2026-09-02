#!/usr/bin/env python3
"""Named probe 1: write a receipt, read it back, parse it, compare, report bytes.

Uses a different instrument than probe 2: parsed-document equality plus the
on-disk byte count from the live catalog artifact. A path in prose is not proof.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "command-center"))
import receipt_writer as RW  # noqa: E402

LIVE = REPO / "command-center/receipts/IMP-0434.json"
SENTINEL = "SENTINEL:IMP-0434:RECEIPT-WRITER-ATOMIC"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0434-p1-") as tmp:
        rt = RW.self_test_roundtrip(Path(tmp) / "scratch")
    print(json.dumps({"probe": "roundtrip-self-test", **rt}, sort_keys=True))
    if not rt.get("ok"):
        print("FAILED:IMP-0434-probe1 library round-trip self-test")
        return 1
    if not rt.get("parsed_equals_written"):
        print("FAILED:IMP-0434-probe1 parsed content did not equal what was written")
        return 1
    if not rt.get("both_states"):
        print("FAILED:IMP-0434-probe1 structural validator is not two-sided")
        return 1

    if not LIVE.is_file() or LIVE.stat().st_size <= 0:
        print("FAILED:IMP-0434-probe1 live receipt absent")
        return 1
    raw = LIVE.read_bytes()
    live_bytes = len(raw)
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:IMP-0434-probe1 live unparseable:{type(exc).__name__}")
        return 1
    text = raw.decode("utf-8")
    if SENTINEL not in text:
        print("FAILED:IMP-0434-probe1 sentinel absent from live receipt")
        return 1
    if doc.get("unit_id") != "IMP-0434":
        print("FAILED:IMP-0434-probe1 unit_id", doc.get("unit_id"))
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:IMP-0434-probe1 self-declared:{st}")
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0434-p1-live-") as tmp:
        copy = Path(tmp) / "copy.json"
        measured = RW.round_trip(copy, doc, validate=True, repo=REPO)
    if not measured.get("ok") or not measured.get("parsed_equals_written"):
        print("FAILED:IMP-0434-probe1 live document failed library round-trip")
        print(json.dumps(measured, sort_keys=True))
        return 1

    writer = REPO / "command-center/receipt_writer.py"
    src = writer.read_text(encoding="utf-8")
    if "os.replace" not in src:
        print("FAILED:IMP-0434-probe1 writer source has no os.replace")
        return 1

    out = {
        "probe": "probe1-roundtrip",
        "unit_id": "IMP-0434",
        "live_exists": True,
        "live_bytes": live_bytes,
        "live_sha256": RW.digest_bytes(raw)[0],
        "parsed_equals_written": True,
        "library_roundtrip_bytes": measured["bytes"],
        "contract": rt.get("contract"),
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"live_bytes={live_bytes} copy_bytes={measured['bytes']} "
        f"parsed_equals_written=True contract={rt.get('contract')}"
    )
    print("SUCCESS:IMP-0434-probe1 round-trip read-back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
