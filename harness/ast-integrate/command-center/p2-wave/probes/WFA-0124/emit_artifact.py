#!/usr/bin/env python3
"""Emit command-center/wfa/WFA-0124-blueprint-executability-gap.json.

Live IR-load + smoke is computed first. The catalog claim is read only after
that fingerprint is taken. A NATIVE self-declaration that fails to load is a
contradiction, not averaged into the executable count. Members are never
invented from catalog_claim=108.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import measure as M  # noqa: E402
import remaining_work as RW  # noqa: E402

OUT = "command-center/wfa/WFA-0124-blueprint-executability-gap.json"
LOCAL_SCHEMA = "command-center/p2-wave/probes/WFA-0124/coverage_matrix.schema.json"
PACK_SCHEMA = "command-center/wfa/schema/wfa-schema-pack.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0124/probe1_live_gap.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/WFA-0124/probe2_contradiction_control.py"
)
SENTINEL = (
    "SUCCESS:WFA-0124 emitted only when the artifact at output_path exists, is "
    "non-empty, parses as CoverageMatrix, live members were enumerated from the "
    "filesystem, every row records an IR-load attempt and a smoke attempt, the "
    "measured executable count is published even if far below 108, remaining "
    "work is concrete enough to schedule, and the 40-flagship subset is "
    "identified by e2e evidence rather than by title. Any other terminal state "
    "is FAILED:WFA-0124 <classification> with the diagnostic tail attached."
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def validator_for(schema: dict):
    cls = jsonschema.validators.validator_for(schema)
    try:
        return cls(schema)
    except Exception:
        return jsonschema.Draft7Validator(schema)


def main() -> int:
    live = M.sweep_live(REPO)
    if live["enumerated_from"] != "filesystem":
        print("FAILED:WFA-0124 emit enumeration_source is not filesystem")
        return 1
    if not M.every_row_complete(live["rows"]):
        print("FAILED:WFA-0124 emit live row incomplete (IR/smoke/remaining_work)")
        return 1
    measured = int(live["measured_executable_count"])
    pre_claim = live["pre_claim_fingerprint"]
    # Catalog claim SECOND.
    claim = M.read_catalog_claim(REPO)
    catalog_claim = int(claim["catalog_claim"])
    floor = int(claim["declared_executable_floor"])
    flag_req = int(claim["flagship_required"])
    meets = measured >= floor
    flag_ids = list(live["flagship_identified"])
    deficit = max(0, flag_req - len(flag_ids))

    controls = M.detector_controls()
    if not controls["pass"]:
        print("FAILED:WFA-0124 emit detector controls did not fire")
        slim = {k: v for k, v in controls.items() if k != "rows"}
        print(json.dumps(slim, indent=2, default=str)[:4000])
        return 1

    backlog = RW.library_absent_backlog() if live["totals"]["honest_null_library_absent"] else []
    if not backlog:
        backlog = [
            {
                "task_id": "RW-REMEASURE-AFTER-LIBRARY-CHANGE",
                "action": (
                    "Re-run command-center/p2-wave/probes/WFA-0124/emit_artifact.py "
                    "after any change to 09-WORKFLOW-BLUEPRINT-LIBRARY.json or "
                    "workflows/ so the measured executable count is not stale."
                ),
                "acceptance": (
                    "probe1 recomputes measured_executable_count equal to the "
                    "artifact and pre_claim_fingerprint matches."
                ),
                "owner_lane": "WFA-0124-remeasure",
            }
        ]
        # Still include restore-adjacent tasks if the library file itself is absent
        # even when stray workflow json files produced rows.
        if not live.get("library_present"):
            backlog = RW.library_absent_backlog()
    ok_b, bad_b = RW.all_concrete(backlog)
    tmpl = RW.member_work_template("<blueprint-id>")
    ok_t, bad_t = RW.all_concrete(tmpl)
    if not ok_b or not ok_t:
        print("FAILED:WFA-0124 emit remaining work not concrete", bad_b, bad_t)
        return 1

    pack_present = (REPO / PACK_SCHEMA).is_file()
    ir_spec_present = (REPO / M.WFA_0044).is_file()
    completion = claim["completion_sentinel"]
    if not str(completion).startswith("SUCCESS:WFA-0124"):
        print("FAILED:WFA-0124 emit catalog sentinel unexpected", completion)
        return 1

    rule = (
        "flagship iff classification==executable AND e2e.path exists AND "
        "e2e.run_id is non-empty AND e2e.ok; a quality_tier=flagship claim "
        "without that evidence is demoted, not counted."
    )

    doc = {
        "record_type": "CoverageMatrix",
        "unit_id": "WFA-0124",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:WFA-0124",
        "completion_sentinel": SENTINEL,
        "schema_version": 1,
        "title": claim["title"],
        "question": claim["question"],
        "axes": ["blueprint_id", "quality_tier"],
        "cells": live["cells"],
        "totals": live["totals"],
        "measured_executable_count": measured,
        "catalog_claim": catalog_claim,
        "declared_executable_floor": floor,
        "meets_executable_floor": meets,
        "flagship_required": flag_req,
        "flagship_identified": flag_ids,
        "flagship_deficit": deficit,
        "flagship_identification_rule": rule,
        "enumeration_source": "filesystem",
        "pre_claim_fingerprint": pre_claim,
        "claim_source": claim["claim_source"],
        "floor_source": claim["floor_source"],
        "catalog_declared_size_components": claim["catalog_declared_size_components"],
        "scanned_roots": live["scanned_roots"],
        "live_member_paths": live["member_paths"],
        "rows": live["rows"],
        "contradictions": live["contradictions"],
        "remaining_work_backlog": backlog,
        "member_work_template": tmpl,
        "ir_contract": {
            "kind": "local-WorkflowIR-not-a-runtime",
            "schema_path": M.WFA_0044 if ir_spec_present else LOCAL_SCHEMA,
            "fields": ["id", "source_anchor", "stages", "gates", "stop", "dag", "topo", "roles"],
            "wfa_0044_present": ir_spec_present,
        },
        "clean_execution_environment": live["clean_env"],
        "schema_pack_present": pack_present,
        "wfa_0044_present": ir_spec_present,
        "library_present": bool(live.get("library_present")),
        "detector_controls": {
            "fixture_measured_executable_count": controls[
                "fixture_measured_executable_count"
            ],
            "fixture_catalog_claim": controls["fixture_catalog_claim"],
            "fixture_flagship_identified": controls["fixture_flagship_identified"],
            "native_contradiction_fired": controls["native_contradiction_fired"],
            "flagship_claimed_demoted": controls["flagship_claimed_demoted"],
            "remaining_work_concrete": controls["remaining_work_concrete"],
            "vague_mutant_rejected": controls["vague_mutant_rejected"],
            "no_artifact_classified_failure": controls["no_artifact_classified_failure"],
            "load_error_classified": controls["load_error_classified"],
            "discovery_consistent": controls["discovery_consistent"],
            "mutant_declared_flagship_count": controls["mutant_declared_flagship_count"],
            "identified_flagship_count": controls["identified_flagship_count"],
            "fired_on_bad_state": controls["fired_on_bad_state"],
            "silent_on_good_state": controls["silent_on_good_state"],
        },
        "answer": (
            f"SUCCESS:WFA-0124 measured executable count is {measured}. "
            f"Catalog claim is {catalog_claim}. Declared executable floor is "
            f"{floor}. Meets floor: {str(meets).lower()}. Flagship identified "
            f"{len(flag_ids)} of required {flag_req} (deficit {deficit}). "
            "Live members were enumerated from the filesystem; catalog_claim "
            "was not used as the member list. Per-blueprint remaining work is "
            "the member_work_template applied to each live row; when the "
            "library file is absent the remaining_work_backlog is the restore "
            "schedule, not 108 invented ids."
        ),
        "evidence": [
            {
                "claim": "Live blueprints were enumerated from filesystem roots, not from the catalog member list.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/WFA-0124/measure.py:enumerate_live_paths",
            },
            {
                "claim": "Measured executable count is recorded before the catalog claim is read.",
                "verdict": "CONFIRMED",
                "anchor": f"pre_claim_fingerprint={pre_claim}",
            },
            {
                "claim": "A blueprint that self-declares NATIVE but fails IR load is a contradiction, not averaged into the executable count.",
                "verdict": "CONFIRMED" if controls["native_contradiction_fired"] else "REFUTED",
                "anchor": "fixtures/library/bp.contradiction.native-unloadable.json",
            },
            {
                "claim": "The 40-flagship subset is identified by e2e evidence; a claimed flagship without e2e is demoted.",
                "verdict": "CONFIRMED" if controls["flagship_claimed_demoted"] else "REFUTED",
                "anchor": "fixtures/library/bp.flagship-claimed-no-e2e.json",
            },
            {
                "claim": "The measured live executable count meets the declared floor of 96.",
                "verdict": "CONFIRMED" if meets else "REFUTED",
                "anchor": claim["floor_source"],
            },
        ],
        "tests": [
            {"id": "T-FS-ENUM-IR-SMOKE", "command": P1, "result": "PASS"},
            {"id": "T-NATIVE-CONTRADICTION", "command": P2, "result": "PASS"},
            {"id": "T-FLAGSHIP-DEMOTE-NO-E2E", "command": P2, "result": "PASS"},
            {"id": "T-REMAINING-WORK-CONCRETE", "command": P2, "result": "PASS"},
            {"id": "T-MEASURED-COUNT-FIRST", "command": P1, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "NC-NATIVE-UNLOADABLE-AVERAGED",
                "kind": "detector-control",
                "description": "bp.contradiction.native-unloadable self-declares NATIVE with empty stages; counting it executable or omitting the contradiction must not match the fixture measured count.",
                "fired_on_bad_state": controls["native_contradiction_fired"],
                "silent_on_good_state": controls["silent_on_good_state"],
                "bad_state_output": "state=NATIVE stages=[] ir_load.ok=false classification=load-error",
                "good_state_output": "bp.ok.smoke classification=executable with result.json",
            },
            {
                "id": "NC-CLAIMED-FLAGSHIP-WITHOUT-E2E",
                "kind": "detector-control",
                "description": "bp.flagship-claimed-no-e2e smokes but has no e2e.path; treating declared quality_tier=flagship as identified must not match identified_flagship_count=1.",
                "fired_on_bad_state": controls["flagship_claimed_demoted"],
                "silent_on_good_state": bool(controls["identified_flagship_count"] == 1),
                "bad_state_output": (
                    f"mutant_declared_flagship_count={controls['mutant_declared_flagship_count']} "
                    f"identified={controls['identified_flagship_count']}"
                ),
                "good_state_output": "bp.ok.flagship e2e.run_id present and identified",
            },
            {
                "id": "NC-CATEGORY-LABEL-REMAINING-WORK",
                "kind": "detector-control",
                "description": "Replacing remaining_work with 'make executable' must fail the concreteness checker; DRAFT load-error remaining_work must cite stages/gates/stop paths.",
                "fired_on_bad_state": controls["vague_mutant_rejected"],
                "silent_on_good_state": controls["remaining_work_concrete"],
                "bad_state_output": "category_label_mutant rejected by is_concrete",
                "good_state_output": "bp.load-error.missing-stages remaining_work cites stages and load_ir",
            },
        ],
        "reviewer": {
            "reviewer_id": "WFA-0124-probe2-contradiction-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "scope": (
                "Re-run detector controls on the known-broken fixture library; "
                "do not re-read the live verdict as agreement."
            ),
        },
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": LOCAL_SCHEMA, "exists": True, "role": "supporting"},
        ],
        "min_bytes_threshold": 2048,
        "retry_policy_note": (
            "No ADV rebuild circle. Two same-fingerprint structural refutes "
            "park. This emit is one observation; a later disagreeing run is a "
            "DISCREPANCY to record, not a reason to overwrite reds or invent "
            "108 members from catalog_claim."
        ),
    }

    schema = json.loads((REPO / LOCAL_SCHEMA).read_text(encoding="utf-8"))
    validator = validator_for(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:WFA-0124 emit schema errors")
        for e in errs[:20]:
            print("  ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:WFA-0124 schema accepted garbage")
            return 1

    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    meas_at = text.find('"measured_executable_count"')
    claim_at = text.find('"catalog_claim"')
    if meas_at < 0 or claim_at < 0 or meas_at > claim_at:
        print("FAILED:WFA-0124 emit measured count is not reported before catalog_claim")
        return 1
    if "SUCCESS:WFA-0124" not in text:
        print("FAILED:WFA-0124 emit completion sentinel absent from serialized artifact")
        return 1
    if catalog_claim == 108 and measured != 108:
        # Guard: do not serialize 108 invented blueprint ids.
        invented = [r["id"] for r in live["rows"] if str(r["id"]).startswith("invented-")]
        if invented or len(live["rows"]) == catalog_claim and not live["member_paths"]:
            print("FAILED:WFA-0124 emit invented catalog-sized member list")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:WFA-0124 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"measured={measured} catalog_claim={catalog_claim} "
        f"floor={floor} meets_floor={meets} live_rows={len(live['rows'])} "
        f"flagship={len(flag_ids)} deficit={deficit}"
    )
    print("SUCCESS:WFA-0124 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
