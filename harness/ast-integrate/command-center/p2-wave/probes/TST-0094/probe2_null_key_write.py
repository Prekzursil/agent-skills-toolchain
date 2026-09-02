#!/usr/bin/env python3
"""Probe 2: a null key in the filter is rejected at write time.

Catalog test: test_a_null_key_in_the_filter_is_rejected_at_write_time.

Production write(session_id=None) raises NullFilterKeyError and stores
nothing. The analogue mutant that *does* accept null hides the row from a
session-keyed harvest — that is the FC-11319 measured analogue, and it
must remain a mutant, not production.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import harvest as H  # noqa: E402

ART = REPO / "command-center/receipts/TST-0094.json"
ENG = HERE / "harvest.py"
OUT = HERE / "probe2-null-key-write.raw.json"
SENTINEL = "SUCCESS:TST-0094"


def production_write_has_no_silent_null_store() -> dict:
    """AST: production write() must call reject_filter_key unless allow_null_key."""
    tree = ast.parse(ENG.read_text(encoding="utf-8"))
    write_fn = None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "write":
            write_fn = node
            break
    if write_fn is None:
        return {"found_write": False, "calls_reject": False}
    calls_reject = False
    for node in ast.walk(write_fn):
        if isinstance(node, ast.Call):
            func = node.func
            name = ""
            if isinstance(func, ast.Name):
                name = func.id
            elif isinstance(func, ast.Attribute):
                name = func.attr
            if name == "reject_filter_key":
                calls_reject = True
    return {"found_write": True, "calls_reject": calls_reject}


def main() -> int:
    demo = H.null_key_write_demo()
    ast_report = production_write_has_no_silent_null_store()
    errors: list[str] = []

    if not demo["production_write_rejected"]:
        errors.append(f"production did not reject null write: {demo}")
    if demo["production_hidden_count"] != 0:
        errors.append("production stored a hidden null-keyed row")
    if not demo["mutant_hides_row"]:
        errors.append("analogue mutant did not hide the null-keyed row")
    if not demo["harvest_null_filter_rejected"]:
        errors.append("harvest(None) was not rejected")
    if not demo["json_null_record_rejected"]:
        errors.append("JSON session_id:null was not rejected at write")
    if not ast_report["found_write"] or not ast_report["calls_reject"]:
        errors.append(f"write() AST missing reject_filter_key: {ast_report}")
    if not H.analogue_fixed():
        errors.append("analogue_fixed() is false")

    remote = H.RemoteSubstrate()
    for bad in ("", "   ", 0, False):
        try:
            remote.write(bad, "x", "y")
            errors.append(f"write({bad!r}) was accepted")
        except H.NullFilterKeyError:
            pass

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if SENTINEL not in text:
            errors.append("receipt sentinel absent")
        if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            errors.append(f"receipt self-declared {doc.get('state')}")
        recorded = (doc.get("evidence") or {}).get("null_key_write") or {}
        if recorded.get("production_write_rejected") is not True:
            errors.append("receipt did not record write-time rejection")

    report = {
        "probe": "probe2-null-key-write",
        "unit_id": "TST-0094",
        "production_write_rejected": demo["production_write_rejected"],
        "mutant_hides_row": demo["mutant_hides_row"],
        "harvest_null_filter_rejected": demo["harvest_null_filter_rejected"],
        "json_null_record_rejected": demo["json_null_record_rejected"],
        "ast": ast_report,
        "errors": errors,
        "pass": not errors,
    }
    OUT.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, sort_keys=True))
    if errors:
        print("FAILED:TST-0094-probe2 null key not rejected at write time")
        for e in errors:
            print(" ", e)
        return 1
    print(
        "SUCCESS:TST-0094-probe2 null session_id rejected at write; "
        "analogue mutant still hides the row from session-keyed harvest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
