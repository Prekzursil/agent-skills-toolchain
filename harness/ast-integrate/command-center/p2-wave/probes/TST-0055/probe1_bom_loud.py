#!/usr/bin/env python3
"""Probe 1: BOM-prefixed JSON is handled or rejected loudly.

Re-runs the live matrix. Requires every config/artifact reader to HANDLE
UTF-8 and to HANDLE or REJECT_LOUD UTF-8-with-BOM, matching the receipt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import matrix as M  # noqa: E402

ART = REPO / "command-center/receipts/TST-0055.json"
SCHEMA = REPO / "command-center/schema/test-receipt.schema.json"
SENTINEL = "SUCCESS:TST-0055"


def fail(msg: str) -> int:
    print(f"FAILED:TST-0055-probe1 {msg}")
    return 1


def main() -> int:
    live = M.run_matrix()
    if not live["encoding_self_check"]["pass"]:
        return fail("encoding self-check")
    if not live["summary"]["required_utf8_handle"]:
        return fail("required utf-8 HANDLE missing")
    if not live["summary"]["required_bom_handled_or_loud"]:
        return fail("required BOM cell was not HANDLE or REJECT_LOUD")
    if not live["tests"]["test_bom_prefixed_json_is_handled_or_rejected_loudly"]:
        return fail("BOM test false")

    bom_cells = [
        c
        for c in live["matrix"]
        if c["in_required_tests"] and c["encoding"] == "utf-8-bom"
    ]
    if not bom_cells:
        return fail("no BOM cells")
    loud = [c for c in bom_cells if c["classification"] == "REJECT_LOUD"]
    if not loud:
        return fail("no required reader rejected BOM loudly")
    for cell in loud:
        text = cell.get("exception_text") or ""
        if "BOM" not in text and "utf-8-sig" not in text:
            return fail(f"BOM exception text not diagnostic: {text!r}")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        return fail("sentinel absent")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if doc.get("unit_id") != "TST-0055":
        return fail(f"unit_id {doc.get('unit_id')}")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errs = list(jsonschema.Draft7Validator(schema).iter_errors(doc))
    if errs:
        return fail(f"schema {errs[0].message}")

    art_bom = [
        c
        for c in (doc.get("matrix") or [])
        if c.get("in_required_tests") and c.get("encoding") == "utf-8-bom"
    ]
    live_fp = {
        (c["reader_id"], c["encoding"]): (
            c["classification"],
            c.get("exception_type"),
            c.get("exception_text"),
        )
        for c in bom_cells
    }
    art_fp = {
        (c["reader_id"], c["encoding"]): (
            c["classification"],
            c.get("exception_type"),
            c.get("exception_text"),
        )
        for c in art_bom
    }
    if live_fp != art_fp:
        return fail(f"artifact BOM matrix drift {sorted(set(live_fp) ^ set(art_fp))[:6]}")

    tests = {t.get("id"): t for t in (doc.get("tests") or []) if isinstance(t, dict)}
    row = tests.get("test_bom_prefixed_json_is_handled_or_rejected_loudly")
    if not row or row.get("result") != "PASS":
        return fail("artifact BOM test not PASS")

    print(
        json.dumps(
            {
                "probe": "probe1-bom-loud",
                "unit_id": "TST-0055",
                "pass": True,
                "required_bom_cells": len(bom_cells),
                "bom_reject_loud": len(loud),
                "exception_sample": loud[0].get("exception_text"),
            },
            sort_keys=True,
        )
    )
    print(
        f"bom_cells={len(bom_cells)} reject_loud={len(loud)} "
        f"sample={loud[0].get('exception_text')}"
    )
    print("SUCCESS:TST-0055-probe1 BOM handled or rejected loudly")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
