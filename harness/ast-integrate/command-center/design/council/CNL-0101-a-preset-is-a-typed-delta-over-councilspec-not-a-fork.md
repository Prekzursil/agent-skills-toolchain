{
 "answer": "A council preset is a typed delta over a named CouncilSpec, not a forked copy of that spec. Of the 20 keys in the reconstructed 72-record catalog-class corpus, 5 are metadata (id, title, status, default_binding, editable_dials), 2 bind the base (spec_id, spec_version), and 13 are optional overlays. Omitted overlay keys inherit from the base. artifacts/execution/meta stay on the spec only \u2014 a fork would copy them. A write to an overlay key not listed in editable_dials is REJECTED. When the base version bumps from 1.0.0 to 2.0.0 (engagement dropped), every preset is either migrated or listed; this bump migrates 69 and cannot migrate 3 (C-M01, C-002, C-003).",
 "answers": {
  "how_separated": "Separation is mechanical, not naming: metadata keys never overlay the spec; spec_id/spec_version bind a base; the remaining keys are optional overlays gated by editable_dials. A fork is a record that copies artifacts/execution/meta and all 13 sections whether or not they differ from the base.",
  "unreconcilable_pair_outcome": "irreducible-disagreement",
  "why_not_blend": "Blending fork-copy with typed-delta would hide whether an omitted key means inherit-from-base or was silently dropped on a version bump."
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0101-a-preset-is-a-typed-delta-over-councilspec-not-a-fork.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-preset.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
   "role": "supporting"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0101",
 "corpus_provenance": {
  "catalog_cited_preset_count": 72,
  "fixture_preset_count": 72,
  "kind": "reconstructed-catalog-class",
  "named_keys_from_brief": [
   "editable_dials",
   "default_binding"
  ],
  "not_a_byte_copy_of_missing_library": true
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
   "claim": "20 preset keys enumerated from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes on this worktree.",
   "verdict": "REFUTED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/presets.json",
   "claim": "Independent union of top-level keys over the 72 fixture records is 20, classified 5 metadata / 2 base / 13 delta.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py",
   "claim": "Base version bump migrates every preset or lists the ones it cannot, counted mechanically over all 72.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0101/fixtures/silent_non_editable.json",
   "claim": "A preset that silently overrides a non-editable dial is REJECTED.",
   "verdict": "CONFIRMED"
  }
 ],
 "instantiation": {
  "protocol_schedule": [
   "P-01",
   "P-02"
  ],
  "roster": [
   "Architect",
   "Skeptic",
   "Pragmatist",
   "Critic"
  ],
  "stopping": {
   "max_rounds": 8,
   "on_timeout": "halt"
  },
  "task_id": "CNL-0101-fixture-task",
  "voting": {
   "quorum": 4,
   "rule": "unanimous-or-record-dissent"
  }
 },
 "key_count": 20,
 "key_map": [
  {
   "class": "metadata",
   "key": "id",
   "rationale": "Identity of the preset record; not a CouncilSpec section."
  },
  {
   "class": "metadata",
   "key": "title",
   "rationale": "Human label; not an overlay onto the base spec."
  },
  {
   "class": "metadata",
   "key": "status",
   "rationale": "Catalog-cited DISCOVERY status string; metadata, not overlay."
  },
  {
   "class": "metadata",
   "key": "default_binding",
   "rationale": "Named in CNL-0101; binds a protocol, does not copy a spec."
  },
  {
   "class": "metadata",
   "key": "editable_dials",
   "rationale": "Named in CNL-0101; the allow-list of overlay keys."
  },
  {
   "class": "base",
   "key": "spec_id",
   "rationale": "Names the CouncilSpec this record is a delta over."
  },
  {
   "class": "base",
   "key": "spec_version",
   "rationale": "Pins the base version; rewritten on a successful migrate."
  },
  {
   "class": "delta",
   "key": "charter",
   "rationale": "Optional overlay of IMP-0261 section charter."
  },
  {
   "class": "delta",
   "key": "participants",
   "rationale": "Optional overlay of IMP-0261 section participants."
  },
  {
   "class": "delta",
   "key": "roles",
   "rationale": "Optional overlay of IMP-0261 section roles."
  },
  {
   "class": "delta",
   "key": "engagement",
   "rationale": "Optional overlay; dropped by the v2 bump in this unit."
  },
  {
   "class": "delta",
   "key": "budgets",
   "rationale": "Optional overlay of IMP-0261 section budgets."
  },
  {
   "class": "delta",
   "key": "evidence",
   "rationale": "Optional overlay of IMP-0261 section evidence."
  },
  {
   "class": "delta",
   "key": "voting",
   "rationale": "Optional overlay; catalog-cited axis on all 117 R-A09 specs."
  },
  {
   "class": "delta",
   "key": "stopping",
   "rationale": "Optional overlay; catalog-cited axis on all 117 R-A09 specs."
  },
  {
   "class": "delta",
   "key": "outcomes",
   "rationale": "Optional overlay; CNL-0072 6-variant / 17-enum home."
  },
  {
   "class": "delta",
   "key": "integrity",
   "rationale": "Optional overlay of IMP-0261 section integrity."
  },
  {
   "class": "delta",
   "key": "anti_failure",
   "rationale": "Optional overlay; catalog-cited R-A09 axis."
  },
  {
   "class": "delta",
   "key": "audit",
   "rationale": "Optional overlay; catalog-cited R-A09 axis."
  },
  {
   "class": "delta",
   "key": "consensus",
   "rationale": "Optional overlay; catalog-cited R-A09 axis."
  }
 ],
 "kind": "council_preset_design",
 "libraries_on_this_tree": {
  "/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false
 },
 "library_status": {
  "search_paths": [
   "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
  ],
  "search_space_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was sought on this worktree and at the catalog Windows harness path; Path.is_file is false for every candidate. The 72-record corpus is reconstructed catalog-class.",
  "twelve_council_present": false
 },
 "maps_c_ids": [
  {
   "c_id": "C-M01",
   "mechanism": "C-M01 is the catalog-named measured preset; here it is the full-overlay exemplar that cannot migrate when engagement drops.",
   "relation": "operationalizes"
  },
  {
   "c_id": "C-002",
   "mechanism": "C-002 extends the same typed-delta shape with an engagement overlay and is listed un-migratable on the v2 bump.",
   "relation": "extends"
  }
 ],
 "nearest_sibling": {
  "axes_differ": [
   "base-binding spec_id/spec_version",
   "omitted overlays inherit",
   "artifacts/execution/meta remain on the spec"
  ],
  "distance": 3,
  "named": "fork-copy-of-councilspec",
  "source": "CNL-0101 type contrast: a record that copies artifacts/execution/meta plus every IMP-0261 section"
 },
 "negative_control": {
  "on_state": "voting present while editable_dials is only [roles]",
  "rejects": "silent overlay of a dial not listed in editable_dials",
  "verbatim": "REJECT non-editable-dial-override preset=C-SILENT-OVERRIDE key=voting not in editable_dials=['roles']"
 },
 "preset": {
  "base_spec": {
   "id": "councilspec.v2",
   "version_pin": "1.0.0"
  },
  "default_binding": {
   "protocol_family": "catalog-class",
   "protocol_id": "P-01"
  },
  "delta": {
   "anti_failure": {
    "no_silent_average": true
   },
   "audit": {
    "persist_transcript": true
   },
   "outcomes": {
    "unreconcilable_pair": "irreducible-disagreement"
   },
   "phases": {
    "elicit": {
     "max_rounds": 2
    },
    "reconcile": {
     "max_rounds": 2
    }
   },
   "protocol_schedule": [
    "P-01",
    "P-02"
   ],
   "roles": [
    "Architect",
    "Skeptic",
    "Pragmatist",
    "Critic"
   ],
   "stopping": {
    "max_rounds": 8,
    "on_timeout": "halt"
   },
   "voting": {
    "quorum": 4,
    "rule": "unanimous-or-record-dissent"
   }
  },
  "editable_dials": [
   "roles",
   "voting",
   "stopping",
   "anti_failure",
   "audit",
   "outcomes"
  ],
  "id": "council.preset.typed-delta",
  "kind": "council_preset",
  "on_base_version_bump": "Rewrite spec_version iff every overlay key still exists in the new base; otherwise list the preset and the missing keys. This unit's v2 drop of engagement lists ['C-M01', 'C-002', 'C-003']."
 },
 "preset_count": 72,
 "produced_by": "command-center/p2-wave/probes/CNL-0101/emit_artifact.py",
 "question": "What is the preset type such that the 20 keys already carried by the 72 catalogued presets (including editable_dials and default_binding) express a DELTA over a base spec - and what happens to a preset when the base CouncilSpec version bumps?",
 "residual_unknowns": [
  "Byte-faithful 20-key names from the missing 12-COUNCIL-PROTOCOLS-AND-PRESETS.json cannot be confirmed until that file is on disk."
 ],
 "reviewer": {
  "independent": true,
  "method": "probe1 re-derives the 20-key union and 5/2/13 classification from fixtures/presets.json using its own METADATA/BASE sets.",
  "reviewer_id": "CNL-0101-probe1-schema-and-keys",
  "verdict": "PASS"
 },
 "schema_validation": {
  "affected_error_count": 0,
  "invalid_record_error_count": 1,
  "silent_override_rejected": true,
  "validator": "jsonschema.Draft202012Validator"
 },
 "sentinel": "SUCCESS:CNL-0101",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0101/probe1_schema_and_keys.py",
   "id": "probe1-schema-and-keys",
   "result": "NOT-RUN"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0101/probe2_bump_and_dials.py",
   "id": "probe2-bump-and-dials",
   "result": "NOT-RUN"
  }
 ],
 "title": "A preset is a typed delta over CouncilSpec, not a fork",
 "ts": "2026-08-25T00:54:09Z",
 "unit_id": "CNL-0101",
 "version_bump": {
  "cannot_migrate_count": 3,
  "cannot_migrate_ids": [
   "C-M01",
   "C-002",
   "C-003"
  ],
  "dropped_base_keys": [
   "engagement"
  ],
  "from_version": "1.0.0",
  "migrated_count": 69,
  "to_version": "2.0.0"
 }
}
