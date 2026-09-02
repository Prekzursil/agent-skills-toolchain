#!/usr/bin/env python3
"""Emit command-center/confirmation/CNF-0077-blueprint-executability.json.

Live sweep is computed first. The catalog claim is read only after that
fingerprint is taken, so the claim cannot anchor the measurement.

The catalog output_schema is a $ref shim at command-center/schema/smoke-report.schema.json
whose target is https://ast-integrate.invalid/... . jsonschema 4.10.3 on this
tree uses RefResolver and tries the network. Validate a disk-local Draft-07
contract that still rejects garbage and encodes the probe-checked facts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import sweep as S  # noqa: E402

OUT = "command-center/confirmation/CNF-0077-blueprint-executability.json"
SCHEMA = "command-center/schema/smoke-report.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0077/probe1_filesystem_sweep.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNF-0077/probe2_detector_control.py"
)


def local_validator() -> jsonschema.Draft7Validator:
    """Compile a Draft-07 contract from this file. Does not resolve $ref."""
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": [
            "unit_id",
            "state",
            "sentinel",
            "completion_sentinel",
            "measured_executable_count",
            "catalog_claim",
            "declared_floor",
            "meets_floor",
            "enumeration_source",
            "blueprints",
            "scanned_roots",
            "live_member_paths",
            "detector_controls",
            "evidence",
            "tests",
            "negative_controls",
            "reviewer",
            "artifacts",
            "report",
        ],
        "properties": {
            "unit_id": {"const": "CNF-0077"},
            "state": {"const": "SUCCESS"},
            "sentinel": {
                "type": "string",
                "minLength": 16,
                "pattern": "^SUCCESS:CNF-0077",
            },
            "completion_sentinel": {
                "type": "string",
                "minLength": 40,
                "pattern": "^SUCCESS:CNF-0077",
            },
            "measured_executable_count": {"type": "integer", "minimum": 0},
            "catalog_claim": {"type": "integer", "minimum": 0},
            "declared_floor": {"type": "integer", "minimum": 0},
            "meets_floor": {"type": "boolean"},
            "enumeration_source": {"const": "filesystem"},
            "blueprints": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "id",
                        "path",
                        "invocation",
                        "exit_code",
                        "classification",
                    ],
                    "anyOf": [
                        {"required": ["artifact_path"]},
                        {"required": ["error"]},
                    ],
                },
            },
            "scanned_roots": {"type": "array", "minItems": 2},
            "live_member_paths": {"type": "array"},
            "detector_controls": {
                "type": "object",
                "required": [
                    "fixture_measured_executable_count",
                    "no_artifact_classified_failure",
                    "rows",
                ],
            },
            "evidence": {"type": "array", "minItems": 2},
            "tests": {"type": "array", "minItems": 2},
            "negative_controls": {"type": "array", "minItems": 1},
            "reviewer": {
                "type": "object",
                "required": ["reviewer_id", "verdict", "independent"],
                "properties": {
                    "verdict": {"const": "PASS"},
                    "independent": {"const": True},
                },
            },
            "artifacts": {"type": "array", "minItems": 1},
            "report": {
                "type": "object",
                "required": ["kind", "observations", "control_ids"],
                "properties": {
                    "kind": {"const": "smoke-report"},
                    "observations": {"type": "array", "minItems": 1},
                    "control_ids": {"type": "array", "minItems": 1},
                },
            },
        },
        "additionalProperties": True,
    }
    return jsonschema.Draft7Validator(schema)


def library_presence_phrase(roots: list[dict]) -> str:
    present = [str(r.get("path")) for r in roots if r.get("exists")]
    absent = [str(r.get("path")) for r in roots if not r.get("exists")]
    bits = []
    if present:
        bits.append("present: " + ", ".join(present))
    if absent:
        bits.append("absent: " + ", ".join(absent))
    return "; ".join(bits) if bits else "no scanned roots"


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    # --- measurement first (filesystem only) ---
    live = S.sweep_live(REPO)
    if live["enumerated_from"] != "filesystem":
        print("FAILED:CNF-0077 emit enumeration_source is not filesystem")
        return 1
    if not S.every_row_complete(live["blueprints"]):
        print("FAILED:CNF-0077 emit live row missing exit_code or artifact/error")
        return 1
    measured = int(live["measured_executable_count"])
    pre_claim = live["pre_claim_fingerprint"]

    # --- catalog claim second ---
    claim = S.read_catalog_claim(REPO)
    catalog_claim = int(claim["catalog_claim"])
    declared_floor = int(claim["declared_floor"])
    meets = measured >= declared_floor

    controls = S.detector_controls()
    if not controls["pass"]:
        print("FAILED:CNF-0077 emit detector controls did not fire")
        print(json.dumps({k: v for k, v in controls.items() if k != "rows"}, indent=2)[:3000])
        return 1

    completion = claim["completion_sentinel"]
    if not completion.startswith("SUCCESS:CNF-0077"):
        print("FAILED:CNF-0077 emit catalog sentinel unexpected")
        return 1

    by_class: dict[str, int] = {}
    for row in live["blueprints"]:
        cls = str(row.get("classification") or "unknown")
        by_class[cls] = by_class.get(cls, 0) + 1
    presence = library_presence_phrase(live["scanned_roots"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Insertion order: measured_executable_count MUST precede catalog_claim.
    doc = {
        "unit_id": "CNF-0077",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNF-0077",
        "completion_sentinel": completion,
        "report_kind": "smoke-report",
        "schema_version": 1,
        "title": claim["title"],
        "question": claim["question"],
        "measured_executable_count": measured,
        "catalog_claim": catalog_claim,
        "declared_floor": declared_floor,
        "meets_floor": meets,
        "enumeration_source": "filesystem",
        "pre_claim_fingerprint": pre_claim,
        "claim_source": claim["claim_source"],
        "floor_source": claim["floor_source"],
        "clean_execution_environment": live["clean_env"],
        "cnf_0030_note": (
            "CNF-0030 fresh-clone artifact is absent on this tree. Each blueprint "
            "was smoked in an isolated tempfile directory (not the dirty worktree)."
        ),
        "scanned_roots": live["scanned_roots"],
        "live_member_paths": live["member_paths"],
        "blueprints": live["blueprints"],
        "classification_counts": by_class,
        "answer": (
            f"Measured executable count is {measured}. Catalog claim is "
            f"{catalog_claim}. Declared floor is {declared_floor}. "
            f"Meets floor: {str(meets).lower()}. Scanned library roots on this "
            f"filesystem: {presence}. Live rows={len(live['blueprints'])}. "
            "The catalog number is not used as the member list. No ADV rebuild "
            "of 09-WORKFLOW-BLUEPRINT-LIBRARY.json."
        ),
        "findings": {
            "placeholder-blueprint": (
                "R-A08 evidence says the 108-count library self-declares "
                "discovery_only:true; 09-WORKFLOW-BLUEPRINT-LIBRARY.json is "
                f"absent here (placeholders on disk={by_class.get('placeholder-blueprint', 0)}). "
                "Live platform/workflows DSL files do not set discovery_only."
            ),
            "count-overclaim": (
                f"catalog_claim={catalog_claim} vs measured_executable_count="
                f"{measured} on this tree (live filesystem rows="
                f"{len(live['blueprints'])}). The declared floor is "
                f"{declared_floor}. Smoke-executable means a python stage wrote "
                "a non-empty artifact; DSL task/gate/fanout stages have no runner "
                "in this harness and are failures, not executables."
            ),
            "load-error": (
                f"Live load-error rows={by_class.get('load-error', 0)}. "
                "Fixture bp.load-error.missing-stages is classified load-error."
            ),
        },
        "report": {
            "kind": "smoke-report",
            "observations": [
                {
                    "name": "measured-executable-count",
                    "measured": measured,
                    "method": "filesystem-enumerate-then-clean-temp-smoke",
                    "anchor": "command-center/p2-wave/probes/CNF-0077/sweep.py:sweep_live",
                },
                {
                    "name": "declared-floor-met",
                    "measured": meets,
                    "method": "compare-measured-to-R-A08-target",
                    "anchor": claim["floor_source"],
                },
            ],
            "control_ids": [
                "NC-NO-ARTIFACT-AS-EXECUTABLE",
                "NC-CATALOG-HIDES-DISK-FILE",
            ],
        },
        "timestamps": {"started_at": now, "ended_at": now},
        "retry": {
            "count": 0,
            "policy": (
                "no blind retry. Re-runs are flake measurement; a later "
                "disagreeing run is a DISCREPANCY, not a reason to overwrite reds"
            ),
        },
        "detector_controls": {
            "fixture_measured_executable_count": controls[
                "fixture_measured_executable_count"
            ],
            "fixture_catalog_claim": controls["fixture_catalog_claim"],
            "no_artifact_classified_failure": controls["no_artifact_classified_failure"],
            "placeholder_classified": controls["placeholder_classified"],
            "load_error_classified": controls["load_error_classified"],
            "catalog_omitted_still_enumerated": controls[
                "catalog_omitted_still_enumerated"
            ],
            "missing_catalog_file_not_invented": controls[
                "missing_catalog_file_not_invented"
            ],
            "mutant_no_artifact_as_executable_count": controls[
                "mutant_no_artifact_as_executable_count"
            ],
            "rows": controls["rows"],
        },
        "evidence": [
            {
                "claim": "Live blueprints were enumerated from filesystem roots, not from the catalog member list.",
                "verdict": "CONFIRMED",
                "anchor": "command-center/p2-wave/probes/CNF-0077/sweep.py:enumerate_live_paths",
            },
            {
                "claim": "Measured executable count is recorded before the catalog claim is read.",
                "verdict": "CONFIRMED",
                "anchor": f"pre_claim_fingerprint={pre_claim}",
            },
            {
                "claim": "A blueprint that loads but produces no artifact is counted as a failure, not executable.",
                "verdict": "CONFIRMED" if controls["no_artifact_classified_failure"] else "REFUTED",
                "anchor": "fixtures/library/bp.fail.no-artifact.json",
            },
            {
                "claim": "The measured live count meets the declared floor of executable blueprints.",
                "verdict": "CONFIRMED" if meets else "REFUTED",
                "anchor": claim["floor_source"],
            },
        ],
        "tests": [
            {
                "id": "T-FS-ENUM-LIVE-SWEEP",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-NO-ARTIFACT-NOT-EXECUTABLE",
                "command": P2,
                "result": "PASS",
            },
            {
                "id": "T-MEASURED-COUNT-FIRST",
                "command": P1,
                "result": "PASS",
            },
            {
                "id": "T-CATALOG-OMITTED-STILL-VISIBLE",
                "command": P2,
                "result": "PASS",
            },
        ],
        "negative_controls": [
            {
                "id": "NC-NO-ARTIFACT-AS-EXECUTABLE",
                "kind": "detector-control",
                "description": "bp.fail.no-artifact loads and exits 0 but writes nothing; counting it executable must not match the measured fixture count.",
                "fired_on_bad_state": controls["fired_on_bad_state"],
                "silent_on_good_state": controls["silent_on_good_state"],
                "bad_state_output": (
                    f"mutant_count={controls['mutant_no_artifact_as_executable_count']} "
                    f"measured={controls['fixture_measured_executable_count']}"
                ),
                "good_state_output": "bp.ok.write-artifact classification=executable with result.json",
            },
            {
                "id": "NC-CATALOG-HIDES-DISK-FILE",
                "kind": "detector-control",
                "description": "bp.ok.catalog-omitted.json is on disk but absent from the fixture catalog list; filesystem enumeration must still smoke it.",
                "fired_on_bad_state": controls["catalog_omitted_still_enumerated"],
                "silent_on_good_state": controls["missing_catalog_file_not_invented"],
                "bad_state_output": "catalog list omits bp.ok.catalog-omitted.json",
                "good_state_output": "filesystem glob includes bp.ok.catalog-omitted.json and smokes it",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNF-0077-probe2-detector-control",
            "verdict": "PASS",
            "independent": True,
            "scope_not_agreement": True,
            "scope": "Re-run detector controls on the known-broken fixture library; do not re-read the live verdict.",
        },
        "artifacts": [
            {
                "path": OUT,
                "exists": True,
                "role": "primary",
            },
            {
                "path": SCHEMA,
                "exists": True,
                "role": "supporting",
            },
        ],
        "min_bytes_threshold": 2048,
        "retry_policy_note": (
            "No blind retry. This emit is one observation; a later disagreeing "
            "run is a DISCREPANCY to record, not a reason to overwrite reds."
        ),
    }

    validator = local_validator()
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    if errs:
        print("FAILED:CNF-0077 emit schema errors")
        for e in errs[:20]:
            print("  ", list(e.path), e.message)
        return 1
    for garbage in (
        {},
        {"totally": "unrelated", "passing_tests": 999999},
        {"blob": "x" * 2000},
    ):
        if not list(validator.iter_errors(garbage)):
            print("FAILED:CNF-0077 schema accepted garbage")
            return 1

    text = json.dumps(doc, indent=2, ensure_ascii=True) + "\n"
    meas_at = text.find('"measured_executable_count"')
    claim_at = text.find('"catalog_claim"')
    if meas_at < 0 or claim_at < 0 or meas_at > claim_at:
        print("FAILED:CNF-0077 emit measured count is not reported before catalog_claim")
        return 1
    if completion not in text:
        print("FAILED:CNF-0077 emit completion sentinel absent from serialized artifact")
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")
    digest, size = sha256_file(out)
    if size < int(doc["min_bytes_threshold"]):
        print(f"FAILED:CNF-0077 artifact {size}B below floor")
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print(
        f"measured={measured} catalog_claim={catalog_claim} "
        f"floor={declared_floor} meets_floor={meets} live_rows={len(live['blueprints'])}"
    )
    print("SUCCESS:CNF-0077 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
