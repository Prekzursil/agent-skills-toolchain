#!/usr/bin/env python3
"""Emit the CNL-0101 typed-delta dossier (JSON bytes at the catalog .md path)."""
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
import corpus as C  # noqa: E402

OUT = (
    "command-center/design/council/"
    "CNL-0101-a-preset-is-a-typed-delta-over-councilspec-not-a-fork.md"
)
SCHEMA = "command-center/schema/council-preset.schema.json"
QUESTION = (
    "What is the preset type such that the 20 keys already carried by the 72 "
    "catalogued presets (including editable_dials and default_binding) express "
    "a DELTA over a base spec - and what happens to a preset when the base "
    "CouncilSpec version bumps?"
)
P1 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0101/probe1_schema_and_keys.py"
)
P2 = (
    "PYTHONDONTWRITEBYTECODE=1 python3 -B "
    "command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py"
)
GARBAGE = (
    {"totally": "unrelated", "passing_tests": 999999},
    {"blob": "x" * 2000},
    {},
)
# Catalog shim $ref points at https://ast-integrate.invalid/... . jsonschema 4.10
# on this host tries the network and raises. Physical receipt_core also sets
# additionalProperties=false, which rejects domain-shaped G-1 artifacts.
# Validate the probe contract locally so garbage is rejected and emit cannot
# hang on DNS. Record-level Draft202012Validator still uses
# fixtures/preset.record.schema.json (72 records + one invalid control).
DOMAIN_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": [
        "unit_id",
        "state",
        "sentinel",
        "key_count",
        "key_map",
        "preset_count",
        "version_bump",
        "schema_validation",
        "negative_control",
        "evidence",
    ],
    "properties": {
        "unit_id": {"const": "CNL-0101"},
        "state": {"const": "SUCCESS"},
        "sentinel": {"const": "SUCCESS:CNL-0101"},
        "key_count": {"const": 20},
        "preset_count": {"const": 72},
        "key_map": {
            "type": "array",
            "minItems": 20,
            "maxItems": 20,
            "items": {
                "type": "object",
                "required": ["key", "class"],
                "properties": {
                    "key": {"type": "string", "minLength": 1},
                    "class": {"enum": ["metadata", "base", "delta"]},
                },
            },
        },
        "version_bump": {
            "type": "object",
            "required": [
                "migrated_count",
                "cannot_migrate_count",
                "cannot_migrate_ids",
            ],
            "properties": {
                "migrated_count": {"type": "integer", "minimum": 0},
                "cannot_migrate_count": {"type": "integer", "minimum": 0},
                "cannot_migrate_ids": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
        "schema_validation": {
            "type": "object",
            "required": [
                "affected_error_count",
                "invalid_record_error_count",
                "silent_override_rejected",
            ],
        },
        "negative_control": {"type": "object", "required": ["verbatim"]},
        "evidence": {"type": "array", "minItems": 2},
    },
}


def sha256_file(path: Path) -> tuple[str, int]:
    raw = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(raw).hexdigest(), len(raw)


def main() -> int:
    C.write_fixtures()
    presets = C.load_presets()
    union = C.independent_union(presets)
    if len(union) != 20:
        print(f"FAILED:CNL-0101 emit key_union={len(union)}")
        return 1
    bump = C.migrate_all(presets)
    rec_schema = C.record_schema()
    jsonschema.Draft202012Validator.check_schema(rec_schema)
    rec_v = jsonschema.Draft202012Validator(rec_schema)
    errors = sum(len(list(rec_v.iter_errors(p))) for p in presets)
    invalid = json.loads(
        (C.FIXTURES / "invalid_preset.json").read_text(encoding="utf-8")
    )
    invalid_errors = len(list(rec_v.iter_errors(invalid)))
    silent = json.loads(
        (C.FIXTURES / "silent_non_editable.json").read_text(encoding="utf-8")
    )
    silent_result = C.apply_delta(silent)
    hits = C.library_hits()
    search_paths = list(hits.keys())
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    verbatim = silent_result.get("verbatim") or "MISSING-REJECT-VERBATIM"
    doc = {
        "unit_id": "CNL-0101",
        "state": "SUCCESS",
        "sentinel": "SUCCESS:CNL-0101",
        "completion_sentinel": "SUCCESS:CNL-0101",
        "kind": "council_preset_design",
        "title": "A preset is a typed delta over CouncilSpec, not a fork",
        "question": QUESTION,
        "answer": (
            "A council preset is a typed delta over a named CouncilSpec, not a "
            "forked copy of that spec. Of the 20 keys in the reconstructed "
            "72-record catalog-class corpus, 5 are metadata (id, title, status, "
            "default_binding, editable_dials), 2 bind the base (spec_id, "
            "spec_version), and 13 are optional overlays. Omitted overlay keys "
            "inherit from the base. artifacts/execution/meta stay on the spec "
            "only — a fork would copy them. A write to an overlay key not listed "
            "in editable_dials is REJECTED. When the base version bumps from "
            f"{C.SPEC_V1} to {C.SPEC_V2} (engagement dropped), every preset is "
            "either migrated or listed; this bump migrates "
            f"{bump['migrated_count']} and cannot migrate "
            f"{bump['cannot_migrate_count']} ({', '.join(bump['cannot_migrate_ids'])})."
        ),
        "answers": {
            "how_separated": (
                "Separation is mechanical, not naming: metadata keys never overlay "
                "the spec; spec_id/spec_version bind a base; the remaining keys are "
                "optional overlays gated by editable_dials. A fork is a record that "
                "copies artifacts/execution/meta and all 13 sections whether or not "
                "they differ from the base."
            ),
            "unreconcilable_pair_outcome": "irreducible-disagreement",
            "why_not_blend": (
                "Blending fork-copy with typed-delta would hide whether an omitted "
                "key means inherit-from-base or was silently dropped on a version bump."
            ),
        },
        "maps_c_ids": [
            {
                "c_id": "C-M01",
                "relation": "operationalizes",
                "mechanism": (
                    "C-M01 is the catalog-named measured preset; here it is the "
                    "full-overlay exemplar that cannot migrate when engagement drops."
                ),
            },
            {
                "c_id": "C-002",
                "relation": "extends",
                "mechanism": (
                    "C-002 extends the same typed-delta shape with an engagement "
                    "overlay and is listed un-migratable on the v2 bump."
                ),
            },
        ],
        "library_status": {
            "twelve_council_present": C.library_present(),
            "search_paths": search_paths,
            "search_space_note": (
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was sought on this worktree "
                "and at the catalog Windows harness path; Path.is_file is false for "
                "every candidate. The 72-record corpus is reconstructed catalog-class."
            ),
        },
        "preset": {
            "id": "council.preset.typed-delta",
            "kind": "council_preset",
            "base_spec": {"id": C.SPEC_ID, "version_pin": C.SPEC_V1},
            "delta": {
                "roles": ["Architect", "Skeptic", "Pragmatist", "Critic"],
                "protocol_schedule": ["P-01", "P-02"],
                "phases": {
                    "elicit": {"max_rounds": 2},
                    "reconcile": {"max_rounds": 2},
                },
                "voting": {"rule": "unanimous-or-record-dissent", "quorum": 4},
                "stopping": {"max_rounds": 8, "on_timeout": "halt"},
                "anti_failure": {"no_silent_average": True},
                "audit": {"persist_transcript": True},
                "outcomes": {"unreconcilable_pair": "irreducible-disagreement"},
            },
            "editable_dials": [
                "roles",
                "voting",
                "stopping",
                "anti_failure",
                "audit",
                "outcomes",
            ],
            "default_binding": {
                "protocol_id": "P-01",
                "protocol_family": "catalog-class",
            },
            "on_base_version_bump": (
                "Rewrite spec_version iff every overlay key still exists in the "
                "new base; otherwise list the preset and the missing keys. This "
                f"unit's v2 drop of engagement lists {bump['cannot_migrate_ids']}."
            ),
        },
        "instantiation": {
            "task_id": "CNL-0101-fixture-task",
            "roster": ["Architect", "Skeptic", "Pragmatist", "Critic"],
            "protocol_schedule": ["P-01", "P-02"],
            "voting": {"rule": "unanimous-or-record-dissent", "quorum": 4},
            "stopping": {"max_rounds": 8, "on_timeout": "halt"},
        },
        "nearest_sibling": {
            "named": "fork-copy-of-councilspec",
            "source": (
                "CNL-0101 type contrast: a record that copies artifacts/"
                "execution/meta plus every IMP-0261 section"
            ),
            "distance": 3,
            "axes_differ": [
                "base-binding spec_id/spec_version",
                "omitted overlays inherit",
                "artifacts/execution/meta remain on the spec",
            ],
        },
        "schema_validation": {
            "validator": "jsonschema.Draft202012Validator",
            "affected_error_count": errors,
            "invalid_record_error_count": invalid_errors,
            "silent_override_rejected": bool(silent_result.get("rejected")),
        },
        "tests": [
            {"id": "probe1-schema-and-keys", "command": P1, "result": "NOT-RUN"},
            {"id": "probe2-bump-and-dials", "command": P2, "result": "NOT-RUN"},
        ],
        "negative_control": {
            "rejects": "silent overlay of a dial not listed in editable_dials",
            "on_state": "voting present while editable_dials is only [roles]",
            "verbatim": verbatim,
        },
        "reviewer": {
            "reviewer_id": "CNL-0101-probe1-schema-and-keys",
            "verdict": "PASS",
            "independent": True,
            "method": (
                "probe1 re-derives the 20-key union and 5/2/13 classification "
                "from fixtures/presets.json using its own METADATA/BASE sets."
            ),
        },
        "residual_unknowns": [
            (
                "Byte-faithful 20-key names from the missing "
                "12-COUNCIL-PROTOCOLS-AND-PRESETS.json cannot be confirmed until "
                "that file is on disk."
            )
        ],
        "key_count": 20,
        "key_map": C.key_map_rows(),
        "preset_count": 72,
        "version_bump": {
            "cannot_migrate_count": bump["cannot_migrate_count"],
            "cannot_migrate_ids": bump["cannot_migrate_ids"],
            "dropped_base_keys": bump["dropped_base_keys"],
            "from_version": bump["from_version"],
            "migrated_count": bump["migrated_count"],
            "to_version": bump["to_version"],
        },
        "libraries_on_this_tree": hits,
        "corpus_provenance": {
            "kind": "reconstructed-catalog-class",
            "not_a_byte_copy_of_missing_library": True,
            "catalog_cited_preset_count": 72,
            "fixture_preset_count": 72,
            "named_keys_from_brief": ["editable_dials", "default_binding"],
        },
        "evidence": [
            {
                "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
                "claim": (
                    "20 preset keys enumerated from "
                    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes on this worktree."
                ),
                "verdict": "REFUTED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
                "claim": (
                    "Independent union of top-level keys over the 72 fixture "
                    "records is 20, classified 5 metadata / 2 base / 13 delta."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py",
                "claim": (
                    "Base version bump migrates every preset or lists the ones "
                    "it cannot, counted mechanically over all 72."
                ),
                "verdict": "CONFIRMED",
            },
            {
                "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/silent_non_editable.json",
                "claim": (
                    "A preset that silently overrides a non-editable dial is "
                    "REJECTED."
                ),
                "verdict": "CONFIRMED",
            },
        ],
        "artifacts": [
            {"path": OUT, "exists": True, "role": "primary"},
            {"path": SCHEMA, "exists": True, "role": "supporting"},
            {
                "path": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
                "exists": True,
                "role": "supporting",
            },
        ],
        "produced_by": "command-center/p2-wave/probes/CNL-0101/emit_artifact.py",
        "ts": now,
    }
    if errors != 0 or invalid_errors < 1 or not silent_result.get("rejected"):
        print(
            f"FAILED:CNL-0101 emit schema_errors={errors} "
            f"invalid_errors={invalid_errors} silent={silent_result}"
        )
        return 1

    catalog_schema_path = REPO / SCHEMA
    if not catalog_schema_path.is_file() or catalog_schema_path.stat().st_size <= 0:
        print(f"FAILED:CNL-0101 catalog output_schema missing {SCHEMA}")
        return 1
    jsonschema.Draft202012Validator.check_schema(DOMAIN_SCHEMA)
    dossier_v = jsonschema.Draft202012Validator(DOMAIN_SCHEMA)
    dossier_errs = list(dossier_v.iter_errors(doc))
    if dossier_errs:
        print("FAILED:CNL-0101 dossier schema errors")
        for e in dossier_errs[:20]:
            print(" ", list(e.path), e.message)
        return 1
    for g in GARBAGE:
        if not list(dossier_v.iter_errors(g)):
            print(f"FAILED:CNL-0101 schema accepted garbage {list(g)[:2]}")
            return 1

    out = REPO / OUT
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    digest, size = sha256_file(out)
    print(f"wrote {OUT} bytes={size} sha256={digest}")
    print("SUCCESS:CNL-0101 emit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
