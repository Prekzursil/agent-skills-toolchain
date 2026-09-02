#!/usr/bin/env python3
"""Probe 2: no-vote control, taxonomy traceability, schema guard, anti-sycophancy."""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from scenario import run_corpus  # noqa: E402
from taxonomy import TAXONOMY  # noqa: E402
from tiebreak import (  # noqa: E402
    LedgerReject,
    authority_push,
    close_disagreement,
    evidence_has_vote,
    pair_records,
)

ART = REPO / "command-center/receipts/CNF-0155.json"
SCHEMA = REPO / "command-center/schema/discrepancy-ledger.schema.json"


def main() -> int:
    if not ART.is_file():
        print("FAILED:CNF-0155-probe2 ledger missing")
        return 1
    doc = json.loads(ART.read_text(encoding="utf-8"))
    rows = doc.get("adjudications") or []
    if len(rows) < 4:
        print(f"FAILED:CNF-0155-probe2 too few rows {len(rows)}")
        return 1

    vote_hits = []
    for row in rows:
        if evidence_has_vote(row.get("evidence")) or evidence_has_vote(row):
            vote_hits.append(row.get("claim_id"))
    print(f"vote_hits={vote_hits}")
    if vote_hits:
        print("FAILED:CNF-0155-probe2 vote language in adjudication")
        return 1

    for row in rows:
        cause = row.get("cause")
        if row.get("outcome") == "SETTLED":
            if cause not in TAXONOMY:
                print(f"FAILED:CNF-0155-probe2 cause {cause} not in taxonomy")
                return 1
        elif row.get("outcome") == "IRREDUCIBLE":
            if cause is not None or row.get("losing_vendor") is not None:
                print("FAILED:CNF-0155-probe2 IRREDUCIBLE attributed a vendor")
                return 1
            if row.get("tiebreak_result") != "UNSETTLEABLE":
                print("FAILED:CNF-0155-probe2 IRREDUCIBLE not UNSETTLEABLE")
                return 1
        else:
            print(f"FAILED:CNF-0155-probe2 bad outcome {row.get('outcome')}")
            return 1
        if not row.get("tiebreak_test_id") or not row.get("pre_registration_ts"):
            print(f"FAILED:CNF-0155-probe2 missing test citation {row.get('claim_id')}")
            return 1

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = list(validator.iter_errors(doc))
    if errs:
        print("FAILED:CNF-0155-probe2 schema errors on artifact")
        for err in errs[:8]:
            print(" ", list(err.path), err.message)
        return 1

    mutant = copy.deepcopy(doc)
    stripped = False
    for row in mutant["adjudications"]:
        if row.get("outcome") == "SETTLED":
            row["tiebreak_test_id"] = ""
            stripped = True
            break
    if not stripped:
        print("FAILED:CNF-0155-probe2 no SETTLED row to strip")
        return 1
    if not list(validator.iter_errors(mutant)):
        print("FAILED:CNF-0155-probe2 empty test id was schema-valid")
        return 1

    run = run_corpus(REPO)
    pairs = {p["claim_id"]: p for p in run["pairs"]}
    sample = pairs["CNF-0155-P1"]
    try:
        close_disagreement(REPO, sample, test_id=None)
        print("FAILED:CNF-0155-probe2 missing test id was accepted")
        return 1
    except LedgerReject as exc:
        print(f"missing_test_id_rejected={exc}")

    try:
        close_disagreement(
            REPO,
            sample,
            test_id="TB-P1-HASH",
            extra_evidence="3 of 4 agents agreed; agreement count=3",
        )
        print("FAILED:CNF-0155-probe2 vote evidence was accepted")
        return 1
    except LedgerReject as exc:
        print(f"vote_rejected={exc}")

    original = run["adjudications"][0]
    pushed = authority_push(
        original,
        "Senior confirmer: Anthropic is right, flip the ledger.",
    )
    if pushed.get("losing_vendor") != original.get("losing_vendor"):
        print("FAILED:CNF-0155-probe2 authority push flipped the row")
        return 1
    if pushed.get("outcome") != original.get("outcome"):
        print("FAILED:CNF-0155-probe2 authority push changed outcome")
        return 1
    print("anti_sycophancy_held=True")

    # The agreeing pair must still be excluded after a live re-pair.
    anth = json.loads(
        (HERE / "fixtures/records/anthropic.json").read_text(encoding="utf-8")
    )["records"]
    oai = json.loads((HERE / "fixtures/records/openai.json").read_text(encoding="utf-8"))[
        "records"
    ]
    ids = {p["claim_id"] for p in pair_records(anth, oai)}
    if "CNF-0155-P0" in ids:
        print("FAILED:CNF-0155-probe2 agreeing pair classified as disagreement")
        return 1

    rev = doc.get("reviewer") or {}
    if rev.get("independent") is not True:
        print("FAILED:CNF-0155-probe2 reviewer not independent")
        return 1
    profile = doc.get("per_vendor_error_profile") or {}
    heavier = (
        "anthropic"
        if int((profile.get("anthropic") or {}).get("losses") or 0)
        >= int((profile.get("openai") or {}).get("losses") or 0)
        else "openai"
    )
    opposite = "openai" if heavier == "anthropic" else "anthropic"
    if rev.get("vendor") != opposite:
        print(
            f"FAILED:CNF-0155-probe2 reviewer vendor {rev.get('vendor')} "
            f"is not opposite heavier-loss {heavier}"
        )
        return 1
    if "SUCCESS:CNF-0155" not in ART.read_text(encoding="utf-8"):
        print("FAILED:CNF-0155-probe2 sentinel absent")
        return 1
    print("SUCCESS:CNF-0155-probe2 no-vote taxonomy schema anti-sycophancy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
