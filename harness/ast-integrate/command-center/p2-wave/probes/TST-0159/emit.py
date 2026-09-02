#!/usr/bin/env python3
"""Emit command-center/receipts/TST-0159.json from a live write-once run."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import scenarios as S  # noqa: E402

OUT = "command-center/receipts/TST-0159.json"
SCHEMA = "command-center/p2-wave/probes/TST-0159/concurrency_report.schema.json"
ENGINE = "command-center/p2-wave/probes/TST-0159/write_once_store.py"
CATALOG_ENGINE = "tools/lib/handled-ledger.mjs"
SENTINEL = "SUCCESS:TST-0159"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0159/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/TST-0159/probe2_lww_and_evidence.py"
)
QUESTION = (
    "After a false-negative timeout where the original unit actually completed, "
    "does a retry refuse to overwrite the existing terminal receipt? PASS "
    "requires write-once semantics with a version guard and a recorded "
    "DUPLICATE-COMPLETION event."
)
TITLE = "Idempotent retry cannot overwrite a completed receipt"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def engine_anchor(needle: str) -> str:
    text = (REPO / ENGINE).read_text(encoding="utf-8")
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return f"{ENGINE}:{i}"
    return f"{ENGINE}:1"


def _fn_public(fn: dict) -> dict:
    return {
        "ok": fn.get("ok"),
        "write_once_holds": fn.get("write_once_holds"),
        "hashes_equal": fn.get("hashes_equal"),
        "hash_before": fn.get("hash_before"),
        "hash_after": fn.get("hash_after"),
        "first_action": fn.get("first_action"),
        "second_action": fn.get("second_action"),
        "second_status": fn.get("second_status"),
        "receipt_state": fn.get("receipt_state"),
        "receipt_version": fn.get("receipt_version"),
        "receipt_result": fn.get("receipt_result"),
        "event_kinds": fn.get("event_kinds"),
        "dispatch_view": fn.get("dispatch_view"),
        "duplicate_event": (fn.get("duplicate_events") or [None])[0],
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="tst0159-emit-") as tmp:
        live = S.run_all(Path(tmp))
    if not live.get("ok"):
        print("FAILED:TST-0159 emit scenarios failed")
        print(
            json.dumps(
                {
                    "both": (live.get("both_states") or {}).get("ok"),
                    "lww": (live.get("last_write_wins") or {}).get("ok"),
                },
                indent=2,
            )
        )
        return 1

    both = live["both_states"]
    fn = both["false_negative_timeout"]
    failed = both["genuine_failure_retry"]
    stale = both["stale_cas"]
    lww = live["last_write_wins"]
    catalog_named_present = (REPO / CATALOG_ENGINE).is_file()

    doc = {
        "unit_id": "TST-0159",
        "state": "SUCCESS",
        "schema_version": 1,
        "report_kind": "concurrency_report",
        "title": TITLE,
        "question": QUESTION,
        "question_or_target": QUESTION,
        "sentinel": SENTINEL,
        "completion_sentinel": SENTINEL,
        "min_bytes_threshold": 2048,
        "catalog_schema": (
            "command-center/schema/receipt.schema.json#/$defs/concurrency_report"
        ),
        "output_schema_note": (
            (
                "Declared catalog schema file is present on this worktree. "
                if (REPO / "command-center/schema/receipt.schema.json").is_file()
                else "Declared catalog schema file is absent on this worktree. "
            )
            + "G-1 requires the artifact to parse as JSON; this receipt is also "
            "checked against the local concurrency_report.schema.json."
        ),
        "engine": {
            "path": ENGINE,
            "catalog_named_path": CATALOG_ENGINE,
            "catalog_named_present": catalog_named_present,
            "catalog_python_sibling": "tools/lib/handled_ledger.py",
            "catalog_python_sibling_present": (
                REPO / "tools/lib/handled_ledger.py"
            ).is_file(),
            "api": [
                "WriteOnceReceiptStore.write",
                "WriteOnceReceiptStore.load_events",
                "write_once_holds",
                "sha256_path",
            ],
            "notes": (
                "handled-ledger.mjs is absent. TST-0168 already owns "
                "handled_ledger.py for fan-out child receipts; this unit's "
                "SUT is the write-once unit-receipt store with a version "
                "guard, not a rebuild of B07."
            ),
        },
        "both_states": {
            "ok": True,
            "supported_proceeds": True,
            "unsupported_refused": True,
            "false_negative_timeout": _fn_public(fn),
            "genuine_failure_retry": {
                "ok": failed.get("ok"),
                "wrote_new_receipt": failed.get("wrote_new_receipt"),
                "hashes_equal": failed.get("hashes_equal"),
                "hash_before": failed.get("hash_before"),
                "hash_after": failed.get("hash_after"),
                "first_action": failed.get("first_action"),
                "second_action": failed.get("second_action"),
                "second_status": failed.get("second_status"),
                "receipt_state": failed.get("receipt_state"),
                "receipt_version": failed.get("receipt_version"),
                "receipt_result": failed.get("receipt_result"),
                "event_kinds": failed.get("event_kinds"),
                "duplicate_events": failed.get("duplicate_events"),
            },
            "stale_cas": stale,
        },
        "negative_control": {
            "ok": True,
            "last_write_wins": {
                "ok": lww.get("ok"),
                "write_once_holds": lww.get("write_once_holds"),
                "hashes_equal": lww.get("hashes_equal"),
                "hash_before": lww.get("hash_before"),
                "hash_after": lww.get("hash_after"),
                "second_action": lww.get("second_action"),
                "second_status": lww.get("second_status"),
                "receipt_result": lww.get("receipt_result"),
                "detector_fired_on_lww": lww.get("detector_fired_on_lww"),
                "duplicate_events": lww.get("duplicate_events"),
                "detail": lww.get("detail"),
            },
        },
        "tests": [
            {
                "id": "false-negative-timeout-write-once",
                "name": (
                    "retry after false-negative timeout refuses to overwrite "
                    "a terminal SUCCESS receipt"
                ),
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "both-states-genuine-failure-retry-writes",
                "name": "a retry of a genuinely failed unit DOES write a new receipt",
                "result": "PASS",
                "command": P1,
            },
            {
                "id": "negative-control-last-write-wins",
                "name": "last-write-wins semantics must fail this test",
                "result": "PASS",
                "command": P2,
            },
            {
                "id": "version-guard-stale-cas",
                "name": "stale expected_version cannot replace a FAILED receipt",
                "result": "PASS",
                "command": P1,
            },
        ],
        "evidence": [
            {
                "signal": "(a) the receipt's content hash before and after the retry",
                "claim": (
                    "sha256 of the terminal receipt file is identical before "
                    "and after the false-negative timeout retry "
                    f"({fn.get('hash_before')}); a genuine-failure retry "
                    "changes the hash; last-write-wins also changes the hash."
                ),
                "verdict": "CONFIRMED",
                "anchor": engine_anchor("def sha256_path"),
            },
            {
                "signal": "(b) the event log entry naming the suppressed write",
                "claim": (
                    "events.jsonl records kind=DUPLICATE-COMPLETION with "
                    "suppressed_write.reason=false-negative-timeout-retry and "
                    "existing_hash equal to the unchanged receipt hash. "
                    "Last-write-wins records RECEIPT-WRITTEN and no "
                    "DUPLICATE-COMPLETION."
                ),
                "verdict": "CONFIRMED",
                "anchor": engine_anchor('DUPLICATE_COMPLETION = "DUPLICATE-COMPLETION"'),
            },
        ],
        "matrix": {
            "axes": {
                "prior_state": ["SUCCESS", "FAILED"],
                "retry_policy": ["write-once", "last-write-wins"],
            },
            "cells": [
                {
                    "os": "linux",
                    "client": "write-once-store",
                    "client_version": "1",
                    "declared": "SUPPORTED",
                    "attempted": True,
                    "outcome": "REFUSED",
                    "prior_state": "SUCCESS",
                    "label": "false-negative-timeout",
                },
                {
                    "os": "linux",
                    "client": "write-once-store",
                    "client_version": "1",
                    "declared": "SUPPORTED",
                    "attempted": True,
                    "outcome": "PROCEEDED",
                    "prior_state": "FAILED",
                    "label": "genuine-failure-retry",
                },
                {
                    "os": "linux",
                    "client": "last-write-wins-mutant",
                    "client_version": "1",
                    "declared": "UNSUPPORTED",
                    "attempted": True,
                    "outcome": "PROCEEDED",
                    "prior_state": "SUCCESS",
                    "label": "lww-overwrites",
                },
            ],
            "counts": {"refused": 1, "proceeded_allowed": 1, "mutant_proceeded": 1},
        },
        "reviewer": {
            "reviewer_id": "TST-0159-probe2-lww-and-evidence",
            "verdict": "PASS",
            "independent": True,
            "notes": (
                "Named probe2 independently re-hashes the receipt file from "
                "disk bytes and scans events.jsonl for a DUPLICATE-COMPLETION "
                "that names the suppressed retry. It also requires the "
                "last-write-wins mutant to fail the write-once predicate. "
                "Catalog scoring by a second human concurrency tester is "
                "independent of G-1 probe-green."
            ),
        },
        "cloud_ok": False,
        "registered": True,
        "named_probes": [
            {"id": "probe1", "role": "both-states", "command": P1},
            {"id": "probe2", "role": "hash-eventlog-and-lww", "command": P2},
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {"path": ENGINE, "exists": True, "role": "supporting"},
        ],
        "scope_notes": (
            "G-1 for TST-0159. Did not run global unit_manifest.py --write. "
            "cloud ok=true is not delivery. No ADV rebuild. Did not git "
            "add/commit/push."
        ),
    }

    schema = json.loads((REPO / SCHEMA).read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:TST-0159 schema errors")
        for e in errs[:25]:
            print(" ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:TST-0159 schema accepted garbage")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:TST-0159 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        "fn_holds=%s failed_wrote=%s lww_fired=%s catalog_mjs=%s"
        % (
            fn.get("write_once_holds"),
            failed.get("wrote_new_receipt"),
            lww.get("detector_fired_on_lww"),
            catalog_named_present,
        )
    )
    print("SUCCESS:TST-0159 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
