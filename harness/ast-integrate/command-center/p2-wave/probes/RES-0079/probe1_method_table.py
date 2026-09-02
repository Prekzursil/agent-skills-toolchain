#!/usr/bin/env python3
"""Probe 1: method table has prerequisite-data column; one zero-history method; E3 cannot promote.

Both-states: a mutant that drops the prerequisite-data column fails the same checker.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ART = REPO / "command-center/research/RES-0079.json"
SENTINEL = (
    "SUCCESS:RES-0079 in the receipt AND a method table with a "
    "prerequisite-data column and one method identified as usable at zero history"
)
NEEDED = ("doi", "section", "effect_size", "baseline")
ZERO_ID = "linear-equal"
REQUIRED_IDS = ("linear-equal", "log-equal", "bayesian-bma")


def fail(msg: str) -> int:
    print(f"FAILED:RES-0079-probe1 {msg}")
    return 1


def check_table(rows: list, *, require_zero: bool = True) -> list[str]:
    errors = []
    if not isinstance(rows, list) or len(rows) < 3:
        return ["method_table missing or too short"]
    ids = []
    zero = []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i} not object")
            continue
        if "prerequisite-data" not in row:
            errors.append(f"row {i} missing prerequisite-data")
        elif not str(row.get("prerequisite-data") or "").strip():
            errors.append(f"row {i} empty prerequisite-data")
        mid = str(row.get("id") or "")
        ids.append(mid)
        if row.get("usable_at_zero_history") is True:
            zero.append(mid)
    if require_zero:
        for rid in REQUIRED_IDS:
            if rid not in ids:
                errors.append(f"{rid} row absent")
        if zero != [ZERO_ID]:
            errors.append(f"zero-history identification {zero!r} want {[ZERO_ID]!r}")
    return errors


def check_doc(doc: dict) -> list[str]:
    errors = []
    text = json.dumps(doc, sort_keys=True)
    if SENTINEL not in text:
        errors.append("catalog completion_sentinel absent")
    if doc.get("unit_id") != "RES-0079":
        errors.append(f"unit_id {doc.get('unit_id')!r}")
    st = str(doc.get("state") or "").upper()
    if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        errors.append(f"self-declared {st}")
    errors.extend(check_table(doc.get("method_table") or []))
    if "linear pooling" not in str(doc.get("zero_history_method") or "").lower():
        errors.append("zero_history_method is not linear pooling")
    for claim in doc.get("claims") or []:
        cid = claim.get("claim_id")
        if claim.get("cannot_promote") is True:
            if claim.get("verdict") == "CONFIRMED" and claim.get("evidence_tier") in {"E1", "E2"}:
                errors.append(f"{cid} cannot_promote but confirmed E1/E2")
            continue
        if claim.get("verdict") != "CONFIRMED":
            continue
        if claim.get("evidence_tier") == "E3":
            errors.append(f"{cid} E3 confirmed without cannot_promote")
            continue
        lineage = claim.get("source_lineage") or []
        if not lineage:
            errors.append(f"{cid} empty source_lineage")
            continue
        src = lineage[0]
        live = "live worktree" in str(src.get("work") or "").lower() or src.get("doi") is None
        for k in NEEDED:
            if k == "doi" and live:
                continue
            val = str(src.get(k) or "").strip()
            if not val:
                errors.append(f"{cid} missing {k}")
            if k in {"effect_size", "baseline"} and val.upper().startswith("UNQUOTED"):
                errors.append(f"{cid} unquoted {k} on promoted claim")
    return errors


def main() -> int:
    if not ART.is_file() or ART.stat().st_size <= 0:
        return fail("artifact missing")
    doc = json.loads(ART.read_text(encoding="utf-8"))
    errs = check_doc(doc)
    if errs:
        print("\n".join(errs[:12]))
        return fail("green artifact failed checker")

    mutant = copy.deepcopy(doc)
    for row in mutant.get("method_table") or []:
        row.pop("prerequisite-data", None)
    m_err = check_table(mutant.get("method_table") or [])
    if not m_err:
        return fail("mutant without prerequisite-data was accepted (silent both states)")

    print("method_table_rows", len(doc["method_table"]))
    print("prerequisite-data_column", True)
    print("zero_history_method", doc.get("zero_history_method"))
    print("promoted", doc.get("promoted_claim_ids"))
    print("mutant_dropped_prerequisite-data_rejected", True)
    print("mutant_errors", m_err[0])
    print("SUCCESS:RES-0079-probe1 method table and E-tier promotion gate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
