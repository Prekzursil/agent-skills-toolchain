#!/usr/bin/env python3
"""Named probe 1: exercise every trust-policy cell; unspecified fails closed."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from marketplace.reviewer_default import compare_to_policy_cells  # noqa: E402
from marketplace.trust_policy import (  # noqa: E402
    SCHEMA_REL,
    cartesian,
    completeness,
    default_policy_document,
    default_verdict,
    decide,
    drop_cell,
    exercise_matrix,
    load_policy,
    repo_default_path,
    validate_schema,
)

ART = REPO / "command-center/receipts/IMP-0078.json"


def main() -> int:
    if not ART.is_file() or ART.stat().st_size < 128:
        print("FAILED:IMP-0078-probe1 receipt missing")
        return 1
    receipt = json.loads(ART.read_text(encoding="utf-8"))
    blob = json.dumps(receipt)
    if "SUCCESS:IMP-0078" not in blob:
        print("FAILED:IMP-0078-probe1 sentinel absent")
        return 1
    if str(receipt.get("state") or "").upper() in {
        "BLOCKED",
        "FAILED",
        "SEVERED",
        "TIMEOUT",
    }:
        print("FAILED:IMP-0078-probe1 self-declared", receipt.get("state"))
        return 1

    on_disk = load_policy(repo_default_path(REPO))
    generated = default_policy_document()
    if on_disk != generated:
        print("FAILED:IMP-0078-probe1 on-disk default drifted from generator")
        return 1

    report = completeness(on_disk)
    if not report["complete"] or report["expected"] != 72:
        print("FAILED:IMP-0078-probe1 completeness", json.dumps(report)[:1500])
        return 1

    schema_errs = validate_schema(on_disk, REPO / SCHEMA_REL)
    if schema_errs:
        print("FAILED:IMP-0078-probe1 schema", schema_errs[:8])
        return 1

    rows = exercise_matrix(on_disk)
    if len(rows) != len(cartesian()) or len(rows) != 72:
        print(f"FAILED:IMP-0078-probe1 matrix size {len(rows)}")
        return 1
    bad = [
        r
        for r in rows
        if not r["match"]
        or r["observed"]
        != default_verdict(r["signature_state"], r["trust_level"], r["advisory_state"])
    ]
    if bad:
        print("FAILED:IMP-0078-probe1 cell mismatch", json.dumps(bad[:5]))
        return 1

    allows = [r for r in rows if r["observed"] == "allow"]
    if len(allows) != 1 or allows[0]["cell"] != "verified|high|none":
        print("FAILED:IMP-0078-probe1 allow set", allows)
        return 1

    dropped = drop_cell(on_disk, "verified|high|none")
    d = decide(dropped, "verified", "high", "none")
    if d.verdict != "deny" or not d.fail_closed:
        print("FAILED:IMP-0078-probe1 unspecified did not fail closed", d.as_dict())
        return 1
    unknown = decide(on_disk, "forged", "high", "none")
    if unknown.verdict != "deny" or not unknown.fail_closed:
        print("FAILED:IMP-0078-probe1 unknown dimension not closed")
        return 1

    reviewer = compare_to_policy_cells(on_disk["cells"])
    if not reviewer["agreed"]:
        print(
            "FAILED:IMP-0078-probe1 reviewer disagreement",
            reviewer["disagreements"][:8],
        )
        return 1

    print(
        json.dumps(
            {
                "cells": len(rows),
                "complete": True,
                "allow_cells": [a["cell"] for a in allows],
                "unspecified_fail_closed": True,
                "unknown_fail_closed": True,
                "schema_ok": True,
                "reviewer_agreed": True,
            },
            sort_keys=True,
        )
    )
    print("SUCCESS:IMP-0078-probe1 full matrix no unspecified cell")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
