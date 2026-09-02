#!/usr/bin/env python3
"""Probe 1: unregistered write, absent path, and unparseable-but-present must fail.

Condition 12 is not an existence check: a file on disk that does not parse
with its declared consumer must FAIL. The library self-test is the table;
this probe also requires the live CC-0009 receipt to be registered and readable.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools" / "command-center"))

import artifact_register as AR  # noqa: E402

ART = "command-center/receipts/CC-0009.json"
NOT_DELIVERING = frozenset({"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"})


def main() -> int:
    rc = AR.self_test()
    if rc != 0:
        print("FAILED:CC-0009-probe1 library self-test")
        return 1

    art = REPO / ART
    if not art.is_file() or art.stat().st_size <= 0:
        print("FAILED:CC-0009-probe1 receipt missing")
        return 1
    text = art.read_text(encoding="utf-8")
    try:
        doc = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"FAILED:CC-0009-probe1 receipt unparseable: {exc}")
        return 1
    if not isinstance(doc, dict):
        print("FAILED:CC-0009-probe1 receipt is not an object")
        return 1
    st = str(doc.get("state") or "").upper()
    if st in NOT_DELIVERING:
        print(f"FAILED:CC-0009-probe1 self-declared {st}")
        return 1
    if "SUCCESS:CC-0009" not in text:
        print("FAILED:CC-0009-probe1 sentinel absent")
        return 1

    c11 = AR.check_condition_11(REPO, unit_id="CC-0009", output_path=ART)
    c12 = AR.check_condition_12(REPO, unit_id="CC-0009", output_path=ART)
    print(f"live_c11 {c11.result}: {c11.reason}")
    print(f"live_c12 {c12.result}: {c12.reason}")
    readings = c12.evidence.get("readings") or []
    for item in readings:
        print(
            f"  reader={item.get('reader')} path={item.get('path')} "
            f"first_key={item.get('first_parsed_key')!r} "
            f"records={item.get('record_count')}"
        )
    if not c11.ok:
        print("FAILED:CC-0009-probe1 live condition 11")
        return 1
    if not c12.ok:
        print("FAILED:CC-0009-probe1 live condition 12")
        return 1
    if not readings or not readings[0].get("first_parsed_key"):
        print("FAILED:CC-0009-probe1 consumer did not report a first parsed key")
        return 1

    tests = doc.get("tests") or []
    required = {
        "unregistered-write-fails-c11",
        "absent-path-fails-c12",
        "unparseable-present-fails-c12",
        "valid-entries-pass-both-states",
    }
    ids = {t.get("id") for t in tests if isinstance(t, dict)}
    missing = required - ids
    if missing:
        print(f"FAILED:CC-0009-probe1 receipt missing tests {sorted(missing)}")
        return 1
    failed_tests = [
        t.get("id")
        for t in tests
        if isinstance(t, dict) and str(t.get("result") or "").upper() != "PASS"
    ]
    if failed_tests:
        print(f"FAILED:CC-0009-probe1 receipt tests not PASS: {failed_tests}")
        return 1

    print("SUCCESS:CC-0009-probe1 unregistered/absent/unparseable fail; live c11+c12 pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
