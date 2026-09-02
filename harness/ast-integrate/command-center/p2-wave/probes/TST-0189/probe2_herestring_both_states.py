#!/usr/bin/env python3
"""Named probe 2: both-states here-string control (independent of probe1).

Good state: write API argv does not contain the quoted destructive command and
bytes match. Bad state: the same payload in a Set-Content here-string is
truncated on '@ and the payload is visible to a command scanner
(windows-shell.md:9).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import (  # noqa: E402
    SENTINEL,
    UNIT_ID,
    load_receipt,
    measure,
)


def main() -> int:
    ev = measure()
    hs = ev["here_string_control"]
    api = ev["write_api"]
    doc = load_receipt()
    evidence = doc.get("evidence") or {}

    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:{UNIT_ID}-probe2 self-declared {doc.get('state')}")
        return 1
    if SENTINEL not in json.dumps(doc):
        print(f"FAILED:{UNIT_ID}-probe2 sentinel absent")
        return 1

    if not hs["corrupted_or_blocked"]:
        print("FAILED:TST-0189-probe2 here-string route did not corrupt or block")
        return 1
    if hs["written_sha256"] == ev["intended_sha256"]:
        print("FAILED:TST-0189-probe2 here-string wrote intended bytes (control silent)")
        return 1
    if not hs["terminated_early"]:
        print("FAILED:TST-0189-probe2 closer token did not terminate the here-string")
        return 1
    if not hs["payload_scanned_as_command"]:
        print("FAILED:TST-0189-probe2 here-string payload not scanned as a command")
        return 1
    if api["payload_scanned_as_command"]:
        print("FAILED:TST-0189-probe2 write-API argv scanned as a command")
        return 1
    if not api["round_trip_exact"]:
        print("FAILED:TST-0189-probe2 write API failed while here-string was measured")
        return 1
    if not evidence.get("here_string_corrupted_or_blocked"):
        print("FAILED:TST-0189-probe2 receipt missing here-string control")
        return 1
    if not evidence.get("here_string_payload_scanned_as_command"):
        print("FAILED:TST-0189-probe2 receipt missing payload-scanned-as-command")
        return 1
    if evidence.get("write_api_payload_scanned_as_command"):
        print("FAILED:TST-0189-probe2 receipt claims write API was scanned")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-herestring-both-states",
                "unit_id": UNIT_ID,
                "here_string_corrupted": hs["corrupted"],
                "terminated_early": hs["terminated_early"],
                "payload_scanned_as_command": True,
                "write_api_clean_argv": True,
                "write_api_round_trip": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"SUCCESS:{UNIT_ID}-probe2 here-string both-states "
        "(corrupt/scan vs write-API exact/unscanned)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
