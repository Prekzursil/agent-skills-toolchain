#!/usr/bin/env python3
"""Named probe 1: detector control — planted NFD id must be found.

test_detector_finds_a_planted_nfd_id. Live non-ASCII count is recorded, not
asserted; a zero is accepted only because the planted pair hit.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
TOOLS = REPO / "tools" / "command-center"
sys.path.insert(0, str(TOOLS))

import census as C  # noqa: E402
import detector as D  # noqa: E402
import id_normalize as inn  # noqa: E402

ART = REPO / "command-center/receipts/TST-0057.json"
OUT = HERE / "probe1-planted-nfd.raw.json"
SENTINEL = "SUCCESS:TST-0057"


def check_artifact() -> str | None:
    if not ART.is_file():
        return None
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return "artifact sentinel absent"
    doc = json.loads(text)
    if str(doc.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        return f"artifact self-declared {doc.get('state')}"
    det = doc.get("detector") or {}
    if det.get("planted_hit") is not True:
        return "receipt detector.planted_hit is not true"
    census = doc.get("census") or {}
    live = C.run_census()
    if int(census.get("non_ascii_count", -1)) != int(live["non_ascii_count"]):
        return (
            "receipt non_ascii_count "
            f"{census.get('non_ascii_count')!r} != live {live['non_ascii_count']!r}"
        )
    if int(census.get("live_nfc_collision_count", -1)) != int(
        live["live_nfc_collision_count"]
    ):
        return "receipt live_nfc_collision_count drifted from live census"
    if live["non_ascii_count"] == 0 and det.get("planted_hit") is not True:
        return "zero non-ASCII claimed without planted hit"
    return None


def main() -> int:
    planted = D.detect_planted()
    live = C.run_census()
    payload = {
        "planted": planted,
        "live_non_ascii_count": live["non_ascii_count"],
        "live_nfc_collision_count": live["live_nfc_collision_count"],
        "live_record_count": live["record_count"],
        "option_id_resolution_present": live["option_id_resolution"]["present"],
    }
    OUT.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    if not planted["planted_hit"]:
        print("FAILED:TST-0057-probe1 planted NFD pair not detected")
        return 1
    if not planted["ascii_id_not_colliding"]:
        print("FAILED:TST-0057-probe1 ASCII TST-0057 falsely collided")
        return 1
    if planted["pair"]["nfc"] == planted["pair"]["nfd"]:
        print("FAILED:TST-0057-probe1 planted pair not byte-distinct")
        return 1
    if inn.canonical_id(planted["pair"]["nfd"]) != planted["pair"]["nfc"]:
        print("FAILED:TST-0057-probe1 NFD does not NFC-fold to NFC plant")
        return 1
    silent = D.detect(["TST-0057", "ARC-0016", "R-A01"])
    if silent:
        print(f"FAILED:TST-0057-probe1 false positive on ASCII ids {silent}")
        return 1
    art = check_artifact()
    if art:
        print(f"FAILED:TST-0057-probe1 {art}")
        return 1
    print(
        json.dumps(
            {
                "planted_hit": True,
                "live_non_ascii_count": live["non_ascii_count"],
                "live_nfc_collision_count": live["live_nfc_collision_count"],
                "live_record_count": live["record_count"],
            },
            ensure_ascii=True,
        )
    )
    print(
        "SUCCESS:TST-0057-probe1 detector found planted NFD id; "
        f"live non-ASCII={live['non_ascii_count']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
