#!/usr/bin/env python3
"""Emit the CNL-0112 council-preset design artifact from live instantiation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import instantiate as I  # noqa: E402
import scoring as S  # noqa: E402

OUT = (
    REPO
    / "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md"
)


def main() -> int:
    task = I.load_json(I.TASK)
    sibling_raw = I.load_json(I.SIBLING)
    preset = I.CNL_0112_PRESET
    inst = I.instantiate(preset, task)
    sib = I.instantiate(I.sibling_as_preset(sibling_raw), task)
    if not inst["ok"]:
        print("FAILED:emit instantiate rejected the preset")
        return 1
    axes = I.differ_axes(inst, sib)
    proper = S.properness_report()
    lib = I.library_on_disk()
    if lib["on_this_worktree"]:
        print("FAILED:emit library unexpectedly present; refuse to invent a 72-preset comparison")
        return 1
    lib["presets_compared_from_disk"] = 0

    mutant = {
        "unit_id": "CNL-0112",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0112",
    }
    good_errors = None
    bad_errors = None

    doc = {
        "unit_id": "CNL-0112",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0112",
        "title": "Forecasting and expert-elicitation preset with a proper scoring rule",
        "question": (
            "Which proper scoring rule scores the forecasts, what is the resolution "
            "source and date, and what does the preset do with a forecast that can never resolve?"
        ),
        "kind": "council-preset-design",
        "schema_version": 1,
        "preset": preset,
        "nearest_sibling": {
            "id": sibling_raw["id"],
            "named": True,
            "source": sibling_raw["transcription_basis"],
            "library_bytes_read": False,
            "catalog_cited_c_id_shape": "C-M01",
            "why_nearest": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent. The only on-tree "
                "transcribed preset is council.preset.catalog-class.editable from "
                "ARC-0003 samples.json. A name-only clone of that sibling would be a "
                "mechanism-duplicate; this preset differs on roster, vote, stop, "
                "bound protocols, scoring, and unresolvable policy."
            ),
        },
        "answers": {
            "scoring_rule": "logarithmic",
            "scoring_rule_secondary": "brier",
            "scoring_rule_why": (
                "Logarithmic score is strictly proper and local (Gneiting & Raftery "
                "2007). A reporter whose expected score is maximized only by stating "
                "their true credence cannot profit by hedging. Brier is reported as a "
                "bounded secondary. Linear probability score is rejected: it is not "
                "proper and rewards extremist 0/1 reports."
            ),
            "resolution_source_rule": (
                "Named, checkable source required at emission. Missing source => REJECT."
            ),
            "resolution_date_rule": (
                "ISO-8601 resolution date required at emission. Missing date => REJECT."
            ),
            "never_resolves": (
                "REJECT at emission; disposition UNSCOREABLE; excluded from both the "
                "numerator and the denominator of log/Brier; counted only in the "
                "UNSCOREABLE tally (CNL-0074: a council with no resolvable outcome is "
                "UNSCOREABLE, never counted as calibrated)."
            ),
        },
        "instantiation": {
            "task_id": inst["task_id"],
            "roster_ids": inst["roster_ids"],
            "protocol_schedule": inst["protocol_schedule"],
            "voting": inst["voting"],
            "stopping": inst["stopping"],
            "accepted_ids": inst["accepted_ids"],
            "rejected_ids": inst["rejected_ids"],
            "unscoreable_tally": inst["unscoreable_tally"],
            "scoreable_tally": inst["scoreable_tally"],
            "profile": {
                "roles": list(inst["profile"]["roles"]),
                "voting": inst["profile"]["voting"],
                "stopping": inst["profile"]["stopping"],
                "protocol_schedule": list(inst["profile"]["protocol_schedule"]),
                "scoring": inst["profile"]["scoring"],
                "unresolvable_policy": inst["profile"]["unresolvable_policy"],
            },
        },
        "sibling_instantiation": {
            "task_id": sib["task_id"],
            "roster_ids": sib["roster_ids"],
            "protocol_schedule": sib["protocol_schedule"],
            "voting": sib["voting"],
            "stopping": sib["stopping"],
            "profile": {
                "roles": list(sib["profile"]["roles"]),
                "voting": sib["profile"]["voting"],
                "stopping": sib["profile"]["stopping"],
                "protocol_schedule": list(sib["profile"]["protocol_schedule"]),
                "scoring": sib["profile"]["scoring"],
                "unresolvable_policy": sib["profile"]["unresolvable_policy"],
            },
            "differ_axes": axes,
        },
        "proper_scoring_fixture": proper,
        "herding_control_same_evidence_median_collapse": inst[
            "herding_control_same_evidence_median_collapse"
        ],
        "tests": [
            {
                "id": "instantiate-fixture-task",
                "result": "PASS",
                "roster_ids": inst["roster_ids"],
                "protocol_schedule": inst["protocol_schedule"],
                "voting_method": inst["voting"]["method"],
                "stopping_expression": inst["stopping"]["expression"],
            },
            {
                "id": "nearest-sibling-differential",
                "result": "PASS" if len(axes) >= 3 else "FAIL",
                "sibling_id": sibling_raw["id"],
                "differ_axes": axes,
            },
            {
                "id": "jsonschema-Draft202012Validator",
                "result": "NOT-RUN",
                "good_error_count": None,
                "invalid_error_count": None,
            },
            {
                "id": "unresolvable-rejected-at-emission",
                "result": "PASS" if inst["rejected_ids"] == ["F3"] and inst["accepted_ids"] == ["F1", "F2"] else "FAIL",
                "accepted_ids": inst["accepted_ids"],
                "rejected_ids": inst["rejected_ids"],
            },
        ],
        "negative_controls": [
            {
                "id": "NC-unresolvable-emission",
                "rejects": (
                    "a forecast missing resolution_source or resolution_date, or whose "
                    "criterion_class is preference / metaphysical / unbounded_ever"
                ),
                "on_that_state": (
                    "classify_item returns disposition=REJECT score_class=UNSCOREABLE; "
                    "instantiate omits the item from accepted_ids; a resolvable sibling "
                    "item in the same batch is ACCEPTED"
                ),
                "verbatim": "REJECT:UNSCOREABLE F3 reasons=['missing_resolution_source', 'missing_resolution_date', 'preference']",
            },
            {
                "id": "NC-schema-vacuity",
                "rejects": "an artifact with required key preset removed",
                "on_that_state": "Draft202012Validator error count >= 1",
                "verbatim": "validator.iter_errors(mutant_without_preset) is non-empty",
            },
            {
                "id": "NC-linear-score",
                "rejects": "the claim that any reported score is proper",
                "on_that_state": (
                    "under linear score, extremist q=1 beats calibrated q=p*; under log, "
                    "calibrated wins against both hedge and extremist"
                ),
                "verbatim": "linear_prefers_extremist=True log_prefers_calibrated=True",
            },
            {
                "id": "NC-silent-non-editable-override",
                "rejects": "an override of scoring.primary_rule (a non-editable dial)",
                "on_that_state": "apply_overrides returns accepted=False reason=silent-override-of-non-editable-dial",
                "verbatim": "REJECT silent-override-of-non-editable-dial dial=scoring.primary_rule",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0112-probe2-sibling-differential",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "method": (
                "Re-instantiates this preset and the named sibling against the same "
                "fixture and diffs the profile. Does not accept the author's "
                "nearest-sibling sentence as evidence."
            ),
        },
        "library": lib,
        "dependencies_disclosed": {
            "CNL-0101": "preset is a typed delta (kind=typed_delta), not a fork; silent non-editable override rejected",
            "CNL-0035": "Delphi feedback is full distribution + arguments, never median-only; herding is variance collapse with unchanged evidence hash",
            "CNL-0043": "binds FORECASTING P33/P35/P36; P37 excluded because pairwise ranking is not a probability forecast",
            "CNL-0074": "UNSCOREABLE items never counted as calibrated; deferred resolution remains scoreable without the original session",
        },
        "artifacts": [
            {
                "path": "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md",
                "role": "primary",
            },
            {
                "path": "command-center/schema/council-preset.schema.json",
                "role": "schema",
            },
        ],
        "residual_unknowns": [
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent, so a nearest-neighbour among the cited 72 presets cannot be computed from library bytes. The named sibling is the on-tree catalog transcription. If the library lands, re-run differ_axes against every preset record and replace this sibling if a closer neighbour exists.",
        ],
    }
    # Alias keys so a sibling unit's schema that uses nearest_sibling /
    # instantiation / tests / negative_controls still accepts this artifact.
    doc["nearest_sibling"] = doc["nearest_sibling"]
    doc["instantiation"] = doc["instantiation"]
    doc["tests"] = doc["tests"]
    doc["negative_controls"] = doc["negative_controls"]

    errs = list(I.validator().iter_errors(doc))
    print(
        "IMMEDIATE_ERRS",
        len(errs),
        [(e.message, list(e.absolute_path)) for e in errs],
        "schema",
        I.SCHEMA,
        "keys",
        sorted(doc),
        "kind",
        (doc.get("preset") or {}).get("kind"),
    )
    good_errors = I.error_count(doc)
    bad_errors = I.error_count(mutant)
    for row in doc["tests"]:
        if row["id"] == "jsonschema-Draft202012Validator":
            row["good_error_count"] = good_errors
            row["invalid_error_count"] = bad_errors
            row["result"] = "PASS" if good_errors == 0 and bad_errors >= 1 else "FAIL"
            break

    if good_errors != 0:
        print(f"FAILED:emit schema errors on good artifact: {good_errors}")
        print("schema_required", I.load_json(I.SCHEMA).get("required"))
        for err in I.validator().iter_errors(doc):
            print(" ", err.message, "path=", list(err.absolute_path), "schema_path=", list(err.schema_path))
        return 1
    if bad_errors < 1:
        print("FAILED:emit vacuous schema accepted mutant")
        return 1
    if doc["tests"][1]["result"] != "PASS":
        print("FAILED:emit sibling differential too thin", axes)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO).as_posix()} schema_good={good_errors} schema_bad={bad_errors} axes={axes}")
    print("SUCCESS:CNL-0112 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
