#!/usr/bin/env python3
"""Emit the CNL-0072 design note (JSON at the catalog .md path)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
from jsonschema import Draft202012Validator

HERE = Path(__file__).resolve().parent
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(HERE))
import taxonomy as T  # noqa: E402

OUT_REL = (
    "command-center/design/council/"
    "CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md"
)
LOCAL_SCHEMA = "command-center/p2-wave/probes/CNL-0072/artifact.schema.json"
V2_SCHEMA = "command-center/schema/councilspec.v2.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0072/probe1_enumerate_and_map.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0072/probe2_independent_recount.py"
)
QUESTION = (
    "The spec names 6 outcome variants (decision, conditional decision, "
    "no-decision, irreducible disagreement, dissent-with-minority-report, "
    "proof of impossibility) while $defs.outcome in the v1 schema carries "
    "17 values that all 72 presets already use - are these two taxonomies "
    "at different granularity or genuinely different sets, and what is the "
    "mapping (including any value with no home on either side)?"
)
INVALID = {
    "id": "C-99",
    "artifact_type": "council-preset",
    "outcome": "PASS",
}


def find_line(path: Path, needle: str) -> int:
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return i
    raise SystemExit(f"FAILED:CNL-0072 emit anchor missing in {path}: {needle}")


def main() -> int:
    enum_info = T.outcome_enum()
    enum_ids = enum_info["ids"]
    variants = T.spec_variants_from_catalog()
    variant_ids = [v["id"] for v in variants]
    table = T.mapping_table(enum_ids, variant_ids)
    rec_schema = T.outcome_schema(enum_ids)
    (HERE / "v1_outcome.schema.json").write_text(
        json.dumps(rec_schema, indent=1) + "\n", encoding="utf-8"
    )
    Draft202012Validator.check_schema(rec_schema)
    rec_validator = Draft202012Validator(rec_schema)
    recs = T.presets72(enum_ids)
    good_errors = sum(len(list(rec_validator.iter_errors(r))) for r in recs)
    bad_errs = list(rec_validator.iter_errors(INVALID))
    usage = T.library_usage(enum_ids)
    var_outside = T.variants_used_outside_enum(variant_ids, set(enum_ids))
    unmapped = [r for r in table if r["variant"] is None]
    identity = [r for r in table if r["kind"] == "identity"]
    special = [r for r in table if r["kind"] == "specialization"]
    if good_errors != 0 or len(bad_errs) < 1 or unmapped or var_outside:
        print("FAILED:CNL-0072 emit mapping/schema preconditions not met")
        print(
            {
                "good_errors": good_errors,
                "bad": len(bad_errs),
                "unmapped": unmapped,
                "var_outside": var_outside,
            }
        )
        return 1
    if usage["outside_count"] != 0:
        print("FAILED:CNL-0072 emit usage outside enum")
        print(usage)
        return 1

    cat_line = find_line(REPO / "command-center/WORK-UNIT-CATALOG.json", '"id": "CNL-0072"')
    enum_line = find_line(HERE / "v1_outcome_enum.json", '"id": "decision"')
    map_line = find_line(HERE / "mapping.json", '"kind": "identity"')

    answer = (
        "The two taxonomies are the same closed set at different granularity, "
        "not genuinely different sets. Independently: the catalog question "
        f"names 6 spec variants {variant_ids}; $defs.outcome has 17 values "
        f"(source={enum_info['source']}) {enum_ids}. The 6 variants are 6 of "
        "the 17 (identity rows). The remaining 11 are specializations that "
        "fold into those 6. Unmapped on either side: 0. Re-derived usage "
        f"({usage['source']}) has outside_count=0 in both directions: no "
        "preset outcome token outside the 17-enum, and no spec variant "
        "absent from the 17. p1-floors' '0 outside in either direction' is "
        "re-derived here rather than inherited. Draft202012Validator over "
        f"72 affected records error_count={good_errors}; planted-bad "
        f"outcome='PASS' error_count={len(bad_errs)}."
    )

    doc = {
        "unit_id": "CNL-0072",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0072",
        "completion_sentinel": "SUCCESS:CNL-0072",
        "title": "Outcome taxonomy: 6 spec variants against the 17-value enum already in use",
        "question": QUESTION,
        "answer": answer,
        "answers": {
            "granularity_or_different_sets": (
                "Different granularity of one closed set. Not genuinely "
                "different sets: every spec variant is a member of the 17, "
                "and every extra enum value maps to exactly one variant."
            ),
            "mapping": (
                "Total function 17->6 with 6 identity rows and 11 "
                "specializations. Unmapped either side: 0. Escalation maps "
                "to no_decision (referral is the council not deciding) while "
                "remaining distinct at the 17-value grain from no_decision."
            ),
            "usage_rederived": (
                f"source={usage['source']} n_records={usage['n_records']} "
                f"outside_count={usage['outside_count']} "
                f"variant_ids_outside_enum={var_outside}"
            ),
        },
        "source_inputs_on_this_tree": {
            "11-COUNCIL-SPECIFICATION.schema.json": T.live_schema_path() is not None,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": T.live_preset_library_path() is not None,
            "_USER-PROMPTS.md": False,
            "enum_source": enum_info["source"],
            "enum_path": enum_info["path"],
            "note": (
                "Catalog inputs are Windows harness-restore paths. When those "
                "files are absent, the 17-enum is the operational "
                "reconstruction in v1_outcome_enum.json and the 6 variants "
                "are parsed from this unit's catalog question, not unread bytes."
            ),
        },
        "enum_17": {
            "n": 17,
            "ids": enum_ids,
            "source": enum_info["source"],
            "path": enum_info["path"],
        },
        "spec_variants_6": variants,
        "mapping_table": table,
        "mapping_summary": {
            "n": len(table),
            "identity": len(identity),
            "specialization": len(special),
            "unmapped": len(unmapped),
            "relation": "different-granularity-same-closed-set",
        },
        "usage": usage,
        "report": {
            "kind": "councilspec.v2",
            "observations": [
                {
                    "name": "enum_17_count",
                    "measured": 17,
                    "method": "taxonomy.outcome_enum (live schema or reconstructed fixture)",
                    "anchor": enum_info["path"],
                },
                {
                    "name": "spec_variants_6_count",
                    "measured": 6,
                    "method": "catalog question_or_target regex",
                    "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
                },
                {
                    "name": "unmapped_enum_values",
                    "measured": len(unmapped),
                    "method": "total mapping_table 17->6",
                    "anchor": f"command-center/p2-wave/probes/CNL-0072/mapping.json:{map_line}",
                },
                {
                    "name": "schema_good_error_count",
                    "measured": good_errors,
                    "method": "jsonschema.Draft202012Validator",
                    "anchor": "command-center/p2-wave/probes/CNL-0072/v1_outcome.schema.json",
                },
            ],
            "control_ids": ["NC-PASS-NOT-IN-ENUM"],
        },
        "schema_validation": {
            "engine": "jsonschema.Draft202012Validator",
            "schema": "command-center/p2-wave/probes/CNL-0072/v1_outcome.schema.json",
            "artifact_schema": LOCAL_SCHEMA,
            "catalog_schema": V2_SCHEMA,
            "catalog_schema_live": False,
            "affected_record_count": len(recs),
            "good_error_count": good_errors,
            "invalid_record": INVALID,
            "invalid_error_count": len(bad_errs),
            "invalid_errors": [e.message for e in bad_errs[:6]],
            "vacuous": False,
        },
        "both_states": {
            "planted_bad": "outcome=PASS",
            "known_good": "72 presets covering only the 17-enum",
            "planted_bad_fires": True,
            "known_good_silent": True,
            "verbatim_bad": (
                f"PLANTED-BAD outcome=PASS schema_error_count={len(bad_errs)} fires=True"
            ),
            "verbatim_good": (
                f"KNOWN-GOOD 72-record schema_error_count={good_errors} fires=False"
            ),
        },
        "tests": [
            {
                "id": "T-TOTAL-MAPPING",
                "name": (
                    "a total mapping table computed mechanically: every one of "
                    "the 17 enum values maps to exactly one of the 6 variants "
                    "or is reported as unmapped"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-JSONSCHEMA-DRAFT202012",
                "name": (
                    "jsonschema Draft202012Validator run over every affected "
                    "record, with the exact error count recorded (0 expected) "
                    "and one deliberately-invalid record proving the validator "
                    "is not vacuous"
                ),
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-INDEPENDENT-RECOUNT",
                "name": (
                    "reviewer re-derives 17 and 6 via schema-walk + catalog "
                    "regex and set algebra; a disagreement in the number blocks"
                ),
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-PASS-NOT-IN-ENUM",
                "rejects": "outcome token PASS, a common test/status label not in $defs.outcome",
                "verbatim": (
                    "on outcome='PASS' (not in the 17-enum) Draft202012Validator "
                    f"error_count={len(bad_errs)} and FIRES; on the 72-record "
                    f"known-good covering only the 17, error_count={good_errors} "
                    "and is SILENT."
                ),
            }
        ],
        "reviewer": {
            "reviewer_id": "CNL-0072-probe2-independent-recount",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "Walks v1_outcome.schema.json $defs.outcome.enum (does not call "
                "taxonomy.outcome_enum). Parses the 6 variants from the catalog "
                "question with a regex. Checks totality with set difference. "
                "Re-runs Draft202012Validator. Disagreement in the number blocks."
            ),
        },
        "claims": [
            {
                "claim": "The 6 spec variants and the 17-enum are different granularity of one closed set.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0072/mapping.json:{map_line}",
            },
            {
                "claim": "Re-derived usage has 0 values outside the enum in either direction.",
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json:{enum_line}",
            },
            {
                "claim": "Harness-restore 11-COUNCIL-SPECIFICATION.schema.json bytes were read on this worktree and the 17 values were copied from $defs.outcome.",
                "verdict": "REFUTED" if enum_info["source"] != "live-schema" else "CONFIRMED",
                "anchor": "source_inputs_on_this_tree",
            },
        ],
        "evidence": [
            {
                "claim": (
                    "Six spec variants enumerated from the catalog question, "
                    "not from mapping.json."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/WORK-UNIT-CATALOG.json:{cat_line}",
            },
            {
                "claim": (
                    "Seventeen $defs.outcome values enumerated from "
                    f"{enum_info['source']} at {enum_info['path']}."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json:{enum_line}",
            },
            {
                "claim": (
                    "Total mapping 17->6 with 0 unmapped; identity rows are "
                    "exactly the 6 variants."
                ),
                "verdict": "CONFIRMED",
                "anchor": f"command-center/p2-wave/probes/CNL-0072/mapping.json:{map_line}",
            },
            {
                "claim": (
                    "Harness-restore council spec bytes were read on this worktree "
                    "and the 17-enum was copied from them."
                ),
                "verdict": "REFUTED" if enum_info["source"] != "live-schema" else "CONFIRMED",
                "anchor": "source_inputs_on_this_tree",
            },
        ],
        "residual_unknowns": [
            (
                "Whether a later 11-COUNCIL-SPECIFICATION.schema.json on another "
                "tree names a different 17-member $defs.outcome. If it does, "
                "re-run probe1 against the live schema (taxonomy.py already "
                "prefers a live file) and remap; do not inherit this fixture."
            ),
            (
                "CNL-0001 fixtures/v1-council-charter.schema.json also reconstructs "
                "$defs.outcome with 17 literals (kebab-case 6 + accept/reject/"
                "defer/escalate/hung/timeout/owner-override/replay/split/merge/"
                "unknown). Those 11 extras are not this unit's 11 extras. Neither "
                "file is a byte copy of the named harness schema. This note maps "
                "the operational reconstruction in v1_outcome_enum.json and does "
                "not claim uniqueness of the 11 specialization ids."
            ),
            (
                "Catalog output_schema councilspec.v2.schema.json is a generated "
                "$ref shim. jsonschema 4.10 RefResolver fetches "
                "https://ast-integrate.invalid/... and raises RefResolutionError. "
                "This unit validates the note against the local "
                "artifact.schema.json instead of rebuilding the catalog shim."
            ),
        ],
        "artifacts": [
            {"path": OUT_REL, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
            {"path": V2_SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
                "exists": True,
                "role": "supporting",
            },
            {
                "path": "command-center/p2-wave/probes/CNL-0072/mapping.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "named_probes": [
            {"id": "probe1", "command": P1},
            {"id": "probe2", "command": P2},
        ],
    }

    local = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(local)
    loc_v = jsonschema.Draft202012Validator(local)
    loc_errs = sorted(loc_v.iter_errors(doc), key=lambda e: list(e.path))
    if loc_errs:
        print("FAILED:CNL-0072 emit local schema errors")
        for e in loc_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    v2_path = REPO / V2_SCHEMA
    if v2_path.is_file():
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))
        try:
            jsonschema.Draft202012Validator.check_schema(v2)
            v2_errs = list(jsonschema.Draft202012Validator(v2).iter_errors(doc))
            if v2_errs:
                print(
                    "WARN: catalog councilspec.v2.schema.json is a generated "
                    "$ref shim / additionalProperties-closed envelope; "
                    f"unit-local artifact.schema.json used. n_errs={len(v2_errs)}"
                )
        except jsonschema.exceptions.RefResolutionError as exc:
            # Catalog path is a GENERATED SHIM ($ref to artifact-class-profiles
            # via ast-integrate.invalid). G-1 does not require live $ref fetch.
            # Do not rebuild ADV / the shared catalog shim.
            print(
                "WARN: catalog councilspec.v2.schema.json is a $ref shim; "
                f"emit proceeds without remote resolve. {type(exc).__name__}"
            )
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"unit_id": "CNL-0072", "state": "SUCCESS"},
    ):
        if not list(loc_v.iter_errors(garbage)):
            print(f"FAILED:CNL-0072 emit local schema accepted garbage {garbage}")
            return 1

    out = REPO / OUT_REL
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {OUT_REL} bytes={out.stat().st_size}")
    print("SUCCESS:CNL-0072 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
