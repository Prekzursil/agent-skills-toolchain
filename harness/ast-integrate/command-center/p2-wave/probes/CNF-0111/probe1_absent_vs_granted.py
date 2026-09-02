#!/usr/bin/env python3
"""Named probe 1: live absent-vs-granted matrix plus granted control.

Re-runs the product and detector-control matrices. Compares fingerprints to
the confirmation artifact. Requires the granted control to succeed and the
detector to block absent grants.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from measure import empty_cells, fingerprint, measure  # noqa: E402
from schema_util import payload  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0111-runtime-permission-enforcement.json"
UID = "CNF-0111"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0111-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rep = payload(doc)
    if doc.get("unit_id") != UID:
        print("FAILED:CNF-0111-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:CNF-0111-probe1 self-declared", doc.get("state"))
        return 1
    live = measure()
    if empty_cells(live["matrix"]) or empty_cells(live["detector_control"]):
        print("FAILED:CNF-0111-probe1 empty cells")
        return 1
    if not live["control"]["granted_actions_succeeded"]:
        print("FAILED:CNF-0111-probe1 granted control failed")
        return 1
    if not live["control"]["detector_absent_blocked"]:
        print("FAILED:CNF-0111-probe1 detector did not block absent grants")
        return 1
    if not live["control"]["product_absent_open"]:
        print("FAILED:CNF-0111-probe1 product layer unexpectedly blocked")
        return 1
    if fingerprint(live["matrix"]) != fingerprint(rep.get("matrix") or []):
        print("FAILED:CNF-0111-probe1 product matrix fingerprint mismatch")
        print(json.dumps({"live": live["fingerprint_product"], "art": rep.get("fingerprint_product")}, indent=2)[:3000])
        return 1
    if fingerprint(live["detector_control"]) != fingerprint(rep.get("detector_control") or []):
        print("FAILED:CNF-0111-probe1 detector fingerprint mismatch")
        return 1
    granted = [
        c
        for c in live["matrix"] + live["detector_control"]
        if c["granted"] and c["action"] != "write-outside-root"
    ]
    summary = {
        "probe": "probe1-absent-vs-granted",
        "unit_id": UID,
        "pass": True,
        "product_cells": len(live["matrix"]),
        "detector_cells": len(live["detector_control"]),
        "granted_succeeded": all(c["observed"] == "succeeded" for c in granted),
        "detector_absent_blocked": live["control"]["detector_absent_blocked"],
        "product_absent_open": live["control"]["product_absent_open"],
        "empty_cells": 0,
        "isolates_enforcement": live["control"]["isolates_enforcement"],
    }
    print(json.dumps(summary, sort_keys=True))
    print(
        "granted_ok=True detector_blocks=True product_open=True "
        f"cells={len(live['matrix'])}+{len(live['detector_control'])}"
    )
    print("SUCCESS:CNF-0111-probe1 absent-vs-granted matrix")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
