#!/usr/bin/env python3
"""Probe 1: which proposed property would have caught the silent-download case.

Mechanically different from probe 2: this probe only classifies blocked-run
fixtures and checks the live artifact's silent_download_mapping. It does not
inspect the impossible-property control.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import contract as C  # noqa: E402
import fixtures as F  # noqa: E402
import predicate as P  # noqa: E402
from engine import validate_against_schema  # noqa: E402

ART = REPO / C.OUTPUT_REL


def fail(msg: str) -> int:
    print(f"FAILED:{C.UNIT_ID}-probe1 {msg}")
    return 1


def main() -> int:
    for fx in F.CLASSIFY_FIXTURES:
        got = P.classify_blocked_run(
            comment=fx["comment"],
            attempted_destinations=fx["attempted_destinations"],
            claims_offline=fx["claims_offline"],
        )
        print(f"fixture {fx['id']} got={got} expect={fx['expect']}")
        if got != fx["expect"]:
            return fail(f"{fx['id']} classified {got} want {fx['expect']}")

    lying = P.classify_blocked_run(
        comment=C.LYING_COMMENT,
        attempted_destinations=F.LYING_GETPIP["attempted_destinations"],
        claims_offline=True,
    )
    if lying != "silent-download":
        return fail("planted get-pip analogue not caught")

    # Comment alone must not classify as hermetic when destinations exist.
    if (
        P.classify_blocked_run(
            comment=C.LYING_COMMENT,
            attempted_destinations=[{"host": "example.invalid", "port": 443}],
        )
        != "silent-download"
    ):
        return fail("lying comment with destinations was not silent-download")

    herm = P.classify_blocked_run(
        comment=C.LYING_COMMENT,
        attempted_destinations=[],
        claims_offline=True,
    )
    if herm != "hermetic":
        return fail("genuinely empty destination list was not hermetic")

    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if doc.get("state") in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        return fail(f"self-declared {doc.get('state')}")
    if C.SENTINEL not in text:
        return fail("sentinel absent")
    errs = validate_against_schema(doc)
    if errs:
        return fail(f"schema {errs[0]}")

    mapping = doc.get("silent_download_mapping") or {}
    print(
        "mapping catching={c} would_have_caught={w} comment_is_not_evidence={n}".format(
            c=mapping.get("catching_property_id"),
            w=mapping.get("would_have_caught"),
            n=mapping.get("comment_is_not_evidence"),
        )
    )
    if mapping.get("catching_property_id") != C.CATCHING_PROPERTY_ID:
        return fail("artifact catching_property_id is not P-UNDECLARED-EGRESS")
    if mapping.get("would_have_caught") is not True:
        return fail("artifact did not map silent-download as caught")
    if mapping.get("comment_is_not_evidence") is not True:
        return fail("artifact treats comments as evidence")
    case = str(mapping.get("motivating_case") or "")
    if "silent" not in case.lower() or "download" not in case.lower():
        return fail("motivating case does not name silent-download")
    if "14" not in case:
        return fail("motivating case does not name the 14-test instance")

    props = doc.get("property_list") or []
    catching_rows = [
        p
        for p in props
        if isinstance(p, dict) and p.get("id") == C.CATCHING_PROPERTY_ID
    ]
    if not catching_rows:
        return fail("P-UNDECLARED-EGRESS missing from property_list")
    row = catching_rows[0]
    if row.get("catches_silent_download") is not True:
        return fail("P-UNDECLARED-EGRESS not flagged as catching silent-download")
    if row.get("agent_run_adoptable") is not True:
        return fail("catching property marked not adoptable")

    answers = doc.get("answers") or {}
    if answers.get("silent_download_catching_property") != C.CATCHING_PROPERTY_ID:
        return fail("answers.silent_download_catching_property mismatch")
    if answers.get("fourteen_count_promoted") is not False:
        return fail("headline 14 was promoted")

    print(
        "SUCCESS:RES-0114-probe1 silent-download mapped to "
        f"{C.CATCHING_PROPERTY_ID} and planted analogue classified silent-download"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
