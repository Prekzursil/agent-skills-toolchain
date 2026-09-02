#!/usr/bin/env python3
"""Probe 1: enumerator finds a plugin known to be installed.

Known-present is hookify, planted with plugin.json AND in the captured
``claude plugin list``. Both signals must hit. Live ~/.claude is scanned
separately and must not be treated as the detector-control estate.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import enumerate as E  # noqa: E402
import estate as EST  # noqa: E402
import live as L  # noqa: E402

ART = REPO / "command-center/research/teardown/RES-0177-teardown-installed-local-plugins.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:RES-0177-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print("FAILED:RES-0177-probe1 unparseable", exc)
        return 1
    if "SUCCESS:RES-0177" not in text:
        print("FAILED:RES-0177-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0177-probe1 self-declared", doc.get("state"))
        return 1

    bundle = EST.load_estate()
    disk = E.disk_plugins(bundle["plugins_root"])
    listing = E.listing_plugins(bundle["listing_json"], bundle["listing_text"])
    hit = E.query(bundle["known_present"], disk, listing)
    if not hit["disk"]:
        print("FAILED:RES-0177-probe1 known plugin missing from disk", bundle["known_present"])
        return 1
    if not hit["listing"]:
        print("FAILED:RES-0177-probe1 known plugin missing from listing", bundle["known_present"])
        return 1
    if not hit["present"]:
        print("FAILED:RES-0177-probe1 known plugin not in both-signal join")
        return 1

    live = L.scan_live()
    recorded = doc.get("detector_control") or {}
    if recorded.get("known_present") != bundle["known_present"]:
        print("FAILED:RES-0177-probe1 artifact known_present mismatch")
        return 1
    if recorded.get("known_found") is not True:
        print("FAILED:RES-0177-probe1 artifact did not record known_found")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-known-present",
        "unit_id": "RES-0177",
        "known_present": bundle["known_present"],
        "hit": hit,
        "disk_names": sorted(disk),
        "listing_names": sorted(listing),
        "live_verdict": live["verdict"],
        "live_install_present": live["live_install_present"],
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"known={bundle['known_present']} disk={hit['disk']} listing={hit['listing']} "
        f"present={hit['present']} live={live['verdict']}"
    )
    print("SUCCESS:RES-0177-probe1 known-installed found by both signals")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
