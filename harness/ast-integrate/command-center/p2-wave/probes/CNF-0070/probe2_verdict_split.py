#!/usr/bin/env python3
"""Probe 2: independent re-derivation; was-true-then-changed ≠ never-supported.

Reads raw fixture bytes and citation dates, derives verdicts, THEN opens the
artifact conclusions. A reviewer who reads the conclusion first does not count.
A mutant that merges the two verdicts into one label is rejected.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import auditor as A  # noqa: E402
import schema_ctl as SC  # noqa: E402

ART = REPO / "command-center/confirmation/CNF-0070-archival-corroboration.json"
MERGED_LABEL = "unsupported"


def fail(msg: str) -> int:
    print(f"FAILED:CNF-0070-probe2 {msg}")
    return 1


def merge_verdicts(result: dict) -> dict:
    """Illegal merger: collapse was-true-then-changed and never-supported."""
    out = copy.deepcopy(result)
    for row in out["citations"]:
        if row["verdict"] in {A.WAS_TRUE, A.NEVER}:
            row["verdict"] = MERGED_LABEL
    return out


def main() -> int:
    # Derive FIRST from raw sources — do not load the artifact yet.
    derived = A.audit_all(accept_late=False)
    dmap = A.by_id(derived)
    want = {
        "C-CHANGED": A.WAS_TRUE,
        "C-NEVER": A.NEVER,
        "C-NOSNAP": A.NO_SNAP,
        "C-UNTRUSTED": A.WAS_TRUE,
        "C-POSTDATE": A.NO_SNAP,
        "C-SAMEDAY": A.WAS_TRUE,
    }
    for cid, verdict in want.items():
        got = (dmap.get(cid) or {}).get("verdict")
        print(f"derived[{cid}]={got}")
        if got != verdict:
            return fail(f"raw derivation {cid}={got} want={verdict}")

    if dmap["C-CHANGED"]["verdict"] == dmap["C-NEVER"]["verdict"]:
        return fail("was-true-then-changed and never-supported were the same label")
    if A.WAS_TRUE == A.NEVER:
        return fail("verdict constants collapsed")

    merged = merge_verdicts(derived)
    merged_ids = {r["verdict"] for r in merged["citations"] if r["id"] in {"C-CHANGED", "C-NEVER"}}
    if merged_ids != {MERGED_LABEL}:
        return fail("merger control did not collapse both rows")
    print(f"merger_control_collapses_to={MERGED_LABEL} rejected=true")

    # NOW open the artifact and compare. Conclusion-first would be invalid review.
    if not ART.is_file():
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    if doc.get("reviewer", {}).get("read_conclusion_first") is not False:
        return fail("reviewer.read_conclusion_first must be false")
    if doc.get("reviewer", {}).get("independent") is not True:
        return fail("reviewer not independent")

    amap = {str(r["id"]): r for r in doc.get("citations") or []}
    for cid, verdict in want.items():
        got = (amap.get(cid) or {}).get("verdict")
        if got != verdict:
            return fail(f"artifact {cid}={got} want={verdict} (disagrees with raw derivation)")
        if got != dmap[cid]["verdict"]:
            return fail(f"artifact/raw mismatch on {cid}")

    validator = SC.validator()
    if list(validator.iter_errors(doc)):
        return fail("artifact failed schema")

    mutant = copy.deepcopy(doc)
    for row in mutant["citations"]:
        if row["verdict"] in {A.WAS_TRUE, A.NEVER}:
            row["verdict"] = MERGED_LABEL
    merrs = list(validator.iter_errors(mutant))
    if not merrs:
        return fail("schema accepted merged-verdict mutant")
    print(f"merged_verdict_mutant_rejected={merrs[0].message}")

    kinds = {r["verdict"] for r in doc["citations"]}
    if A.WAS_TRUE not in kinds or A.NEVER not in kinds:
        return fail(f"artifact missing distinct verdicts {kinds}")
    print(f"artifact_verdicts={sorted(kinds)}")
    print("SUCCESS:CNF-0070-probe2 independent-rederive verdict-split")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
