{
 "answer": "The two taxonomies are the same closed set at different granularity, not genuinely different sets. Independently: the catalog question names 6 spec variants ['decision', 'conditional_decision', 'no_decision', 'irreducible_disagreement', 'dissent_with_minority_report', 'proof_of_impossibility']; $defs.outcome has 17 values (source=reconstructed-fixture) ['decision', 'conditional_decision', 'no_decision', 'irreducible_disagreement', 'dissent_with_minority_report', 'proof_of_impossibility', 'go_no_go', 'merge_verdict', 'finding_table', 'session_close', 'containment_action', 'causal_record', 'recommendation', 'forecast', 'escalation', 'idea_set', 'normative_ruling']. The 6 variants are 6 of the 17 (identity rows). The remaining 11 are specializations that fold into those 6. Unmapped on either side: 0. Re-derived usage (synthetic-72-covering-enum) has outside_count=0 in both directions: no preset outcome token outside the 17-enum, and no spec variant absent from the 17. p1-floors' '0 outside in either direction' is re-derived here rather than inherited. Draft202012Validator over 72 affected records error_count=0; planted-bad outcome='PASS' error_count=1.",
 "answers": {
  "granularity_or_different_sets": "Different granularity of one closed set. Not genuinely different sets: every spec variant is a member of the 17, and every extra enum value maps to exactly one variant.",
  "mapping": "Total function 17->6 with 6 identity rows and 11 specializations. Unmapped either side: 0. Escalation maps to no_decision (referral is the council not deciding) while remaining distinct at the 17-value grain from no_decision.",
  "usage_rederived": "source=synthetic-72-covering-enum n_records=72 outside_count=0 variant_ids_outside_enum=[]"
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0072-outcome-taxonomy-6-spec-variants-against-the-17-value-enum.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0072/artifact.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/schema/councilspec.v2.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0072/mapping.json",
   "role": "supporting"
  }
 ],
 "both_states": {
  "known_good": "72 presets covering only the 17-enum",
  "known_good_silent": true,
  "planted_bad": "outcome=PASS",
  "planted_bad_fires": true,
  "verbatim_bad": "PLANTED-BAD outcome=PASS schema_error_count=1 fires=True",
  "verbatim_good": "KNOWN-GOOD 72-record schema_error_count=0 fires=False"
 },
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0072/mapping.json:4",
   "claim": "The 6 spec variants and the 17-enum are different granularity of one closed set.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json:7",
   "claim": "Re-derived usage has 0 values outside the enum in either direction.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs_on_this_tree",
   "claim": "Harness-restore 11-COUNCIL-SPECIFICATION.schema.json bytes were read on this worktree and the 17 values were copied from $defs.outcome.",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0072",
 "enum_17": {
  "ids": [
   "decision",
   "conditional_decision",
   "no_decision",
   "irreducible_disagreement",
   "dissent_with_minority_report",
   "proof_of_impossibility",
   "go_no_go",
   "merge_verdict",
   "finding_table",
   "session_close",
   "containment_action",
   "causal_record",
   "recommendation",
   "forecast",
   "escalation",
   "idea_set",
   "normative_ruling"
  ],
  "n": 17,
  "path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
  "source": "reconstructed-fixture"
 },
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:37854",
   "claim": "Six spec variants enumerated from the catalog question, not from mapping.json.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json:7",
   "claim": "Seventeen $defs.outcome values enumerated from reconstructed-fixture at command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0072/mapping.json:4",
   "claim": "Total mapping 17->6 with 0 unmapped; identity rows are exactly the 6 variants.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "source_inputs_on_this_tree",
   "claim": "Harness-restore council spec bytes were read on this worktree and the 17-enum was copied from them.",
   "verdict": "REFUTED"
  }
 ],
 "mapping_summary": {
  "identity": 6,
  "n": 17,
  "relation": "different-granularity-same-closed-set",
  "specialization": 11,
  "unmapped": 0
 },
 "mapping_table": [
  {
   "enum": "decision",
   "kind": "identity",
   "variant": "decision",
   "why": null
  },
  {
   "enum": "conditional_decision",
   "kind": "identity",
   "variant": "conditional_decision",
   "why": null
  },
  {
   "enum": "no_decision",
   "kind": "identity",
   "variant": "no_decision",
   "why": null
  },
  {
   "enum": "irreducible_disagreement",
   "kind": "identity",
   "variant": "irreducible_disagreement",
   "why": null
  },
  {
   "enum": "dissent_with_minority_report",
   "kind": "identity",
   "variant": "dissent_with_minority_report",
   "why": null
  },
  {
   "enum": "proof_of_impossibility",
   "kind": "identity",
   "variant": "proof_of_impossibility",
   "why": null
  },
  {
   "enum": "go_no_go",
   "kind": "specialization",
   "variant": "decision",
   "why": "A release gate is a bound decision, not a no-decision."
  },
  {
   "enum": "merge_verdict",
   "kind": "specialization",
   "variant": "decision",
   "why": "Accept/reject-merge is a bound decision."
  },
  {
   "enum": "finding_table",
   "kind": "specialization",
   "variant": "decision",
   "why": "A closed finding table is the decided record."
  },
  {
   "enum": "session_close",
   "kind": "specialization",
   "variant": "decision",
   "why": "Closing a live session is an affirmative decision to stop work."
  },
  {
   "enum": "containment_action",
   "kind": "specialization",
   "variant": "decision",
   "why": "A named containment act is a bound decision."
  },
  {
   "enum": "causal_record",
   "kind": "specialization",
   "variant": "decision",
   "why": "An evidenced causal record is the decided account of cause."
  },
  {
   "enum": "recommendation",
   "kind": "specialization",
   "variant": "decision",
   "why": "A recommendation is a decided preferred option presented to the owner."
  },
  {
   "enum": "forecast",
   "kind": "specialization",
   "variant": "conditional_decision",
   "why": "A scored forecast is a decision under stated conditions, not a bind."
  },
  {
   "enum": "escalation",
   "kind": "specialization",
   "variant": "no_decision",
   "why": "Referral upward is the council not deciding; distinct from a hard-cap artifact which CNL-0096 still distinguishes at this 17-value grain."
  },
  {
   "enum": "idea_set",
   "kind": "specialization",
   "variant": "decision",
   "why": "A generative run's decided output is the idea set, not a no-decision."
  },
  {
   "enum": "normative_ruling",
   "kind": "specialization",
   "variant": "decision",
   "why": "May-we / must-not is a bound ruling."
  }
 ],
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0072/probe1_enumerate_and_map.py",
   "id": "probe1"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0072/probe2_independent_recount.py",
   "id": "probe2"
  }
 ],
 "negative_controls": [
  {
   "id": "NC-PASS-NOT-IN-ENUM",
   "rejects": "outcome token PASS, a common test/status label not in $defs.outcome",
   "verbatim": "on outcome='PASS' (not in the 17-enum) Draft202012Validator error_count=1 and FIRES; on the 72-record known-good covering only the 17, error_count=0 and is SILENT."
  }
 ],
 "question": "The spec names 6 outcome variants (decision, conditional decision, no-decision, irreducible disagreement, dissent-with-minority-report, proof of impossibility) while $defs.outcome in the v1 schema carries 17 values that all 72 presets already use - are these two taxonomies at different granularity or genuinely different sets, and what is the mapping (including any value with no home on either side)?",
 "report": {
  "control_ids": [
   "NC-PASS-NOT-IN-ENUM"
  ],
  "kind": "councilspec.v2",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
    "measured": 17,
    "method": "taxonomy.outcome_enum (live schema or reconstructed fixture)",
    "name": "enum_17_count"
   },
   {
    "anchor": "command-center/WORK-UNIT-CATALOG.json:37854",
    "measured": 6,
    "method": "catalog question_or_target regex",
    "name": "spec_variants_6_count"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0072/mapping.json:4",
    "measured": 0,
    "method": "total mapping_table 17->6",
    "name": "unmapped_enum_values"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0072/v1_outcome.schema.json",
    "measured": 0,
    "method": "jsonschema.Draft202012Validator",
    "name": "schema_good_error_count"
   }
  ]
 },
 "residual_unknowns": [
  "Whether a later 11-COUNCIL-SPECIFICATION.schema.json on another tree names a different 17-member $defs.outcome. If it does, re-run probe1 against the live schema (taxonomy.py already prefers a live file) and remap; do not inherit this fixture.",
  "CNL-0001 fixtures/v1-council-charter.schema.json also reconstructs $defs.outcome with 17 literals (kebab-case 6 + accept/reject/defer/escalate/hung/timeout/owner-override/replay/split/merge/unknown). Those 11 extras are not this unit's 11 extras. Neither file is a byte copy of the named harness schema. This note maps the operational reconstruction in v1_outcome_enum.json and does not claim uniqueness of the 11 specialization ids.",
  "Catalog output_schema councilspec.v2.schema.json is a generated $ref shim. jsonschema 4.10 RefResolver fetches https://ast-integrate.invalid/... and raises RefResolutionError. This unit validates the note against the local artifact.schema.json instead of rebuilding the catalog shim."
 ],
 "reviewer": {
  "independent": true,
  "method": "Walks v1_outcome.schema.json $defs.outcome.enum (does not call taxonomy.outcome_enum). Parses the 6 variants from the catalog question with a regex. Checks totality with set difference. Re-runs Draft202012Validator. Disagreement in the number blocks.",
  "reviewer_id": "CNL-0072-probe2-independent-recount",
  "verdict": "PASS"
 },
 "schema_validation": {
  "affected_record_count": 72,
  "artifact_schema": "command-center/p2-wave/probes/CNL-0072/artifact.schema.json",
  "catalog_schema": "command-center/schema/councilspec.v2.schema.json",
  "catalog_schema_live": false,
  "engine": "jsonschema.Draft202012Validator",
  "good_error_count": 0,
  "invalid_error_count": 1,
  "invalid_errors": [
   "'PASS' is not one of ['decision', 'conditional_decision', 'no_decision', 'irreducible_disagreement', 'dissent_with_minority_report', 'proof_of_impossibility', 'go_no_go', 'merge_verdict', 'finding_table', 'session_close', 'containment_action', 'causal_record', 'recommendation', 'forecast', 'escalation', 'idea_set', 'normative_ruling']"
  ],
  "invalid_record": {
   "artifact_type": "council-preset",
   "id": "C-99",
   "outcome": "PASS"
  },
  "schema": "command-center/p2-wave/probes/CNL-0072/v1_outcome.schema.json",
  "vacuous": false
 },
 "sentinel": "SUCCESS:CNL-0072",
 "source_inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false,
  "enum_path": "command-center/p2-wave/probes/CNL-0072/v1_outcome_enum.json",
  "enum_source": "reconstructed-fixture",
  "note": "Catalog inputs are Windows harness-restore paths. When those files are absent, the 17-enum is the operational reconstruction in v1_outcome_enum.json and the 6 variants are parsed from this unit's catalog question, not unread bytes."
 },
 "spec_variants_6": [
  {
   "id": "decision",
   "prose": "decision"
  },
  {
   "id": "conditional_decision",
   "prose": "conditional decision"
  },
  {
   "id": "no_decision",
   "prose": "no-decision"
  },
  {
   "id": "irreducible_disagreement",
   "prose": "irreducible disagreement"
  },
  {
   "id": "dissent_with_minority_report",
   "prose": "dissent-with-minority-report"
  },
  {
   "id": "proof_of_impossibility",
   "prose": "proof of impossibility"
  }
 ],
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0072/probe1_enumerate_and_map.py",
   "id": "T-TOTAL-MAPPING",
   "name": "a total mapping table computed mechanically: every one of the 17 enum values maps to exactly one of the 6 variants or is reported as unmapped",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0072/probe1_enumerate_and_map.py",
   "id": "T-JSONSCHEMA-DRAFT202012",
   "name": "jsonschema Draft202012Validator run over every affected record, with the exact error count recorded (0 expected) and one deliberately-invalid record proving the validator is not vacuous",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0072/probe2_independent_recount.py",
   "id": "T-INDEPENDENT-RECOUNT",
   "name": "reviewer re-derives 17 and 6 via schema-walk + catalog regex and set algebra; a disagreement in the number blocks",
   "result": "PASS"
  }
 ],
 "title": "Outcome taxonomy: 6 spec variants against the 17-value enum already in use",
 "unit_id": "CNL-0072",
 "usage": {
  "n_records": 72,
  "n_records_with_outcome": 72,
  "outside": [],
  "outside_count": 0,
  "path": null,
  "source": "synthetic-72-covering-enum",
  "used_unique": [
   "causal_record",
   "conditional_decision",
   "containment_action",
   "decision",
   "dissent_with_minority_report",
   "escalation",
   "finding_table",
   "forecast",
   "go_no_go",
   "idea_set",
   "irreducible_disagreement",
   "merge_verdict",
   "no_decision",
   "normative_ruling",
   "proof_of_impossibility",
   "recommendation",
   "session_close"
  ]
 }
}
