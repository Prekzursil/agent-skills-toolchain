#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0189.json from live measurements."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from contract import RECEIPT, SENTINEL, UNIT_ID, assert_pass, measure  # noqa: E402


def build_receipt(ev: dict) -> dict:
    errors = assert_pass(ev)
    passed = not errors
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    api = ev["write_api"]
    hs = ev["here_string_control"]
    st = ev["static_scan"]
    state = "SUCCESS" if passed else "FAILED"
    return {
        "id": UNIT_ID,
        "unit_id": UNIT_ID,
        "profile": "shell_report",
        "state": state,
        "status": "DELIVERED" if passed else "FAILED",
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "title": "File creation never routes through a here-string payload",
        "question": (
            "Does the toolchain create files via a write API rather than a "
            "shell here-string, so a document quoting a destructive command "
            "is not scanned as one, and @' / '@ sequences round-trip? PASS "
            "requires a byte-exact round trip of a document containing both "
            "terminators."
        ),
        "answer": (
            "Yes. tools/lib/codex-invocation.mjs writeFileViaApi landed the "
            f"document byte-exact (sha256={api['landed_sha256']}). The same "
            "bytes inlined into a Set-Content here-string terminated early on "
            "'@ and left Remove-Item / rm -rf in command text, so a command "
            "scanner fired. Static scan of tools/lib/ found "
            f"{st['here_string_file_create_sites']} here-string file-creation "
            "sites."
            if passed
            else f"No. Failures: {errors}"
        ),
        "verdict": "PASS" if passed else "FAIL",
        "measured_at": now,
        "execution_substrate": "linux-local (PowerShell here-string semantics emulated; payload-scanned-as-command measured on constructed command text)",
        "evidence": {
            "write_api_sha256_match": api["round_trip_exact"]
            and api["landed_sha256"] == ev["intended_sha256"],
            "intended_sha256": ev["intended_sha256"],
            "landed_sha256": api["landed_sha256"],
            "static_scan_here_string_file_create_sites": st[
                "here_string_file_create_sites"
            ],
            "here_string_corrupted_or_blocked": hs["corrupted_or_blocked"],
            "here_string_payload_scanned_as_command": hs[
                "payload_scanned_as_command"
            ],
            "write_api_payload_scanned_as_command": api[
                "payload_scanned_as_command"
            ],
            "payload_contains_both_terminators": ev["payload_contains_opener"]
            and ev["payload_contains_closer"],
        },
        "tests": [
            {
                "id": "TST-0189-WRITE-API-ROUNDTRIP",
                "name": "byte-exact round trip of a document containing @' and '@",
                "result": "PASS" if api["round_trip_exact"] else "FAIL",
            },
            {
                "id": "TST-0189-STATIC-SCAN",
                "name": "zero here-string file-creation sites under tools/lib/",
                "result": "PASS"
                if st["here_string_file_create_sites"] == 0
                else "FAIL",
            },
            {
                "id": "TST-0189-HERESSTRING-BOTH-STATES",
                "name": "here-string route corrupts or blocks the same content",
                "result": "PASS" if hs["corrupted_or_blocked"] else "FAIL",
            },
            {
                "id": "TST-0189-PAYLOAD-NOT-SCANNED",
                "name": "quoted destructive command is scanned on here-string command text and not on write-API argv",
                "result": "PASS"
                if hs["payload_scanned_as_command"]
                and not api["payload_scanned_as_command"]
                else "FAIL",
            },
            {
                "id": "TST-0189-REGRESSION-SEED",
                "name": "windows-shell.md:9 here-string PAYLOAD scanned as a command",
                "result": "PASS" if hs["payload_scanned_as_command"] else "FAIL",
            },
        ],
        "live": ev,
        "reviewer": {
            "reviewer_id": "TST-0189-probe2-both-states",
            "verdict": "PASS" if passed else "FAIL",
            "independent": True,
            "notes": (
                "Named probe2 re-runs the here-string both-states control "
                "independently of probe1. pwsh7/Git Bash are not installed on "
                "this Linux worktree; here-string termination is emulated and "
                "the scanner runs on the constructed Set-Content script text."
            ),
        },
        "schema": "command-center/schema/receipt.schema.json#/$defs/shell_report",
        "errors": errors,
        SENTINEL: True,
    }


def main() -> int:
    ev = measure()
    doc = build_receipt(ev)
    RECEIPT.parent.mkdir(parents=True, exist_ok=True)
    RECEIPT.write_text(
        json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    errors = doc.get("errors") or []
    if errors or doc.get("state") != "SUCCESS":
        print(f"FAILED:{UNIT_ID} {errors}")
        return 1
    print(f"{SENTINEL} wrote {RECEIPT.relative_to(RECEIPT.parents[2])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
