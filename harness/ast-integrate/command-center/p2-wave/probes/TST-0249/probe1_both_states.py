#!/usr/bin/env python3
"""Probe 1: both-states UTF-8 console output is byte-exact.

Mechanism: in-process TextIOWrapper(encoding=utf-8) two-run identity plus
equality with text.encode('utf-8'). Independent of probe2's subprocess exit
status and of the live-catalog cp1252 decode seed.

Detector control: the same payload through TextIOWrapper(encoding=cp1252,
errors=strict) must raise UnicodeEncodeError — otherwise the UTF-8 identity
is a vacuous ASCII-only test.
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
    bs = live["both_states"]
    ctrl = live["controls"]
    print(
        json.dumps(
            {
                "probe": "probe1-both-states",
                "unit_id": H.UNIT,
                "utf8_two_captures_identical": bs["utf8_two_captures_identical"],
                "utf8_matches_encode": bs["utf8_matches_encode"],
                "utf8_byte_exact": bs["utf8_byte_exact"],
                "utf8_sha256": bs["utf8_sha256"],
                "utf8_byte_count": bs["utf8_byte_count"],
                "strict_cp1252_raises": ctrl["strict_cp1252_raises"],
                "subprocess_utf8_byte_exact": bs["subprocess_utf8_byte_exact"],
            },
            sort_keys=True,
        )
    )
    print(
        f"utf8_byte_exact={bs['utf8_byte_exact']} "
        f"two_identical={bs['utf8_two_captures_identical']} "
        f"matches_encode={bs['utf8_matches_encode']} "
        f"sha256={bs['utf8_sha256']} bytes={bs['utf8_byte_count']}"
    )
    print(
        f"detector strict_cp1252_raises={ctrl['strict_cp1252_raises']} "
        f"subprocess_utf8_byte_exact={bs['subprocess_utf8_byte_exact']}"
    )
    if not bs["utf8_byte_exact"]:
        print("FAILED:TST-0249-probe1 UTF-8 console output is not byte-exact")
        return 1
    if not ctrl["strict_cp1252_raises"]:
        print("FAILED:TST-0249-probe1 strict cp1252 did not raise (vacuous payload)")
        return 1
    if not bs["subprocess_utf8_byte_exact"]:
        print("FAILED:TST-0249-probe1 production close.py UTF-8 stdout drifted from encode")
        return 1

    if not ART.is_file():
        print("FAILED:TST-0249-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if H.SENTINEL not in ART.read_text(encoding="utf-8"):
        print("FAILED:TST-0249-probe1 sentinel absent")
        return 1
    rec = doc.get("both_states") or {}
    if rec.get("utf8_sha256") != bs["utf8_sha256"]:
        print(
            f"FAILED:TST-0249-probe1 sha drift artifact={rec.get('utf8_sha256')} live={bs['utf8_sha256']}"
        )
        return 1
    if rec.get("utf8_byte_exact") is not True:
        print("FAILED:TST-0249-probe1 artifact both_states.utf8_byte_exact")
        return 1
    if rec.get("utf8_byte_count") != bs["utf8_byte_count"]:
        print("FAILED:TST-0249-probe1 byte_count drift")
        return 1
    print("SUCCESS:TST-0249-probe1 UTF-8 both-states byte-exact")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
