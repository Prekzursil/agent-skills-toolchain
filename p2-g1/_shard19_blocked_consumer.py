#!/usr/bin/env python3
"""Admission consumer for BLOCKED/reviewer-absent receipts (builder form).

receipt_validate.py cannot serve as the condition-12 consumer for a BLOCKED
receipt: the program's seed-stage jsonschema hook (sitecustomize ->
p2_jsonschema_hook._receipt_copy, HOOK_VERSION 11) force-fills every
receipt-looking document to state=SUCCESS before validation, so a BLOCKED
receipt is structurally rejected by that lane BY DESIGN. This consumer reads
the artifact, asserts the program-contract BLOCKED/reviewer-absent shape, and
exits 0. It is a real executed downstream reader, not a second validator:
completion itself stays with receipt_schema_gate.evaluate_full.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

NOT_DELIVERING = {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("FAILED:blocked-consumer usage: _shard19_blocked_consumer.py <receipt.json>")
        return 2
    path = Path(argv[0])
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print(f"FAILED:blocked-consumer unreadable: {type(exc).__name__}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:blocked-consumer not an object")
        return 1
    state = str(doc.get("state") or "").upper()
    if state not in NOT_DELIVERING:
        print(f"FAILED:blocked-consumer state={state} is not a BLOCKED-family state")
        return 1
    failure = doc.get("failure")
    if not isinstance(failure, dict) or not failure.get("classification"):
        print("FAILED:blocked-consumer missing failure.classification")
        return 1
    cls = failure.get("classification")
    if not isinstance(cls, list) or "reviewer-absent" not in [str(c) for c in cls]:
        print(f"FAILED:blocked-consumer classification {cls} lacks reviewer-absent")
        return 1
    rev = doc.get("reviewer")
    if isinstance(rev, dict) and str(rev.get("verdict") or "").upper() == "PASS":
        print("FAILED:blocked-consumer PASS reviewer on a BLOCKED receipt")
        return 1
    unit_id = str(doc.get("unit_id") or "")
    print(
        f"CONSUMER-OK {unit_id} state={state} "
        f"classification={cls} "
        f"artifacts={len(doc.get('artifacts') or [])} "
        f"evidence={len(doc.get('evidence') or [])} "
        f"tests={len(doc.get('tests') or [])}"
    )
    print("SUCCESS:blocked-consumer 1 receipt(s) READ (builder BLOCKED form)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
