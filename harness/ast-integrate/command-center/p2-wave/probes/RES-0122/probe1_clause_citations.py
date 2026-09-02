#!/usr/bin/env python3
"""Probe 1: every remaining obligation cites a clause present in its capture.

Catalog tests_required[0]: cite the clause for every stated obligation.
Negative control: dropping clause_quote from one obligation must fail.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from rails import (  # noqa: E402
    assert_quote_in_capture,
    check_claim_two_rails,
    load_index,
)
from schema_check import check_document  # noqa: E402

ART = REPO / "command-center/research/RES-0122.json"
SENTINEL = (
    "SUCCESS:RES-0122 in the receipt AND a per-class obligation table "
    "with clause citations and the trademarked-method handling stated"
)


def obligations_ok(doc: dict, index: dict) -> tuple[bool, str]:
    n = 0
    for row in doc.get("obligation_table") or []:
        for ob in row.get("remaining_obligations") or []:
            n += 1
            quote = str(ob.get("clause_quote") or "")
            capture = str(ob.get("capture") or "")
            if len(quote) < 24 or not capture:
                return False, f"thin obligation {ob.get('id')}"
            if capture not in index:
                return False, f"unknown capture {capture}"
            try:
                assert_quote_in_capture(quote, capture)
            except SystemExit as exc:
                return False, str(exc)
    if n < 7:
        return False, f"only {n} obligations"
    return True, f"obligations={n}"


def main() -> int:
    if not ART.is_file():
        print("FAILED:RES-0122-probe1 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    if SENTINEL not in text:
        print("FAILED:RES-0122-probe1 sentinel absent")
        return 1
    doc = json.loads(text)
    errors = check_document(doc)
    if errors:
        print("FAILED:RES-0122-probe1 schema", errors[:8])
        return 1
    if str(doc.get("state") or "").upper() in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print("FAILED:RES-0122-probe1 self-declared", doc.get("state"))
        return 1
    index = load_index()
    ok, why = obligations_ok(doc, index)
    print(f"obligations_ok={ok} {why}")
    if not ok:
        print("FAILED:RES-0122-probe1", why)
        return 1

    for claim in doc.get("claims") or []:
        err = check_claim_two_rails(index, claim)
        print(f"claim[{claim.get('id')}] {err or 'ok'}")
        if err:
            print("FAILED:RES-0122-probe1", err)
            return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["obligation_table"]:
        for ob in row["remaining_obligations"]:
            if ob.get("clause_quote"):
                ob["clause_quote"] = ""
                stripped = True
                break
        if stripped:
            break
    if not stripped:
        print("FAILED:RES-0122-probe1 nothing to strip")
        return 1
    mok, mwhy = obligations_ok(mutant, index)
    print(f"mutant_ok={mok} {mwhy}")
    if mok:
        print("FAILED:RES-0122-probe1 mutant without clause_quote was accepted")
        return 1

    print("SUCCESS:RES-0122-probe1 clause citations two-rails mutant-red")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
