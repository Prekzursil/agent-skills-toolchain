#!/usr/bin/env python3
"""Probe 2: Draft202012Validator + composition negative control + recount.

Negative control (verbatim): the check REJECTS a composer that authorizes
action when the legal board outcome is PROHIBITED and the risk committee
outcome is ACCEPT (risk-accept-overrides-legal-no). It is SILENT on the
honest composer, which records both outcomes and sets action_authorized=false.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import boards as B  # noqa: E402
import compose as K  # noqa: E402
import instantiate as I  # noqa: E402
import schema_check as V  # noqa: E402
import sibling as S  # noqa: E402

ART = (
    REPO
    / "command-center/design/council"
    / "CNL-0111-normative-boards-ethics-legal-review-and-the-risk-committe.md"
)
NEGATIVE_VERBATIM = K.NEGATIVE_VERBATIM


def _fail(msg: str) -> int:
    print(f"FAILED:CNL-0111-probe2 {msg}")
    return 1


def independent_recount() -> dict:
    """Recompute sibling distances without reading the design-note numbers."""
    legal_p, risk_p = B.family_presets()
    library, meta = S.library_presets()
    row_legal = B.as_signature_row(legal_p)
    row_risk = B.as_signature_row(risk_p)
    return {
        "c15_c16_distance": S.pairwise_distance(row_legal, row_risk),
        "nearest_sibling_legal": S.nearest_sibling(
            row_legal, library, exclude_ids={"C15", "C16"}
        ),
        "nearest_sibling_risk": S.nearest_sibling(
            row_risk, library, exclude_ids={"C15", "C16"}
        ),
        "threshold": meta["threshold"],
        "original_library_present": meta["original_library_present"],
    }


def main() -> int:
    presets = B.family_presets()
    schema_report = V.validate_records(presets)
    if schema_report["record_error_count"] != 0:
        return _fail(f"schema errors {schema_report}")
    if schema_report["invalid_error_count"] < 1 or schema_report["vacuous"]:
        return _fail("deliberately-invalid record did not fail; validator vacuous")

    conflict_task = I.load_task()
    legal = I.legal_outcome(conflict_task)
    risk = I.risk_outcome(conflict_task)
    mutant_claim = K.mutant_risk_overrides_legal(legal, risk)
    honest_claim = K.action_authorized(legal, risk)
    bad_verdict = K.check_composer(mutant_claim, legal, risk)
    good_verdict = K.check_composer(honest_claim, legal, risk)
    fired_on_bad = bad_verdict == "FIRE"
    silent_on_good = good_verdict == "SILENT"
    if not (fired_on_bad and silent_on_good):
        return _fail(
            f"negative control did not discriminate bad={bad_verdict} good={good_verdict}"
        )
    if not mutant_claim:
        return _fail("planted-bad composer is not actually authorizing")
    if honest_claim:
        return _fail("honest composer authorized legal NO + risk ACCEPT")

    recount = independent_recount()
    if recount["c15_c16_distance"] <= recount["threshold"]:
        return _fail("recount C15 vs C16 collapsed")
    if recount["nearest_sibling_legal"]["same_signature"]:
        return _fail("recount legal sibling same signature")
    if recount["nearest_sibling_risk"]["same_signature"]:
        return _fail("recount risk sibling same signature")

    if ART.is_file():
        text = ART.read_text(encoding="utf-8")
        doc = json.loads(text)
        if "SUCCESS:CNL-0111" not in text:
            return _fail("sentinel-absent")
        st = str(doc.get("state") or "").upper()
        if st in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
            return _fail(f"self-declared {st}")
        measured = doc.get("measured") or {}
        if measured.get("c15_c16_distance") != recount["c15_c16_distance"]:
            return _fail("artifact c15_c16_distance disagree")
        art_legal = (measured.get("nearest_sibling_legal") or {}).get("neighbour_id")
        art_risk = (measured.get("nearest_sibling_risk") or {}).get("neighbour_id")
        if art_legal != recount["nearest_sibling_legal"]["neighbour_id"]:
            return _fail("artifact legal neighbour disagree")
        if art_risk != recount["nearest_sibling_risk"]["neighbour_id"]:
            return _fail("artifact risk neighbour disagree")
        envelope = V.load_schema()
        envelope.pop("_cnl0111_schema_rel", None)
        schema_art = V.Draft202012Validator(envelope)
        n_art = V.error_count(schema_art, doc)
        if n_art != 0:
            return _fail(f"artifact schema errors={n_art}")
        print("artifact_recount_agrees=true")
        print(f"artifact_schema_errors={n_art}")
    else:
        print("artifact_absent_at_probe2_run")

    print(
        json.dumps(
            {
                "probe": "probe2-schema-and-negative-control",
                "schema_report": schema_report,
                "planted_bad_authorized": mutant_claim,
                "honest_authorized": honest_claim,
                "check_on_planted_bad": bad_verdict,
                "check_on_honest": good_verdict,
                "recount": {
                    "c15_c16_distance": recount["c15_c16_distance"],
                    "legal_neighbour": recount["nearest_sibling_legal"]["neighbour_id"],
                    "risk_neighbour": recount["nearest_sibling_risk"]["neighbour_id"],
                },
                "negative_control_verbatim": NEGATIVE_VERBATIM,
            },
            sort_keys=True,
        )
    )
    print(
        "negative control on the state it is meant to reject: "
        "legal=PROHIBITED risk=ACCEPT mutant_authorized=true -> FIRE"
    )
    print(
        f"fired_on_bad={fired_on_bad} silent_on_good={silent_on_good} "
        f"record_error_count={schema_report['record_error_count']} "
        f"invalid_error_count={schema_report['invalid_error_count']}"
    )
    print("SUCCESS:CNL-0111-probe2 schema zero-error plus negative control FIRE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
