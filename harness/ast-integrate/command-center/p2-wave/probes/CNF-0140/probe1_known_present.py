#!/usr/bin/env python3
"""Probe 1: known-present / deleted-gap / cross-registry parse."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import controls as C  # noqa: E402
import overclaim as O  # noqa: E402

ART = REPO / "command-center/receipts/CNF-0140.json"


def main() -> int:
    kp = C.known_present()
    xr = C.cross_registry()
    sc = C.spotcheck_five()
    checks = [
        ("present_ok", kp.get("present_ok")),
        ("deleted_ok", kp.get("deleted_ok")),
        ("p2_excluded", kp.get("p2_excluded")),
        ("ungraded_named", kp.get("ungraded_named")),
        ("counts_ok", kp.get("counts_ok")),
        ("cross_registry_ok", xr.get("ok")),
        ("spotcheck_five", sc.get("ok")),
        ("known_present_bundle", kp.get("ok")),
    ]
    for name, ok in checks:
        print(f"{name}={ok}")
        if not ok:
            print(f"FAILED:CNF-0140-probe1 {name}")
            if name == "cross_registry_ok":
                print(f"  why={xr.get('why')}")
            return 1

    if not ART.is_file():
        print("FAILED:CNF-0140-probe1 receipt missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0140" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0140-probe1 sentinel absent")
        return 1
    ok, why = O.check_overclaim(doc)
    print(f"artifact_overclaim_ok={ok} {why}")
    if not ok:
        print("FAILED:CNF-0140-probe1 overclaim on live artifact")
        return 1
    ledger = (doc.get("census") or {}).get("ledger")
    if not isinstance(ledger, list):
        print("FAILED:CNF-0140-probe1 live ledger missing")
        return 1
    counts = doc.get("counts") or {}
    if "registry_p0_p1_count" not in counts or "records_directory_listing_count" not in counts:
        print("FAILED:CNF-0140-probe1 second-signal counts missing")
        return 1
    print(
        "resolved={0} gaps={1} listing_unparseable={2}".format(
            kp["resolved_count"],
            kp["gap_count"],
            xr.get("unparseable_files"),
        )
    )
    print("SUCCESS:CNF-0140-probe1 known-present deleted-gap cross-registry")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
