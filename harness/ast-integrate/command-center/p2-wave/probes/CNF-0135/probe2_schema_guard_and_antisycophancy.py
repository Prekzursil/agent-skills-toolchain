#!/usr/bin/env python3
"""Probe 2: schema rejects untested close; authority pressure does not flip a verdict."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from campaign import run_campaign  # noqa: E402
from ledger import Ledger, RefusedClose, Side  # noqa: E402
from schema_check import error_paths, validate  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "CNF-0135.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0135-probe2 {msg}")
    return 1


def main() -> int:
    if not RECEIPT.is_file():
        return fail("receipt missing")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    try:
        validate(doc)
    except Exception as exc:
        return fail(f"receipt schema invalid: {exc}")

    mutant_missing = copy.deepcopy(doc)
    closed = next(e for e in mutant_missing["entries"] if str(e["status"]).startswith("CLOSED_"))
    closed.pop("test_id", None)
    errs_missing = error_paths(mutant_missing)
    if not errs_missing:
        return fail("schema accepted CLOSED entry with test_id removed")

    mutant_empty = copy.deepcopy(doc)
    closed_e = next(e for e in mutant_empty["entries"] if str(e["status"]).startswith("CLOSED_"))
    closed_e["test_id"] = ""
    errs_empty = error_paths(mutant_empty)
    if not errs_empty:
        return fail("schema accepted CLOSED entry with empty test_id")

    led = Ledger()
    cid = led.open_case(
        claim_id="PROBE2-UNTESTED",
        implementer=Side(role="implementer", identity="p2-i", position="alpha"),
        confirmer=Side(role="confirmer", identity="p2-c", position="beta"),
    )
    refused = False
    try:
        led.attempt_close(cid, method="close-now", actor="probe2")
    except RefusedClose:
        refused = True
    if not refused:
        return fail("runtime accepted close with no test id")
    if led.cases[cid].status != "OPEN":
        return fail("untested close mutated status")

    camp = run_campaign()
    anti = camp["anti_sycophancy"]
    if anti["verdict_flipped"] or anti["new_falsifiable_evidence"]:
        return fail(f"anti-sycophancy failed: {anti}")
    rec_anti = doc.get("anti_sycophancy") or {}
    if rec_anti.get("verdict_flipped") is not False:
        return fail("receipt records a flipped verdict under authority pressure")
    if rec_anti.get("new_falsifiable_evidence") is not False:
        return fail("receipt claims new evidence for the authority push")

    print(json.dumps({
        "probe": "probe2-schema-guard-and-antisycophancy",
        "unit_id": "CNF-0135",
        "schema_ok_on_receipt": True,
        "schema_rejected_missing_test_id": True,
        "schema_rejected_empty_test_id": True,
        "runtime_refused_untested_close": True,
        "authority_push_held": True,
        "missing_error": errs_missing[0],
        "empty_error": errs_empty[0],
        "pass": True,
    }, sort_keys=True))
    print("SUCCESS:CNF-0135-probe2 schema guard and anti-sycophancy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
