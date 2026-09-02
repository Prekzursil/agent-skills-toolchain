#!/usr/bin/env python3
"""Named probe 2: atomicity + independent read-back of the live receipt.

Different field than probe 1: this probe reads destination integrity under an
injected crash (old-complete or absent, never a half-file) and independently
re-reads the live artifact as raw start/end bytes + sha256, not parsed-equality.
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


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="imp0434-p2-") as tmp:
        at = RW.self_test_atomicity(Path(tmp) / "scratch")
    print(json.dumps({"probe": "atomicity-self-test", **at}, sort_keys=True))
    if not at.get("ok"):
        print("FAILED:IMP-0434-probe2 atomicity self-test")
        return 1
    if not at.get("atomic_crash_left_old_complete"):
        print("FAILED:IMP-0434-probe2 crash left something other than the old file")
        return 1
    if not at.get("naive_crash_left_half_file"):
        print("FAILED:IMP-0434-probe2 negative control (naive writer) did not leave a half-file")
        return 1
    if not at.get("atomic_crash_on_absent_left_nothing"):
        print("FAILED:IMP-0434-probe2 crash with no prior file left a destination")
        return 1

    if not LIVE.is_file() or LIVE.stat().st_size <= 0:
        print("FAILED:IMP-0434-probe2 live receipt absent")
        return 1
    raw = LIVE.read_bytes()
    if not raw.startswith(b"{"):
        print("FAILED:IMP-0434-probe2 live receipt does not start with '{'")
        return 1
    if not raw.rstrip().endswith(b"}"):
        print("FAILED:IMP-0434-probe2 live receipt does not end with '}'")
        return 1
    if SENTINEL.encode("utf-8") not in raw:
        print("FAILED:IMP-0434-probe2 sentinel bytes absent")
        return 1
    try:
        doc = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"FAILED:IMP-0434-probe2 live unparseable:{type(exc).__name__}")
        return 1
    sha, nbytes = RW.digest_bytes(raw)
    if nbytes != len(raw.replace(b"\r\n", b"\n")):
        print("FAILED:IMP-0434-probe2 digest length mismatch")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0434-probe2 live self-declared non-delivery")
        return 1

    writer_src = (REPO / "command-center/receipt_writer.py").read_text(encoding="utf-8")
    uses_tmp = "mkstemp" in writer_src and "os.replace" in writer_src
    if not uses_tmp:
        print("FAILED:IMP-0434-probe2 writer is not tmp-plus-replace")
        return 1

    out = {
        "probe": "probe2-atomicity-independent-readback",
        "unit_id": "IMP-0434",
        "live_starts_object": True,
        "live_ends_object": True,
        "live_bytes": len(raw),
        "live_sha256": sha,
        "independent_parse_unit_id": doc.get("unit_id"),
        "atomic_crash_left_old_complete": True,
        "naive_crash_left_half_file": True,
        "pass": True,
    }
    print(json.dumps(out, sort_keys=True))
    print(
        f"live_bytes={len(raw)} sha256={sha} "
        f"atomic_old_intact=True naive_half=True"
    )
    print("SUCCESS:IMP-0434-probe2 atomicity and independent read-back")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
