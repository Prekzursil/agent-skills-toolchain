#!/usr/bin/env python3
"""Named probe 2 (reviewer): assertion classifier misclassifies the labelled set.

Starts from the labelled fixtures, not from the author's summary. The
production classifier still reads source.type. The negative-control
classifier reads claimed_tier / asserted_source_type and is shown wrong
on every planted disagreement. Also AST-checks production functions do
not load those assertion fields.
"""

from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(REPO / "tools"))

from council.evidence.standard import (  # noqa: E402
    CLASSIFIER_INPUT_FIELD,
    admit_claim,
    bind_decision,
    classify_by_claimant_assertion,
    classify_source_type,
    load_labelled_claims,
    misclassification_report,
    preset_for,
)

STANDARD_SRC = REPO / "tools" / "council" / "evidence" / "standard.py"
PRODUCTION_FNS = frozenset(
    {
        "classify_source_type",
        "_source_type_value",
        "admit_claim",
        "bind_decision",
        "classification_pass",
        "read_field",
    }
)
BANNED = frozenset({"claimed_tier", "asserted_source_type"})


def fail(msg: str) -> int:
    print(f"FAILED:IMP-0365-probe2 {msg}")
    return 1


def _production_reads_assertion() -> list[str]:
    tree = ast.parse(STANDARD_SRC.read_text(encoding="utf-8"))
    hits = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name not in PRODUCTION_FNS:
            continue
        literals = {
            child.value
            for child in ast.walk(node)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        }
        banned_hit = literals & BANNED
        if banned_hit:
            hits.append(f"{node.name}:{sorted(banned_hit)}")
    return hits


def main() -> int:
    claims = load_labelled_claims()
    report = misclassification_report(claims)
    if not report["shows_misclassification"]:
        return fail("labelled set did not show assertion-classifier misclassification")
    if report["n_mismatch"] != len(claims):
        return fail(
            f"expected every labelled claim to mismatch, got {report['n_mismatch']}"
        )
    if report["classifier_input_field"] != CLASSIFIER_INPUT_FIELD:
        return fail("report did not name source.type as the production input")

    for claim in claims:
        truth = classify_source_type(claim)
        asserted = classify_by_claimant_assertion(claim)
        if truth == asserted:
            return fail(f"{claim['id']}: assertion classifier accidentally agreed")
        if truth != claim["label_tier"]:
            return fail(
                f"{claim['id']}: source-type class {truth} != label {claim['label_tier']}"
            )

    ast_hits = _production_reads_assertion()
    if ast_hits:
        return fail(f"production functions read assertion fields: {ast_hits}")

    poison = next(c for c in claims if c["id"] == "C-UNCITED")
    row = admit_claim(preset_for("executable-proof-only"), poison)
    if row["admitted"]:
        return fail("production admit trusted claimant assertion on C-UNCITED")
    if row["classifier_input_value"] != "assertion":
        return fail("production classifier did not record source.type=assertion")
    if classify_by_claimant_assertion(poison) != "executable-proof-only":
        return fail("negative-control classifier did not swallow the over-claim")

    decision = bind_decision(preset_for("peer-reviewed-only"), claims)
    if "C-CITED" in decision["supporting_claim_ids"]:
        return fail("blog citation bound under peer-reviewed-only via assertion")
    if "C-MISSING-TYPE" in decision["supporting_claim_ids"]:
        return fail("missing source.type bound because claimed_tier looked reviewed")

    payload = {
        "probe": "probe2-assertion-misclassification",
        "unit_id": "IMP-0365",
        "reviewer_id": "IMP-0365-probe2-assertion-misclassification",
        "independent": True,
        "starts_from": "tools/council/evidence/fixtures/labelled_claims.json",
        "production_classifier_input_field": CLASSIFIER_INPUT_FIELD,
        "negative_control_classifier": "classify_by_claimant_assertion",
        "n": report["n"],
        "n_mismatch": report["n_mismatch"],
        "mismatch_ids": report["mismatch_ids"],
        "shows_misclassification": True,
        "ast_production_ignores_assertion_fields": True,
        "production_still_refuses_overclaimed": True,
        "rows": report["rows"],
        "pass": True,
    }
    print(json.dumps(payload, sort_keys=True))
    print(
        f"mismatches={report['n_mismatch']}/{report['n']} "
        "input=source.type assertion_classifier=wrong"
    )
    print(
        "SUCCESS:IMP-0365-probe2 assertion classifier misclassifies labelled set"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
