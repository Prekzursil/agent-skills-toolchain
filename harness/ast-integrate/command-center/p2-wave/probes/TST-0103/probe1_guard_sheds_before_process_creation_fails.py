#!/usr/bin/env python3
"""Probe 1: guard sheds load before process creation fails.

Catalog test: test_guard_sheds_load_before_process_creation_fails
Samples commit-charge and available-commit on the ramp; shed is timestamped
(logical ramp time) before the unguarded process-creation failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from checks import probe1_live  # noqa: E402

ART = REPO / "command-center/receipts/TST-0103.json"
SENTINEL = "SUCCESS:TST-0103"


def _check_receipt(live: dict) -> list[str]:
    errors: list[str] = []
    if not ART.is_file():
        errors.append("receipt missing")
        return errors
    try:
        doc = json.loads(ART.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"receipt unparseable: {type(exc).__name__}")
        return errors
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"receipt self-declared {doc.get('state')}")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        errors.append("sentinel absent from receipt")
    ramp = doc.get("ramp") or {}
    live_ord = live.get("ordering") or {}
    art_ord = ramp.get("ordering") or {}
    for key in (
        "shed_step",
        "fail_step",
        "shed_before_fail",
        "guarded_rescue_spawn_succeeded",
        "unguarded_process_creation_failed",
        "working_set_guard_did_not_shed",
    ):
        if live_ord.get(key) != art_ord.get(key):
            errors.append(f"receipt ordering.{key} != live {art_ord.get(key)!r} vs {live_ord.get(key)!r}")
    shed = (ramp.get("guarded") or {}).get("shed") or {}
    if "commit_charge" not in shed or "available_commit" not in shed:
        errors.append("receipt shed event missing the two required counters")
    return errors


def main() -> int:
    live, errors = probe1_live()
    ord_ = live.get("ordering") or {}
    print(
        json.dumps(
            {
                "probe": "probe1",
                "shed_step": ord_.get("shed_step"),
                "fail_step": ord_.get("fail_step"),
                "shed_before_fail": ord_.get("shed_before_fail"),
                "rescue_ok": ord_.get("guarded_rescue_spawn_succeeded"),
                "unguarded_failed": ord_.get("unguarded_process_creation_failed"),
                "ws_guard_silent": ord_.get("working_set_guard_did_not_shed"),
            },
            sort_keys=True,
        )
    )
    if ART.is_file():
        errors.extend(_check_receipt(live))
    if errors:
        for e in errors:
            print(f"FAILED:TST-0103-probe1 {e}")
        return 1
    print("SUCCESS:TST-0103-probe1 guard sheds before process-creation failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
