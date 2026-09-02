#!/usr/bin/env python3
"""Probe 2: meta-schema, positive inventory, invariant file:line, receipt."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import inventory as I  # noqa: E402
import validator as V  # noqa: E402

RECEIPT = REPO / "command-center" / "receipts" / "REL-0002.json"
SENTINEL = "SUCCESS:REL-0002"


def main() -> int:
    fail = False
    rollback = V.rollback_schema()
    receipt_schema = V.receipt_schema()
    try:
        V.check_meta(rollback)
        print("rollback_schema check_schema=ok")
    except Exception as exc:
        print(f"FAILED:REL-0002-probe2 rollback meta-schema: {exc}")
        fail = True
    try:
        V.check_meta(receipt_schema)
        print("receipt_schema check_schema=ok")
    except Exception as exc:
        print(f"FAILED:REL-0002-probe2 receipt meta-schema: {exc}")
        fail = True

    quotes = V.locate_invariants()
    print(json.dumps({"invariants": quotes}, sort_keys=True))
    texts = {row["id"]: row["text"] for row in quotes}
    if texts.get("INV-PATH") != V.INV_PATH:
        print("FAILED:REL-0002-probe2 INV-PATH text drift")
        fail = True
    if texts.get("INV-PREDATE") != V.INV_PREDATE:
        print("FAILED:REL-0002-probe2 INV-PREDATE text drift")
        fail = True
    for row in quotes:
        print(f"{row['id']} {row['file']}:{row['line']}")

    doc = I.build_inventory()
    covered = I.catalog_types_covered(doc)
    missing = [t for t in I.CATALOG_TYPES if t not in covered]
    print(f"catalog_types_covered={covered} missing={missing}")
    if missing:
        print(f"FAILED:REL-0002-probe2 missing catalog types {missing}")
        fail = True
    for action in doc["actions"]:
        has_inv = "inverse" in action
        has_irr = "irreversible" in action
        if has_inv == has_irr:
            print(f"FAILED:REL-0002-probe2 action {action['id']} xor broken")
            fail = True
        if has_inv:
            print(
                f"action {action['id']} type={action['action_type']} "
                f"inverse={action['inverse']['kind']} "
                f"completeness={action['inverse']['completeness']}"
            )
        else:
            print(
                f"action {action['id']} type={action['action_type']} "
                "IRREVERSIBLE"
            )

    errs = V.error_strings(V.rollback_validator(), doc)
    print(f"inventory_errors={errs}")
    if errs:
        print("FAILED:REL-0002-probe2 inventory does not validate")
        fail = True

    if not RECEIPT.is_file() or RECEIPT.stat().st_size <= 0:
        print("FAILED:REL-0002-probe2 receipt missing")
        fail = True
    else:
        receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
        rerr = V.error_strings(V.receipt_validator(), receipt)
        print(f"receipt_schema_errors={rerr}")
        if rerr:
            print("FAILED:REL-0002-probe2 receipt schema errors")
            fail = True
        body = RECEIPT.read_text(encoding="utf-8")
        if SENTINEL not in body:
            print("FAILED:REL-0002-probe2 sentinel absent from receipt")
            fail = True
        if receipt.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            print(f"FAILED:REL-0002-probe2 self-declared {receipt.get('state')}")
            fail = True
        quoted = receipt.get("contract", {}).get("named_invariants") or []
        by_id = {q.get("id"): q for q in quoted}
        for row in quotes:
            hit = by_id.get(row["id"]) or {}
            if hit.get("line") != row["line"] or hit.get("text") != row["text"]:
                print(f"FAILED:REL-0002-probe2 receipt invariant drift {row['id']}")
                fail = True

    garbage = [{}, {"totally": "unrelated", "passing_tests": 999999}, {"blob": "x" * 2000}]
    rejected = 0
    rv = V.receipt_validator()
    for g in garbage:
        if V.error_strings(rv, g):
            rejected += 1
    print(f"garbage_rejected={rejected}/3")
    if rejected != 3:
        print("FAILED:REL-0002-probe2 receipt schema accepted garbage")
        fail = True

    if fail:
        print("FAILED:REL-0002-probe2 positive meta-schema")
        return 1
    print(
        "SUCCESS:REL-0002-probe2 meta-schema, full inventory, invariants "
        "file:line, receipt"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
