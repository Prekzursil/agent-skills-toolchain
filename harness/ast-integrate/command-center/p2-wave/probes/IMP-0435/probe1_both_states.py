#!/usr/bin/env python3
"""Named probe 1: both-states CI gate (invalid receipt red, valid green)."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import scenario as S  # noqa: E402

ART = S.REPO / S.OUT


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:IMP-0435-probe1 receipt missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if S.SENTINEL not in text:
        print("FAILED:IMP-0435-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    if doc.get("unit_id") != "IMP-0435":
        print("FAILED:IMP-0435-probe1 unit_id", doc.get("unit_id"))
        return 1
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:IMP-0435-probe1 self-declared", doc.get("state"))
        return 1

    with tempfile.TemporaryDirectory(prefix="imp0435-p1-") as tmp:
        both = S.both_states(Path(tmp))
    wiring = S.workflow_wiring()
    payload = {
        "probe": "probe1-both-states-gate",
        "unit_id": "IMP-0435",
        "pass": bool(both["pass"] and wiring["invokes_receipt_validate"]),
        "green_exit": both["green"]["exit_code"],
        "red_exit": both["red"]["exit_code"],
        "red_failing_step": both["red"]["failing_step"],
        "red_failed_at_validator": both["red"]["failed_at_validator"],
        "green_run_id": both["green"]["run_id"],
        "red_run_id": both["red"]["run_id"],
        "empty_walk_rejected": (not both["empty"]["lib_ok"]) and both["empty"]["c0"],
        "live_default_argv_ok": both["live_default_argv"]["ok"],
        "workflow_step": wiring["step_name"],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["pass"]:
        print("FAILED:IMP-0435-probe1 both-states gate")
        print("green", both["green"]["output_tail"][-500:])
        print("red", both["red"]["output_tail"][-500:])
        return 1
    print(
        f"green_rc={both['green']['exit_code']} red_rc={both['red']['exit_code']} "
        f"failing_step={both['red']['failing_step']}"
    )
    print("SUCCESS:IMP-0435-probe1 both-states gate red-on-invalid green-on-valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
