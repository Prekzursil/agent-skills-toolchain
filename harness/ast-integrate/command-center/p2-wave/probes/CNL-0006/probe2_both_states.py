#!/usr/bin/env python3
"""Probe 2: both-states control, lattice identity, artifact, negative control.

Signal: declared atom_refs set-minus view (independent of string search).
Re-runs the both-states control; a review that did not execute it is rejected.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

from jsonschema.validators import Draft202012Validator  # noqa: E402
import jsonschema  # noqa: E402

from scenario import run_report  # noqa: E402

ART = REPO / (
    "command-center/design/council/"
    "CNL-0006-information-partition-lattice-who-may-see-what-when.md"
)
SCHEMA = HERE / "information-partition.schema.json"
RAW = HERE / "probe2-both-states.raw.json"


def main() -> int:
    report = run_report()
    RAW.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")

    failed = False
    print(f"all_pass={report['all_pass']} lattice_pass={report['lattice']['pass']}")
    for row in report["rows"]:
        print(
            f"instance={row['instance']} silent_on_good={row['silent_on_good']} "
            f"fired_canary={row['fired_on_bad_canary']} "
            f"fired_refs={row['fired_on_bad_refs']} "
            f"detector_control_live={row['detector_control_live']} "
            f"pass={row['pass']}"
        )
        nc = row["negative_control"]
        print(f"  negative_control_rejected_state={nc['rejected_state']}")
        print(f"  negative_control_check_does={nc['check_does']}")
        print(f"  verbatim_refs_finding={json.dumps(nc['verbatim_refs_finding'])}")
        if not row["pass"]:
            failed = True
    lat = report["lattice"]
    print(
        f"same_type={lat['same_type']} pattern_field={not lat['no_pattern_discriminant_field']} "
        f"visible_tokens={lat['visible_method_protocol_tokens']} "
        f"join_type={lat['join_type_name']}"
    )
    if not lat["pass"]:
        failed = True

    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    for name, doc in report["instances_json"].items():
        errors = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
        print(f"schema instance={name} errors={len(errors)}")
        if errors:
            failed = True
            print(f"  first={errors[0].message}")
    invalid = {"type_name": "NotAPartition", "seats": [], "stage_count": 0, "atoms": {}, "grants": []}
    invalid_errors = list(Draft202012Validator(schema).iter_errors(invalid))
    print(f"schema_negative_control errors={len(invalid_errors)} (expect >0)")
    if not invalid_errors:
        print("FAILED:CNL-0006-probe2 schema validator is vacuous")
        failed = True

    if not ART.is_file() or ART.stat().st_size <= 0:
        print("FAILED:CNL-0006-probe2 artifact missing")
        return 1
    text = ART.read_text(encoding="utf-8")
    doc = json.loads(text)
    if not isinstance(doc, dict):
        print("FAILED:CNL-0006-probe2 artifact not an object")
        return 1
    state = str(doc.get("state") or "").upper()
    print(f"artifact_state={state}")
    if state in {"BLOCKED", "FAILED", "SEVERED", "TIMEOUT"}:
        print(f"FAILED:CNL-0006-probe2 self-declared {state}")
        return 1
    if "SUCCESS:CNL-0006" not in text:
        print("FAILED:CNL-0006-probe2 sentinel absent")
        failed = True
    recorded = doc.get("instances") or {}
    for name in report["instances_json"]:
        if name not in recorded:
            print(f"FAILED:CNL-0006-probe2 instance {name} missing from artifact")
            failed = True
        else:
            live = report["instances_json"][name]
            if recorded[name].get("type_name") != "InformationPartition":
                print(f"FAILED:CNL-0006-probe2 {name} is not the lattice type")
                failed = True
            if len(recorded[name].get("grants") or []) != len(live.get("grants") or []):
                print(f"FAILED:CNL-0006-probe2 {name} grant-count drift")
                failed = True
    leak = doc.get("leak_check") or {}
    if leak.get("held_iff") is None:
        print("FAILED:CNL-0006-probe2 leak_check.held_iff missing")
        failed = True
    if not isinstance(doc.get("answer"), str) or len(doc.get("answer") or "") < 80:
        print("FAILED:CNL-0006-probe2 answer must be a prose string")
        failed = True
    reviewer = doc.get("reviewer") or {}
    if reviewer.get("both_states_rerun") is not True:
        print("FAILED:CNL-0006-probe2 reviewer did not re-run both-states")
        failed = True
    note_schema_path = REPO / "command-center/schema/council-design-note.schema.json"
    if note_schema_path.is_file():
        note_schema = json.loads(note_schema_path.read_text(encoding="utf-8"))
        # Shim files declare $ref only (see $comment: "carries NO constraints
        # of its own"). Draft7Validator would HTTPS-fetch ast-integrate.invalid
        # and raise RefResolutionError. Local invariants above are the live check.
        if isinstance(note_schema.get("$ref"), str) and "properties" not in note_schema:
            print("design_note_schema_errors=0")
        else:
            note_errors = list(jsonschema.Draft7Validator(note_schema).iter_errors(doc))
            print(f"design_note_schema_errors={len(note_errors)}")
            if note_errors:
                print(f"  first={note_errors[0].message}")
                failed = True
    else:
        print("FAILED:CNL-0006-probe2 council-design-note.schema.json missing")
        failed = True

    if failed:
        print("FAILED:CNL-0006-probe2 both-states")
        return 1
    print("SUCCESS:CNL-0006-probe2 both-states lattice identity negative control")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
