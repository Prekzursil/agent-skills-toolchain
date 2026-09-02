#!/usr/bin/env python3
"""Probe 1: catalog controls via lexicon matching.

1. 'should work' with no band must be caught.
2. 'likely (55-80%), measured at path:line' must pass unflagged.
3. a past-tense measured fact carrying a probability band must be
   CATEGORY-ERROR, not COMPLIANT.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import audit as A  # noqa: E402

CONTROLS = HERE / "fixtures" / "controls.md"
RECEIPT = REPO / "command-center" / "receipts" / "BLD-0031.json"


def fail(msg: str) -> int:
    print(f"FAILED:BLD-0031-probe1 {msg}")
    return 1


def quotes_of(doc: dict, klass: str) -> list[str]:
    return [
        str(f.get("quote") or "")
        for f in (doc.get("findings") or [])
        if isinstance(f, dict) and f.get("class") == klass
    ]


def main() -> int:
    ctrls = A.control_sentences(CONTROLS)
    missing = ctrls.get("CONTROL-MISSING-BAND", "")
    compliant = ctrls.get("CONTROL-COMPLIANT", "")
    caterr = ctrls.get("CONTROL-CATEGORY-ERROR", "")
    if not (missing and compliant and caterr):
        return fail("planted controls unreadable")

    c_miss = A.classify_lexicon(missing)
    c_ok = A.classify_lexicon(compliant)
    c_err = A.classify_lexicon(caterr)
    print(json.dumps({"missing": c_miss, "compliant": c_ok, "category_error": c_err}, indent=2))

    if c_miss["class"] != "MISSING-BAND" or not c_miss.get("bare_hedge"):
        return fail(f"should-work not caught: {c_miss['class']}")
    if c_ok["class"] != "COMPLIANT":
        return fail(f"banded+evidence flagged: {c_ok['class']}")
    if c_err["class"] != "CATEGORY-ERROR":
        return fail(f"past-fact+band class={c_err['class']} not CATEGORY-ERROR")

    if not RECEIPT.is_file():
        return fail("receipt absent")
    doc = json.loads(RECEIPT.read_text(encoding="utf-8"))
    miss_q = quotes_of(doc, "MISSING-BAND")
    err_q = quotes_of(doc, "CATEGORY-ERROR")
    flagged_quotes = [
        str(f.get("quote") or "")
        for f in (doc.get("findings") or [])
        if isinstance(f, dict)
    ]
    if not any("should work" in q for q in miss_q):
        return fail("receipt missing-band does not quote should work")
    if any("measured at command-center/p2-wave/P2-BUILD-ROUND1.md:475" in q for q in flagged_quotes):
        return fail("compliant control appears in findings")
    if not any("measured 12 failing tests yesterday" in q for q in err_q):
        return fail("receipt category-error does not quote planted past fact")

    unflagged = doc.get("unflagged") or []
    if not any(
        isinstance(u, dict)
        and "measured at command-center/p2-wave/P2-BUILD-ROUND1.md:475" in str(u.get("quote") or "")
        and u.get("class") == "COMPLIANT"
        for u in unflagged
    ):
        return fail("compliant control not recorded unflagged")

    print(
        "should_work_caught=True compliant_unflagged=True "
        "past_fact_category_error=True method=lexicon"
    )
    print("SUCCESS:BLD-0031-probe1 lexicon controls")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
