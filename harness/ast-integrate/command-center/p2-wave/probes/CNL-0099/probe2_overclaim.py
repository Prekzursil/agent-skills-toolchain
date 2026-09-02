#!/usr/bin/env python3
"""Probe 2: schema, false-positive-rate type, overclaim, independent both-states.

The reviewer named in the artifact is this probe. Agreement with the author's
prose is not the pass condition; re-running both-states and rejecting
schema/overclaim mutants is.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path = [p for p in sys.path if p not in ("", ".", str(REPO))]
sys.path.insert(0, str(HERE))
import detector as D  # noqa: E402
import schema_check as SC  # noqa: E402

ART = (
    REPO
    / "command-center/design/council/"
    / "CNL-0099-hallucinated-expertise-and-hidden-conflicts-of-interest.md"
)
SCHEMA = REPO / "command-center/schema/council-detector-spec.schema.json"


def fail(msg: str) -> int:
    print(f"FAILED:CNL-0099-probe2 {msg}")
    return 1


def main() -> int:
    if not ART.is_file():
        return fail("artifact-missing")
    if not SCHEMA.is_file():
        return fail("schema-missing")
    text = ART.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0099" not in text:
        return fail("sentinel-absent")
    doc = json.loads(text)
    if not SCHEMA.is_file():
        return fail("schema-missing")
    cat_errs = SC.catalog_errors(doc)
    ov_errs = SC.overlay_errors(doc)
    if cat_errs or ov_errs:
        return fail(f"schema {(cat_errs or ov_errs)[:3]}")
    print("schema_ok=True")

    garbage = {"unit_id": "not-a-unit", "passing_tests": 999}
    g_errs = SC.catalog_errors(garbage)
    print(f"garbage_rejected={bool(g_errs)}")
    if not g_errs:
        return fail("schema-accepted-garbage")

    mutant_fp = copy.deepcopy(doc)
    report = mutant_fp.setdefault("report", {})
    report["false_positive_rate"] = "low"
    fp_errs = SC.overlay_errors(mutant_fp)
    print(f"adjective_fp_rejected={bool(fp_errs)}")
    if not fp_errs:
        return fail("schema-accepted-adjective-fp-rate")

    mutant_ctrl = copy.deepcopy(doc)
    (mutant_ctrl.get("report") or {}).pop("detector_control", None)
    mutant_ctrl.pop("detector_control", None)
    ctrl_errs = SC.overlay_errors(mutant_ctrl)
    print(f"missing_detector_control_rejected={bool(ctrl_errs)}")
    if not ctrl_errs:
        return fail("schema-accepted-missing-detector-control")

    spec = SC.payload(doc)
    if not isinstance(spec.get("false_positive_rate"), (int, float)):
        return fail("fp-rate-not-number")
    print(f"false_positive_rate={spec['false_positive_rate']}")

    rev = doc.get("reviewer") or {}
    rep_rev = spec.get("reviewer") or {}
    independent = rev.get("independent") is True or rep_rev.get("independent") is True
    reran = (
        rev.get("reran_both_states") is True or rep_rev.get("reran_both_states") is True
    )
    if not independent or not reran:
        return fail("reviewer-did-not-claim-independent-rerun")

    index = D.load_index()
    planted_r = D.evaluate(D.load_fixture(index["planted_bad_primary"]))
    good_r = D.evaluate(D.load_fixture(index["known_good_primary"]))
    print(f"reviewer_planted_fired={planted_r['fired']}")
    print(f"reviewer_good_fired={good_r['fired']}")
    if not planted_r["fired"] or good_r["fired"]:
        return fail("reviewer-both-states")

    claims = spec.get("claims") or []
    if not isinstance(claims, list) or len(claims) < 2:
        return fail("claims-missing")
    saw_refuted = False
    saw_confirmed = False
    for row in claims:
        verdict = str(row.get("verdict") or "")
        fid = str(row.get("evidence_fixture") or "")
        if not fid:
            return fail(f"claim-{row.get('id')}-missing-fixture")
        live = D.evaluate(D.load_fixture(fid))
        if verdict == "REFUTED":
            saw_refuted = True
            if not live["fired"]:
                return fail(f"REFUTED-claim-{row.get('id')}-fixture-did-not-fire")
        elif verdict == "CONFIRMED":
            saw_confirmed = True
            if live["fired"]:
                return fail(f"CONFIRMED-claim-{row.get('id')}-fixture-fired")
        else:
            return fail(f"claim-{row.get('id')}-bad-verdict")
    print(f"overclaim_ok=True refuted={saw_refuted} confirmed={saw_confirmed}")
    if not saw_refuted or not saw_confirmed:
        return fail("need-both-REFUTED-and-CONFIRMED")

    naive_exp = D.naive_expertise_tag_match(
        D.load_fixture("planted_expertise_bad")
    )
    naive_coi = D.naive_coi_declaration_only(D.load_fixture("planted_coi_bad"))
    print(f"naive_tag_on_planted_expertise_fired={naive_exp['fired']}")
    print(f"naive_declaration_on_planted_coi_fired={naive_coi['fired']}")
    if naive_exp["fired"] or naive_coi["fired"]:
        return fail("naive-should-be-silent-on-hidden-plants")

    print("SUCCESS:CNL-0099-probe2 schema overclaim reviewer-both-states")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
