#!/usr/bin/env python3
"""Named probe 2: independent reviewer re-runs the detector controls."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from consumers import CONSUMERS, artifact_payload  # noqa: E402
from inventory import inventory  # noqa: E402
from measure import corruption_control, payload_records_control  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0123-downstream-readability.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 200:
        print("FAILED:CNF-0123-probe2 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if "SUCCESS:CNF-0123" not in json.dumps(doc):
        print("FAILED:CNF-0123-probe2 sentinel absent")
        return 1

    payload = payload_records_control()
    if not payload["schema_valid_unreadable"]:
        print("FAILED:CNF-0123-probe2 unreadable fixture is not schema-valid")
        return 1
    if not payload["schema_valid_readable"]:
        print("FAILED:CNF-0123-probe2 readable fixture is not schema-valid")
        return 1
    if payload["unreadable_exit_code"] == 0:
        print("FAILED:CNF-0123-probe2 unreadable fixture was consumed")
        return 1
    if payload["readable_exit_code"] != 0:
        print("FAILED:CNF-0123-probe2 readable fixture was rejected")
        return 1
    if not payload["detector_fired"]:
        print("FAILED:CNF-0123-probe2 both-states detector inert")
        print(json.dumps(payload, indent=2)[:1500])
        return 1

    corrupt = corruption_control()
    if corrupt["intact_exit_code"] != 0:
        print("FAILED:CNF-0123-probe2 intact consumer did not pass")
        return 1
    if corrupt["corrupt_exit_code"] == 0:
        print("FAILED:CNF-0123-probe2 corrupt consumer did not fail")
        return 1
    if not corrupt["failed"]:
        print("FAILED:CNF-0123-probe2 corruption control did not fail")
        return 1

    planted = next(
        (r for r in inventory() if r["class_id"] == "planted-unconsumed"), None
    )
    if planted is None:
        print("FAILED:CNF-0123-probe2 planted class missing from inventory")
        return 1
    if planted["class_id"] in CONSUMERS:
        print("FAILED:CNF-0123-probe2 planted class has a consumer")
        return 1
    body = artifact_payload(doc)
    art_planted = [
        r
        for r in (body.get("classes") or [])
        if r.get("class_id") == "planted-unconsumed"
    ]
    if not art_planted or art_planted[0].get("finding") != "unconsumed":
        print("FAILED:CNF-0123-probe2 planted class not unconsumed in artifact")
        return 1

    art_ctrl = body.get("corruption_control") or {}
    if art_ctrl.get("failed") is not True:
        print("FAILED:CNF-0123-probe2 artifact corruption_control.failed is not true")
        return 1

    print(
        json.dumps(
            {
                "probe": "probe2-detector-control",
                "unit_id": "CNF-0123",
                "schema_valid_unreadable_rejected": True,
                "schema_valid_readable_accepted": True,
                "corruption_failed": True,
                "planted_unconsumed": True,
                "pass": True,
            },
            sort_keys=True,
        )
    )
    print(
        f"unreadable_exit={payload['unreadable_exit_code']} "
        f"readable_exit={payload['readable_exit_code']} "
        f"corrupt_exit={corrupt['corrupt_exit_code']}"
    )
    print("SUCCESS:CNF-0123-probe2 detector control re-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
