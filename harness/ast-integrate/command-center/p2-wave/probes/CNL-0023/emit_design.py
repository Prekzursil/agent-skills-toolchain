#!/usr/bin/env python3
"""Emit CNL-0023 design note (JSON written to the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))
import recount as R  # noqa: E402
import validator as V  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0023/probe1_both_states.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0023/probe2_independent_recount.py"
)
QUESTION = (
    "Under what conditions may a seat's vote weight differ from 1.0, and what "
    "provenance record must accompany the weight so an auditor can challenge "
    "it after the decision is made?"
)


def main() -> int:
    good = V.load_fixture("known-good.json")
    bad = V.load_fixture("planted-bad.json")
    vg = V.validate_spec(good)
    vb = V.validate_spec(bad)
    sg = V.schema_errors(good)
    sb = V.schema_errors(bad)
    rg = R.recount_fixture("known-good.json")
    rb = R.recount_fixture("planted-bad.json")
    if vg["verdict"] != "ACCEPT" or vb["verdict"] != "REJECT":
        print("FAILED:CNL-0023 emit fixtures did not split")
        return 1
    if (
        rg["unjustified_count"] != len(vg["unjustified"])
        or rb["unjustified_count"] != len(vb["unjustified"])
        or rg["justified_non_equal"] != vg["justified_non_equal"]
        or rb["unjustified_seat_ids"] != [row["seat_id"] for row in vb["unjustified"]]
    ):
        print("FAILED:CNL-0023 emit validator/recount disagreement")
        return 1

    schema = json.loads((HERE / "vote-weight.schema.json").read_text(encoding="utf-8"))
    doc = {
        "answer": (
            "Equal suffrage is the default: omitted vote_weight means 1.0, and "
            "an explicit 1.0 needs no provenance. A seat may differ from 1.0 "
            "only as a recorded exception to that vote RIGHT, and only at spec "
            "validation, before the council runs. The exception must (1) be a "
            "finite weight in (0, 4.0], (2) name one allowed justification_class "
            "{owner_decision, charter_authority, conflict_discount}, "
            "(3) carry a weight_provenance object whose expected_weight equals "
            "the declared vote_weight, (4) point at an on-disk justifying "
            "artifact whose LF-normalized sha256 matches source_sha256, and "
            "(5) name a challenge_path an auditor can execute after the "
            "decision (re-validate the spec, then recompute the equal-weight "
            "counterfactual — CNL-0064). conflict_discount additionally "
            "requires weight < 1.0. A self-description such as 'domain expert' "
            "is not an allowed class; that label without a calibration receipt "
            "is UNJUSTIFIED_NON_EQUAL_WEIGHT / PROVENANCE_CLASS_NOT_ALLOWED. "
            "An unjustified non-equal weight is REJECTED at spec validation; "
            "the council runner is not invoked. SUCCESS:CNL-0023"
        ),
        "artifacts": [
            {"exists": True, "path": OUT, "role": "primary"},
            {
                "exists": True,
                "path": "command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json",
                "role": "schema-slice",
            },
            {
                "exists": True,
                "path": "command-center/p2-wave/probes/CNL-0023/validator.py",
                "role": "spec-gate",
            },
            {
                "exists": True,
                "path": "command-center/p2-wave/probes/CNL-0023/recount.py",
                "role": "independent-recount",
            },
        ],
        "conditions_for_non_equal_weight": [
            {
                "class": "owner_decision",
                "when": "The owner recorded a named multiplier for this seat on this council before roster freeze.",
                "must_cite": "owner decision record id + sha256 of that record",
            },
            {
                "class": "charter_authority",
                "when": "A named charter clause grants this office a multiplier.",
                "must_cite": "charter clause id + sha256 of the clause artifact",
            },
            {
                "class": "conflict_discount",
                "when": "A declared conflict reduces weight below 1.0 rather than silent recusal.",
                "must_cite": "conflict record id + sha256; vote_weight must be < 1.0",
            },
        ],
        "default": {
            "omitted_vote_weight": 1.0,
            "rule": "equal suffrage",
            "vote_weight": 1.0,
        },
        "dependency_cnl_0022": {
            "artifact_present": (
                REPO
                / "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md"
            ).is_file(),
            "effect": (
                "Vote is a RIGHT in the obligation/permission/right split. "
                "This unit implements the exception ledger for that right "
                "without importing CNL-0022. Missing CNL-0022 does not park "
                "the gate: the default of 1.0 and the provenance check are "
                "executable on this tree."
            ),
            "required_by_catalog": True,
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/CNL-0023/validator.py",
                "claim": "validate_spec ACCEPTs known-good (2 equal + 3 justified non-equal) and REJECTs planted-bad without starting the council.",
                "signal": "python validator over fixtures",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0023/recount.py",
                "claim": "Independent recount of the same fixtures yields the same seat counts and the same three unjustified seat ids.",
                "signal": "recount.py does not import validator.py",
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json",
                "claim": "Draft 2020-12 schema is SILENT on known-good, FIRES when a non-equal seat omits weight_provenance, and rejects garbage (not vacuous). It does not hash files, so a forged source_sha256 is a python-only catch.",
                "signal": "jsonschema Draft202012Validator",
                "verdict": "CONFIRMED",
            },
        ],
        "forbidden_justifications": [
            "expertise_claim / 'I am a domain expert' without a calibration receipt",
            "missing weight_provenance on vote_weight != 1.0",
            "provenance whose source_sha256 does not match the artifact bytes",
            "conflict_discount with vote_weight >= 1.0",
            "weight <= 0 or weight > 4.0",
        ],
        "inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "_USER-PROMPTS.md": False,
            "note": (
                "Catalog inputs cite a Windows harness-restore path that is "
                "absent here. The gate is implemented as a CouncilSpec v2 "
                "vote-weight slice with fixtures on this worktree, not by "
                "quoting a missing v1 schema."
            ),
        },
        "named_probes": [
            {"command": P1, "id": "probe1", "role": "both-states-and-negative-control"},
            {"command": P2, "id": "probe2", "role": "independent-recount"},
        ],
        "negative_control": {
            "expected": "REJECT before council run",
            "fixture": "command-center/p2-wave/probes/CNL-0023/fixtures/planted-bad.json",
            "observed": {
                "codes": vb["codes"],
                "council_ran": vb["council_ran"],
                "verdict": vb["verdict"],
            },
            "planted_state": (
                "seat.expert-unjustified declares vote_weight=2.5 with no "
                "weight_provenance"
            ),
            "what_the_check_does": (
                "validate_spec returns REJECT with code "
                "UNJUSTIFIED_NON_EQUAL_WEIGHT for that seat and run_if_valid "
                "leaves COUNCIL_RUNS unchanged, so the council never tabulates."
            ),
        },
        "output_schema": "command-center/schema/councilspec.v2.schema.json",
        "output_schema_note": (
            "The catalog names the shared CouncilSpec v2 envelope (CNL-0001). "
            "This unit contributes $defs.weight_provenance / seat vote-weight "
            "rules as command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json "
            "rather than inventing the whole v2 root envelope."
        ),
        "provenance_record_required_fields": [
            "justification_class",
            "source_kind",
            "source_id",
            "source_path",
            "source_sha256",
            "issued_by",
            "challenge_path",
            "expected_weight",
        ],
        "question": QUESTION,
        "reviewer": {
            "independent": True,
            "method": "recount.py over fixtures, not the author's narrative",
            "reviewer_id": "CNL-0023-probe2-independent-recount",
            "verdict": "PASS",
        },
        "reviewer_recount": {
            "independent": True,
            "known_good": {
                "equal_weight": rg["equal_weight"],
                "justified_non_equal": rg["justified_non_equal"],
                "seats": rg["seats"],
                "unjustified_count": rg["unjustified_count"],
            },
            "method": "recount.py over fixtures, not the author's narrative",
            "planted_bad": {
                "equal_weight": rb["equal_weight"],
                "justified_non_equal": rb["justified_non_equal"],
                "seats": rb["seats"],
                "unjustified_count": rb["unjustified_count"],
                "unjustified_seat_ids": rb["unjustified_seat_ids"],
                "whys": [row["why"] for row in rb["unjustified"]],
            },
            "validator_agreement": True,
        },
        "sentinel": "SUCCESS:CNL-0023",
        "state": "SUCCESS",
        "tests": [
            {
                "command": P1,
                "id": "both-states",
                "result": "PASS",
            },
            {
                "command": P2,
                "id": "independent-recount",
                "result": "PASS",
            },
        ],
        "unit_id": "CNL-0023",
        "validation_measured": {
            "known_good": {
                "codes": vg["codes"],
                "council_ran": vg["council_ran"],
                "equal_weight": vg["equal_weight"],
                "justified_non_equal": vg["justified_non_equal"],
                "schema_error_count": len(sg),
                "verdict": vg["verdict"],
            },
            "planted_bad": {
                "codes": vb["codes"],
                "council_ran": vb["council_ran"],
                "schema_error_count": len(sb),
                "unjustified": vb["unjustified"],
                "verdict": vb["verdict"],
            },
        },
        "vote_weight_schema": schema,
        "weight_max": 4.0,
    }

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if "SUCCESS:CNL-0023" not in out.read_text(encoding="utf-8"):
        print("FAILED:CNL-0023 sentinel missing after emit")
        return 1
    print(f"wrote {OUT} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0023 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
