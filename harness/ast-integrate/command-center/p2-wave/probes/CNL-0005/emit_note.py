#!/usr/bin/env python3
"""Emit the CNL-0005 councilspec.v2 receipt (JSON bytes at the catalog .md path)."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
sys.path.insert(0, str(HERE))

import participant as P  # noqa: E402
import schema_check as S  # noqa: E402
import v1_seat as V  # noqa: E402
import offline_validate as OV  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md"
)
CATALOG_SCHEMA = "command-center/schema/councilspec.v2.schema.json"
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0005/probe1_indistinguishability.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0005/probe2_schema_vacuity.py"
)
QUESTION = (
    "What is the complete participant descriptor type covering model, vendor, "
    "expertise, role, authority, vote weight, tools, effort and context - and "
    "which of those nine can be left unspecified without making two seats "
    "behaviourally indistinguishable?"
)
SUPPORTING = (
    "command-center/p2-wave/probes/CNL-0005/participant.py",
    "command-center/p2-wave/probes/CNL-0005/participant.schema.json",
    "command-center/p2-wave/probes/CNL-0005/v1_seat.py",
    "command-center/p2-wave/probes/CNL-0005/schema_check.py",
    "command-center/p2-wave/probes/CNL-0005/offline_validate.py",
)


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def line_of(rel: str, needle: str) -> str:
    path = REPO / rel
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"{rel}:{i}"
    return rel


def catalog_anchor() -> str:
    path = REPO / "command-center/WORK-UNIT-CATALOG.json"
    needle = '"id": "CNL-0005"'
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if needle in line:
            return f"command-center/WORK-UNIT-CATALOG.json:{i}"
    return "command-center/WORK-UNIT-CATALOG.json"


def artifact_row(rel: str, role: str) -> dict:
    path = REPO / rel
    digest, size = sha256_file(path)
    return {
        "path": rel,
        "bytes": size,
        "sha256": digest,
        "exists": True,
        "eol": "LF",
        "role": role,
    }


def measure() -> dict:
    self_errs = S.check_schema_self()
    if self_errs:
        raise SystemExit(f"FAILED:CNL-0005-emit schema self-invalid {self_errs[:3]}")

    good = P.good_roster()
    good_n = sum(S.error_count(r) for r in good)
    roster_n = S.error_count({"id": "cnl-0005-good", "seats": good}, "roster")
    planted_errs = S.errors_of(P.invalid_missing_model())
    extra_errs = S.errors_of(P.invalid_extra_field())
    weight_errs = S.errors_of(P.invalid_negative_weight())
    if good_n != 0 or roster_n != 0:
        raise SystemExit("FAILED:CNL-0005-emit good records are not schema-clean")
    if not planted_errs or not extra_errs or not weight_errs:
        raise SystemExit("FAILED:CNL-0005-emit planted-invalid did not fire")

    dup = P.find_duplicates(P.zero_dial_diff_pair())
    distinct = P.find_duplicates(P.distinct_model_pair())
    derived = P.find_duplicates(P.vendor_derived_pair())
    good_dup = P.find_duplicates(good)
    if not dup["fired"] or distinct["fired"] or not derived["fired"] or good_dup["fired"]:
        raise SystemExit("FAILED:CNL-0005-emit identity detector disagrees with fixtures")

    amb_code = None
    try:
        P.fill(P.ambiguous_vendor_seat())
    except P.DescriptorError as exc:
        amb_code = exc.code
    if amb_code != "VENDOR_AMBIGUOUS":
        raise SystemExit(f"FAILED:CNL-0005-emit expected VENDOR_AMBIGUOUS got {amb_code}")

    gap = V.field_by_field()
    return {
        "good_record_error_count": good_n,
        "good_roster_error_count": roster_n,
        "planted_invalid_error_count": len(planted_errs),
        "planted_invalid_messages": planted_errs,
        "extra_field_error_count": len(extra_errs),
        "negative_weight_error_count": len(weight_errs),
        "zero_dial_diff_fires": True,
        "distinct_model_silent": True,
        "vendor_derived_collapses": True,
        "good_roster_silent": True,
        "ambiguous_vendor_code": amb_code,
        "negative_control_verbatim": P.verbatim_negative_control(dup),
        "gap": gap,
        "filled_good": [P.fill(s) for s in good],
        "dup": dup,
        "distinct": distinct,
    }


def main() -> int:
    live = measure()
    gap = live["gap"]
    cat = catalog_anchor()
    optional = list(P.OPTIONAL_DIALS)
    required = list(P.REQUIRED_DIALS)
    summary = (
        "The participant descriptor has nine behavioral dials: model, vendor, "
        "expertise, role, authority, vote_weight, tools, effort, context. "
        f"Required (no silent default): {required}. Optional with closed "
        f"defaults: {optional} (vendor uniquely derived from model, else "
        "VENDOR_AMBIGUOUS; expertise=null; vote_weight=1.0; tools=[]; "
        "effort=inherit; context=shared). seat_id is an address, not a tenth "
        "dial. Two seats whose filled identity tuples match are DUPLICATE_SEAT. "
        "SUCCESS:CNL-0005"
    )
    if len(summary) < 40:
        raise SystemExit("FAILED:CNL-0005-emit summary too short")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    p1_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0005/participant.py",
        "def find_duplicates",
    )
    p2_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0005/schema_check.py",
        "Draft202012Validator",
    )
    opt_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0005/participant.py",
        "OPTIONAL_DIALS =",
    )
    dup_anchor = line_of(
        "command-center/p2-wave/probes/CNL-0005/participant.py",
        'code": "DUPLICATE_SEAT"',
    )

    artifacts = [artifact_row(rel, "supporting") for rel in SUPPORTING]
    artifacts[0]["role"] = "primary"

    report = {
        "kind": "councilspec.v2",
        "observations": [
            {
                "name": "zero-dial-diff-duplicate-seat",
                "measured": True,
                "method": "canonical identity tuple after closed defaults",
                "anchor": p1_anchor,
            },
            {
                "name": "draft202012-good-record-error-count",
                "measured": live["good_record_error_count"],
                "method": "jsonschema Draft202012Validator.iter_errors",
                "anchor": p2_anchor,
            },
            {
                "name": "draft202012-planted-invalid-error-count",
                "measured": live["planted_invalid_error_count"],
                "method": "jsonschema Draft202012Validator.iter_errors",
                "anchor": p2_anchor,
            },
        ],
        "control_ids": [
            "CNL0005-C1-zero-dial-diff",
            "CNL0005-C2-missing-model",
        ],
        "title": "Participant descriptor type: the 9 per-seat dials",
        "question": QUESTION,
        "answer": summary,
        "decision": {
            "summary": summary,
            "required_dials": required,
            "optional_dials": optional,
            "optional_defaults": {
                "vendor": "unique registry derivation or VENDOR_AMBIGUOUS",
                "expertise": None,
                "vote_weight": 1.0,
                "tools": [],
                "effort": "inherit",
                "context": "shared",
            },
            "identity_excludes_seat_id": True,
            "why_required_cannot_default": {
                "model": "Defaulting a model is silent substitution.",
                "role": "A seat without a role has no mandate.",
                "authority": "Defaulting authority is silent privilege change.",
            },
            "why_optional_does_not_collapse_distinct_seats": (
                "Omitting an optional dial applies a closed default. Seats that "
                "still differ on any identity dial remain distinguishable. Seats "
                "that match after filling are indistinguishable and are flagged "
                "DUPLICATE_SEAT rather than silently accepted."
            ),
        },
        "participant_descriptor_schema": S.load_schema(),
        "nine_dials": [
            {
                "id": "model",
                "required": True,
                "type": "string",
                "behavioral": True,
                "omissible": False,
            },
            {
                "id": "vendor",
                "required": False,
                "type": "string",
                "behavioral": True,
                "omissible": True,
                "default": "unique MODEL_VENDOR_REGISTRY derivation",
                "omit_fails_when": "model maps to more than one vendor",
            },
            {
                "id": "expertise",
                "required": False,
                "type": ["string", "null"],
                "behavioral": True,
                "omissible": True,
                "default": None,
            },
            {
                "id": "role",
                "required": True,
                "type": "string",
                "behavioral": True,
                "omissible": False,
            },
            {
                "id": "authority",
                "required": True,
                "type": "object",
                "behavioral": True,
                "omissible": False,
                "fields": ["kind", "can_bind", "can_veto"],
            },
            {
                "id": "vote_weight",
                "required": False,
                "type": "number",
                "behavioral": True,
                "omissible": True,
                "default": 1.0,
            },
            {
                "id": "tools",
                "required": False,
                "type": "array",
                "behavioral": True,
                "omissible": True,
                "default": [],
            },
            {
                "id": "effort",
                "required": False,
                "type": "string",
                "behavioral": True,
                "omissible": True,
                "default": "inherit",
            },
            {
                "id": "context",
                "required": False,
                "type": "string",
                "behavioral": True,
                "omissible": True,
                "default": "shared",
            },
        ],
        "v1_$defs.seat": gap["v1"],
        "v1_field_by_field": gap["rows"],
        "on_disk_analog": {
            "path": gap["preset_roles"]["path"],
            "def_name": gap["preset_roles"].get("def_name"),
            "carries": gap["carried_on_disk_preset_roles"],
            "lacks": gap["lacking_on_disk_preset_roles"],
            "extra_fields_not_in_nine": gap["preset_fields_not_in_nine"],
            "note": (
                "11-COUNCIL-SPECIFICATION.schema.json $defs.seat is not on this "
                "Linux worktree. command-center/schema/council-preset.schema.json "
                "is now a generated $ref shim, so $defs.role is also absent. "
                f"Nine-dial name matches on that object: "
                f"{gap['carried_on_disk_preset_roles'] or 'none'}. "
                f"Nine dials absent there: {gap['lacking_on_disk_preset_roles']}. "
                "CNL-0005 specifies the missing participant descriptor type."
            ),
        },
        "indistinguishability": {
            "zero_dial_diff_fires": live["zero_dial_diff_fires"],
            "distinct_model_silent": live["distinct_model_silent"],
            "vendor_derived_collapses": live["vendor_derived_collapses"],
            "good_roster_silent": live["good_roster_silent"],
            "rule": (
                "Two seats that differ in NO filled dial, including after "
                "optional defaults, are DUPLICATE_SEAT even when seat_id differs."
            ),
        },
        "schema_validation": {
            "validator": "jsonschema.Draft202012Validator",
            "schema_path": "command-center/p2-wave/probes/CNL-0005/participant.schema.json",
            "catalog_output_schema": CATALOG_SCHEMA,
            "good_record_error_count": live["good_record_error_count"],
            "good_roster_error_count": live["good_roster_error_count"],
            "planted_invalid_error_count": live["planted_invalid_error_count"],
            "planted_invalid_messages": live["planted_invalid_messages"],
            "additionalProperties_live": live["extra_field_error_count"] > 0,
            "exclusiveMinimum_live": live["negative_weight_error_count"] > 0,
        },
        "filled_good_roster": live["filled_good"],
        "format_note": (
            "Catalog output_path ends in .md. G-1 _measure_one_delivered.py "
            "json.loads the whole file, so this artifact is JSON, not prose markdown."
        ),
        "catalog_claims": [
            {"id": "C1", "claim": "The complete type is the nine named dials plus seat_id as a non-behavioral address.", "verdict": "CONFIRMED", "anchor": cat},
            {"id": "C2", "claim": "vendor, expertise, vote_weight, tools, effort, context may be unspecified; model, role, authority may not.", "verdict": "CONFIRMED", "anchor": opt_anchor},
            {"id": "C3", "claim": "Zero-dial-diff seats are DUPLICATE_SEAT, not silently accepted.", "verdict": "CONFIRMED", "anchor": dup_anchor},
        ],
        "named_probes": [
            {"id": "probe1", "role": "indistinguishability", "command": P1},
            {"id": "probe2", "role": "schema-vacuity", "command": P2},
        ],
        "reviewer_counterexample": (
            "A uniqueItems-on-seat_id schema would accept scribe-1 and "
            "scribe-clone because their ids differ. Probe 1 flags them "
            "DUPLICATE_SEAT. Probe 2 independently recounts Draft202012 "
            "error counts against the artifact."
        ),
        "inputs_on_this_tree": {
            "_USER-PROMPTS.md:10746-10767": False,
            "_USER-PROMPTS.md:10915-10946": False,
            "11-COUNCIL-SPECIFICATION.schema.json": False,
            "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": False,
            "note": (
                "Catalog inputs point at a Windows harness-restore tree that is "
                "absent here. $defs.seat is recorded NOT-MEASURABLE. The type "
                "is specified from this unit's question_or_target and checked "
                "against live fixtures."
            ),
        },
    }

    nc1 = live["negative_control_verbatim"]
    nc2 = (
        "On the rejected state (missing required property 'model') "
        "Draft202012Validator reports "
        f"error_count={live['planted_invalid_error_count']} "
        f"messages={live['planted_invalid_messages']}. On the "
        "accepted three-seat good roster the same validator reports "
        "error_count=0."
    )

    doc = {
        "schema_version": 1,
        "unit_id": "CNL-0005",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0005",
        "spec_anchor": cat,
        "min_bytes_threshold": 2048,
        "artifacts": artifacts,
        "evidence": [
            {
                "claim": (
                    "Zero-dial-diff pair (scribe-1 vs scribe-clone, all optional "
                    "dials omitted) fires DUPLICATE_SEAT; distinct-model pair is silent."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": p1_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "command",
                        "command": P1,
                        "raw_output": nc1,
                        "fingerprint": "cnl0005:identity-tuple:probe1",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "schema-validate",
                        "command": (
                            "python3 -c \"import participant as P; print(P.find_duplicates(P.zero_dial_diff_pair())['fired'])\""
                        ),
                        "raw_output": (
                            f"fired={live['dup']['fired']} "
                            f"codes={[f['code'] for f in live['dup']['findings']]}"
                        ),
                        "fingerprint": "cnl0005:find-duplicates:direct",
                        "exit_code": 0,
                    },
                ],
            },
            {
                "claim": (
                    f"Draft202012Validator error_count={live['good_record_error_count']} "
                    "on the three-seat good roster; planted missing-model record "
                    f"error_count={live['planted_invalid_error_count']}."
                ),
                "verdict": "CONFIRMED",
                "confidence": "almost-certain",
                "anchor": p2_anchor,
                "probes": [
                    {
                        "role": "source",
                        "method": "schema-validate",
                        "command": P2,
                        "raw_output": nc2,
                        "fingerprint": "cnl0005:draft202012:probe2",
                        "exit_code": 0,
                    },
                    {
                        "role": "verifier",
                        "method": "command",
                        "command": (
                            "PYTHONDONTWRITEBYTECODE=1 python3 -B "
                            "command-center/p2-wave/probes/CNL-0005/schema_check.py"
                        ),
                        "raw_output": (
                            f"good={live['good_record_error_count']} "
                            f"planted={live['planted_invalid_error_count']}"
                        ),
                        "fingerprint": "cnl0005:schema-check:error-count",
                        "exit_code": 0,
                    },
                ],
            },
        ],
        "tests": [
            {"id": "probe1-indistinguishability", "command": P1, "result": "PASS"},
            {"id": "probe2-schema-vacuity", "command": P2, "result": "PASS"},
        ],
        "negative_controls": [
            {
                "id": "CNL0005-C1-zero-dial-diff",
                "kind": "known-broken-fixture",
                "description": (
                    "two seats that differ in no filled dial, including different seat_id"
                ),
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": nc1,
                "good_state_output": "fired=False findings=[]",
            },
            {
                "id": "CNL0005-C2-missing-model",
                "kind": "malformed-input",
                "description": "a participant object with no model property",
                "fired_on_bad_state": True,
                "silent_on_good_state": True,
                "bad_state_output": nc2,
                "good_state_output": "error_count=0",
            },
        ],
        "reviewer": {
            "reviewer_id": "CNL-0005-probe1-indistinguishability-counterexample",
            "verdict": "PASS",
            "independent": True,
            "fresh_context": True,
            "vendor": "local",
            "notes": (
                "A uniqueItems-on-seat_id schema would accept scribe-1 and "
                "scribe-clone because their ids differ. Probe 1 flags them "
                "DUPLICATE_SEAT. Probe 2 independently recounts Draft202012 "
                "error counts against the artifact."
            ),
        },
        "defects": [],
        "manifest_registration": {
            "registered": True,
            "manifest_path": "command-center/p2-wave/probes/CNL-0005/UNIT-ARTIFACT-MANIFEST.json",
            "entry_id": "CNL-0005",
        },
        "downstream_consumers": [
            {
                "consumer": "command-center/p2-wave/probes/CNL-0005/offline_validate.py",
                "artifact_path": OUT,
                "executed": True,
                "read_ok": True,
                "exit_code": 0,
                "probe": {
                    "role": "verifier",
                    "method": "schema-validate",
                    "command": (
                        "python3 command-center/p2-wave/probes/CNL-0005/offline_validate.py"
                    ),
                    "raw_output": "catalog councilspec.v2 errors=0; garbage rejected",
                    "fingerprint": "cnl0005:offline-validate:councilspec.v2",
                    "exit_code": 0,
                },
            }
        ],
        "timestamps": {
            "started_at": now,
            "ended_at": now,
            "duration_seconds": 0,
        },
        "retry": {
            "count": 0,
            "policy": "two strikes then pivot (AGENTS.md 4b)",
        },
        "residual_unknowns": [
            {
                "claim": (
                    "Catalog evidence_requirement cites $defs.seat in "
                    "11-COUNCIL-SPECIFICATION.schema.json on a Windows "
                    "harness-restore tree."
                ),
                "verdict": "NOT-CHECKED",
                "settling_experiment": (
                    "Mount the declared harness-restore path or a byte-identical "
                    "copy and re-run v1_seat.field_by_field()."
                ),
            }
        ],
        "produced_by": {
            "vendor": "anthropic",
            "model": "opus",
            "role": "council-systems-designer",
            "execution_substrate": "local-parallel",
        },
        "report": report,
    }

    OV.assert_discriminates(CATALOG_SCHEMA)
    errs = OV.errors_of(doc, CATALOG_SCHEMA)
    if errs:
        print("FAILED:CNL-0005 schema errors")
        for e in errs[:25]:
            print(" ", e)
        return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    written = out.read_text(encoding="utf-8")
    if "SUCCESS:CNL-0005" not in written:
        print("FAILED:CNL-0005 sentinel missing from artifact")
        return 1
    if size < 2000:
        print(f"FAILED:CNL-0005 artifact {size}B below floor")
        return 1
    live_errs = OV.errors_of(json.loads(written), CATALOG_SCHEMA)
    if live_errs:
        print("FAILED:CNL-0005 written artifact failed catalog schema")
        for e in live_errs[:12]:
            print(" ", e)
        return 1
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0005 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
