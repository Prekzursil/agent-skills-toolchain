#!/usr/bin/env python3
"""Named probe 1: both-states background reject + AND-gate.

Broken twin returns a job receipt as success. Repaired twin rejects before
the vendor is called and still requires exists+nonempty+parses for SUCCESS.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from dispatch import campaign  # noqa: E402

ART = REPO / "command-center/wfa/WFA-0090-repair-crossvendor-dispatch.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:WFA-0090-probe1 artifact missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("unit_id") != "WFA-0090":
        print("FAILED:WFA-0090-probe1 unit_id", doc.get("unit_id"))
        return 1
    text = json.dumps(doc)
    if "SUCCESS:WFA-0090" not in text:
        print("FAILED:WFA-0090-probe1 sentinel absent")
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:WFA-0090-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="wfa0090-p1-") as raw:
        live = campaign(Path(raw))

    bg = live["both_states_background"]
    if not bg.get("pass"):
        print("FAILED:WFA-0090-probe1 both-states background")
        print(json.dumps(bg, indent=2))
        return 1
    if not live.get("and_gate_exit0_insufficient"):
        print("FAILED:WFA-0090-probe1 AND-gate did not reject exit-0-only")
        return 1
    if not live.get("regex_independent_of_and_gate"):
        print("FAILED:WFA-0090-probe1 regex gate not independent of AND-gate")
        return 1
    if not live.get("healthy_success"):
        print("FAILED:WFA-0090-probe1 healthy path not SUCCESS")
        return 1

    recorded = (doc.get("before_after") or {}).get("background") or {}
    if not recorded.get("after_rejected"):
        print("FAILED:WFA-0090-probe1 artifact missing repaired reject")
        return 1

    payload = {
        "pass": True,
        "probe": "probe1-background-reject",
        "unit_id": "WFA-0090",
        "broken_accepted_receipt": bg["broken_accepted_receipt"],
        "repaired_rejected": bg["repaired_rejected"],
        "repaired_vendor_not_called": bg["repaired_vendor_not_called"],
        "and_gate_exit0_insufficient": True,
        "regex_independent_of_and_gate": True,
        "healthy_success": True,
        "computed_not_asserted": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        "broken_receipt=True repaired_rejected=True vendor_not_called=True "
        "and_gate=True regex_independent=True"
    )
    print("SUCCESS:WFA-0090-probe1 both-states background reject")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
