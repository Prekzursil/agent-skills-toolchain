#!/usr/bin/env python3
"""Probe 2: regression seed + cp1252 process exit status.

Independent of probe1's in-process TextIOWrapper byte capture:
  (a) subprocess exit status of close.py --list under PYTHONIOENCODING=cp1252
  (b) UnicodeDecodeError from the cp1252 codec on the live UTF-8 catalog

The seed must fire on this box (live WORK-UNIT-CATALOG.json contains a cp1252
undefined byte). The UTF-8 decode of the same bytes must succeed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import harness as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0249.json"


def main() -> int:
    live = H.measure()
    seed = live["regression_seed"]
    proc = live["cp1252_console"]["subprocess"]
    print(
        json.dumps(
            {
                "probe": "probe2-regression-seed",
                "unit_id": H.UNIT,
                "path": seed["path"],
                "utf8_ok": seed["utf8_ok"],
                "cp1252_raises": seed["cp1252_raises"],
                "cp1252_exc": seed["cp1252_exc"],
                "unicode_at_hole": seed["unicode_at_hole"],
                "utf8_sequence_at_hole_hex": seed["utf8_sequence_at_hole_hex"],
                "cp1252_exit_code": proc["exit_code"],
                "unicode_encode_error": proc["unicode_encode_error"],
                "stdout_byte_count": proc["stdout_byte_count"],
            },
            sort_keys=True,
        )
    )
    print(
        f"seed utf8_ok={seed['utf8_ok']} cp1252_raises={seed['cp1252_raises']} "
        f"exc={seed['cp1252_exc']}"
    )
    print(
        f"cp1252_console exit={proc['exit_code']} "
        f"UnicodeEncodeError={proc['unicode_encode_error']} "
        f"stdout_bytes={proc['stdout_byte_count']}"
    )
    if not seed["utf8_ok"]:
        print("FAILED:TST-0249-probe2 live catalog is not valid UTF-8")
        return 1
    if not seed["cp1252_raises"]:
        print("FAILED:TST-0249-probe2 cp1252 decode did not raise UnicodeDecodeError")
        return 1
    exc = seed.get("cp1252_exc") or {}
    if exc.get("type") != "UnicodeDecodeError":
        print("FAILED:TST-0249-probe2 expected UnicodeDecodeError")
        return 1
    if exc.get("undefined_byte") != "0x90":
        print(f"FAILED:TST-0249-probe2 expected undefined byte 0x90 got {exc.get('undefined_byte')}")
        return 1
    if proc["exit_code"] == 0:
        print("FAILED:TST-0249-probe2 cp1252 close.py unexpectedly exited 0")
        return 1
    if not proc["unicode_encode_error"]:
        print("FAILED:TST-0249-probe2 cp1252 close.py did not surface UnicodeEncodeError")
        return 1

    if not ART.is_file():
        print("FAILED:TST-0249-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if H.SENTINEL not in text:
        print("FAILED:TST-0249-probe2 sentinel absent")
        return 1
    rec_seed = doc.get("regression_seed") or {}
    rec_exc = rec_seed.get("cp1252_exc") or {}
    if rec_seed.get("cp1252_raises") is not True:
        print("FAILED:TST-0249-probe2 artifact seed not live")
        return 1
    if rec_exc.get("start") != exc.get("start") or rec_exc.get("undefined_byte") != exc.get(
        "undefined_byte"
    ):
        print(f"FAILED:TST-0249-probe2 seed drift artifact={rec_exc} live={exc}")
        return 1
    rec_proc = ((doc.get("cp1252_console") or {}).get("subprocess") or {})
    if rec_proc.get("exit_code") != proc["exit_code"]:
        print(
            f"FAILED:TST-0249-probe2 exit drift artifact={rec_proc.get('exit_code')} live={proc['exit_code']}"
        )
        return 1
    if rec_proc.get("unicode_encode_error") is not True:
        print("FAILED:TST-0249-probe2 artifact missing UnicodeEncodeError flag")
        return 1
    ev = doc.get("evidence") or []
    kinds = {e.get("kind") for e in ev if isinstance(e, dict)}
    if "process-exit-status" not in kinds or "byte-level-capture" not in kinds:
        print(f"FAILED:TST-0249-probe2 evidence kinds {kinds}")
        return 1
    print("SUCCESS:TST-0249-probe2 regression seed and cp1252 exit status")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
