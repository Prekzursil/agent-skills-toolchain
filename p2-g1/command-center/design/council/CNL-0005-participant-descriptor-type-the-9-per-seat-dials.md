{
 "artifacts": [
  {
   "bytes": 12994,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0005/participant.py",
   "role": "primary",
   "sha256": "6d0e0cdc6909e00f1298beb769a4d6d8a0947b1025078e671731db2821c63450"
  },
  {
   "bytes": 1986,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0005/participant.schema.json",
   "role": "supporting",
   "sha256": "158608f9bd4021e876889431aa536afc1216c1a363c803a35ff57e4d130f94cd"
  },
  {
   "bytes": 6278,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0005/v1_seat.py",
   "role": "supporting",
   "sha256": "307c7ceaf27d538eebf36f1b3c8e2f66b621c16e93ba4745e6748a09522cf00b"
  },
  {
   "bytes": 1402,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0005/schema_check.py",
   "role": "supporting",
   "sha256": "3e9e0e18a02b08cb448c9765fcce85e2d58b47c46b8ac17d269df9d99a42e521"
  },
  {
   "bytes": 4603,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0005/offline_validate.py",
   "role": "supporting",
   "sha256": "cb62ce7096591f9eb9253aa9f360226ba5c68d47ec7eced2945e8df4e3a18e78"
  }
 ],
 "defects": [],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
   "consumer": "command-center/p2-wave/probes/CNL-0005/offline_validate.py",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "python3 command-center/p2-wave/probes/CNL-0005/offline_validate.py",
    "exit_code": 0,
    "fingerprint": "cnl0005:offline-validate:councilspec.v2",
    "method": "schema-validate",
    "raw_output": "catalog councilspec.v2 errors=0; garbage rejected",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0005/participant.py:217",
   "claim": "Zero-dial-diff pair (scribe-1 vs scribe-clone, all optional dials omitted) fires DUPLICATE_SEAT; distinct-model pair is silent.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe1_indistinguishability.py",
     "exit_code": 0,
     "fingerprint": "cnl0005:identity-tuple:probe1",
     "method": "command",
     "raw_output": "On the rejected state (two seats that differ in NO dial, including after filling optional defaults) the check reports fired=True codes=['DUPLICATE_SEAT'] seat_ids=['scribe-1', 'scribe-clone']. It does not silently accept the pair. On the accepted state (two seats that differ in at least one filled dial) the same check reports fired=False findings=[].",
     "role": "source"
    },
    {
     "command": "python3 -c \"import participant as P; print(P.find_duplicates(P.zero_dial_diff_pair())['fired'])\"",
     "exit_code": 0,
     "fingerprint": "cnl0005:find-duplicates:direct",
     "method": "schema-validate",
     "raw_output": "fired=True codes=['DUPLICATE_SEAT']",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0005/schema_check.py:8",
   "claim": "Draft202012Validator error_count=0 on the three-seat good roster; planted missing-model record error_count=1.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe2_schema_vacuity.py",
     "exit_code": 0,
     "fingerprint": "cnl0005:draft202012:probe2",
     "method": "schema-validate",
     "raw_output": "On the rejected state (missing required property 'model') Draft202012Validator reports error_count=1 messages=[\"'model' is a required property\"]. On the accepted three-seat good roster the same validator reports error_count=0.",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/schema_check.py",
     "exit_code": 0,
     "fingerprint": "cnl0005:schema-check:error-count",
     "method": "command",
     "raw_output": "good=0 planted=1",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "manifest_registration": {
  "entry_id": "CNL-0005",
  "manifest_path": "command-center/p2-wave/probes/CNL-0005/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "bad_state_output": "On the rejected state (two seats that differ in NO dial, including after filling optional defaults) the check reports fired=True codes=['DUPLICATE_SEAT'] seat_ids=['scribe-1', 'scribe-clone']. It does not silently accept the pair. On the accepted state (two seats that differ in at least one filled dial) the same check reports fired=False findings=[].",
   "description": "two seats that differ in no filled dial, including different seat_id",
   "fired_on_bad_state": true,
   "good_state_output": "fired=False findings=[]",
   "id": "CNL0005-C1-zero-dial-diff",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "On the rejected state (missing required property 'model') Draft202012Validator reports error_count=1 messages=[\"'model' is a required property\"]. On the accepted three-seat good roster the same validator reports error_count=0.",
   "description": "a participant object with no model property",
   "fired_on_bad_state": true,
   "good_state_output": "error_count=0",
   "id": "CNL0005-C2-missing-model",
   "kind": "malformed-input",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "opus",
  "role": "council-systems-designer",
  "vendor": "anthropic"
 },
 "report": {
  "answer": "The participant descriptor has nine behavioral dials: model, vendor, expertise, role, authority, vote_weight, tools, effort, context. Required (no silent default): ['model', 'role', 'authority']. Optional with closed defaults: ['vendor', 'expertise', 'vote_weight', 'tools', 'effort', 'context'] (vendor uniquely derived from model, else VENDOR_AMBIGUOUS; expertise=null; vote_weight=1.0; tools=[]; effort=inherit; context=shared). seat_id is an address, not a tenth dial. Two seats whose filled identity tuples match are DUPLICATE_SEAT. SUCCESS:CNL-0005",
  "catalog_claims": [
   {
    "anchor": "command-center/WORK-UNIT-CATALOG.json:34538",
    "claim": "The complete type is the nine named dials plus seat_id as a non-behavioral address.",
    "id": "C1",
    "verdict": "CONFIRMED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0005/participant.py:23",
    "claim": "vendor, expertise, vote_weight, tools, effort, context may be unspecified; model, role, authority may not.",
    "id": "C2",
    "verdict": "CONFIRMED"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0005/participant.py:248",
    "claim": "Zero-dial-diff seats are DUPLICATE_SEAT, not silently accepted.",
    "id": "C3",
    "verdict": "CONFIRMED"
   }
  ],
  "control_ids": [
   "CNL0005-C1-zero-dial-diff",
   "CNL0005-C2-missing-model"
  ],
  "decision": {
   "identity_excludes_seat_id": true,
   "optional_defaults": {
    "context": "shared",
    "effort": "inherit",
    "expertise": null,
    "tools": [],
    "vendor": "unique registry derivation or VENDOR_AMBIGUOUS",
    "vote_weight": 1.0
   },
   "optional_dials": [
    "vendor",
    "expertise",
    "vote_weight",
    "tools",
    "effort",
    "context"
   ],
   "required_dials": [
    "model",
    "role",
    "authority"
   ],
   "summary": "The participant descriptor has nine behavioral dials: model, vendor, expertise, role, authority, vote_weight, tools, effort, context. Required (no silent default): ['model', 'role', 'authority']. Optional with closed defaults: ['vendor', 'expertise', 'vote_weight', 'tools', 'effort', 'context'] (vendor uniquely derived from model, else VENDOR_AMBIGUOUS; expertise=null; vote_weight=1.0; tools=[]; effort=inherit; context=shared). seat_id is an address, not a tenth dial. Two seats whose filled identity tuples match are DUPLICATE_SEAT. SUCCESS:CNL-0005",
   "why_optional_does_not_collapse_distinct_seats": "Omitting an optional dial applies a closed default. Seats that still differ on any identity dial remain distinguishable. Seats that match after filling are indistinguishable and are flagged DUPLICATE_SEAT rather than silently accepted.",
   "why_required_cannot_default": {
    "authority": "Defaulting authority is silent privilege change.",
    "model": "Defaulting a model is silent substitution.",
    "role": "A seat without a role has no mandate."
   }
  },
  "filled_good_roster": [
   {
    "authority": {
     "can_bind": true,
     "can_veto": false,
     "kind": "chair"
    },
    "context": "shared",
    "effort": "high",
    "expertise": "systems-architecture",
    "model": "claude-opus-4",
    "role": "chair",
    "seat_id": "chair-1",
    "tools": [
     "grep",
     "read"
    ],
    "vendor": "anthropic",
    "vote_weight": 1.0
   },
   {
    "authority": {
     "can_bind": false,
     "can_veto": false,
     "kind": "vote"
    },
    "context": "shared",
    "effort": "medium",
    "expertise": null,
    "model": "gpt-4.1",
    "role": "critic",
    "seat_id": "critic-1",
    "tools": [
     "read"
    ],
    "vendor": "openai",
    "vote_weight": 1.0
   },
   {
    "authority": {
     "can_bind": false,
     "can_veto": false,
     "kind": "observe"
    },
    "context": "shared",
    "effort": "inherit",
    "expertise": null,
    "model": "gemini-2.5-pro",
    "role": "scribe",
    "seat_id": "scribe-1",
    "tools": [],
    "vendor": "google",
    "vote_weight": 1.0
   }
  ],
  "format_note": "Catalog output_path ends in .md. G-1 _measure_one_delivered.py json.loads the whole file, so this artifact is JSON, not prose markdown.",
  "indistinguishability": {
   "distinct_model_silent": true,
   "good_roster_silent": true,
   "rule": "Two seats that differ in NO filled dial, including after optional defaults, are DUPLICATE_SEAT even when seat_id differs.",
   "vendor_derived_collapses": true,
   "zero_dial_diff_fires": true
  },
  "inputs_on_this_tree": {
   "11-COUNCIL-SPECIFICATION.schema.json": false,
   "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
   "_USER-PROMPTS.md:10746-10767": false,
   "_USER-PROMPTS.md:10915-10946": false,
   "note": "Catalog inputs point at a Windows harness-restore tree that is absent here. $defs.seat is recorded NOT-MEASURABLE. The type is specified from this unit's question_or_target and checked against live fixtures."
  },
  "kind": "council-design-note",
  "named_probes": [
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe1_indistinguishability.py",
    "id": "probe1",
    "role": "indistinguishability"
   },
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe2_schema_vacuity.py",
    "id": "probe2",
    "role": "schema-vacuity"
   }
  ],
  "nine_dials": [
   {
    "behavioral": true,
    "id": "model",
    "omissible": false,
    "required": true,
    "type": "string"
   },
   {
    "behavioral": true,
    "default": "unique MODEL_VENDOR_REGISTRY derivation",
    "id": "vendor",
    "omissible": true,
    "omit_fails_when": "model maps to more than one vendor",
    "required": false,
    "type": "string"
   },
   {
    "behavioral": true,
    "default": null,
    "id": "expertise",
    "omissible": true,
    "required": false,
    "type": [
     "string",
     "null"
    ]
   },
   {
    "behavioral": true,
    "id": "role",
    "omissible": false,
    "required": true,
    "type": "string"
   },
   {
    "behavioral": true,
    "fields": [
     "kind",
     "can_bind",
     "can_veto"
    ],
    "id": "authority",
    "omissible": false,
    "required": true,
    "type": "object"
   },
   {
    "behavioral": true,
    "default": 1.0,
    "id": "vote_weight",
    "omissible": true,
    "required": false,
    "type": "number"
   },
   {
    "behavioral": true,
    "default": [],
    "id": "tools",
    "omissible": true,
    "required": false,
    "type": "array"
   },
   {
    "behavioral": true,
    "default": "inherit",
    "id": "effort",
    "omissible": true,
    "required": false,
    "type": "string"
   },
   {
    "behavioral": true,
    "default": "shared",
    "id": "context",
    "omissible": true,
    "required": false,
    "type": "string"
   }
  ],
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0005/participant.py:217",
    "measured": true,
    "method": "canonical identity tuple after closed defaults",
    "name": "zero-dial-diff-duplicate-seat"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0005/schema_check.py:8",
    "measured": 0,
    "method": "jsonschema Draft202012Validator.iter_errors",
    "name": "draft202012-good-record-error-count"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0005/schema_check.py:8",
    "measured": 1,
    "method": "jsonschema Draft202012Validator.iter_errors",
    "name": "draft202012-planted-invalid-error-count"
   }
  ],
  "on_disk_analog": {
   "carries": [],
   "def_name": null,
   "extra_fields_not_in_nine": [],
   "lacks": [
    "model",
    "vendor",
    "expertise",
    "role",
    "authority",
    "vote_weight",
    "tools",
    "effort",
    "context"
   ],
   "note": "11-COUNCIL-SPECIFICATION.schema.json $defs.seat is not on this Linux worktree. command-center/schema/council-preset.schema.json is now a generated $ref shim, so $defs.role is also absent. Nine-dial name matches on that object: none. Nine dials absent there: ['model', 'vendor', 'expertise', 'role', 'authority', 'vote_weight', 'tools', 'effort', 'context']. CNL-0005 specifies the missing participant descriptor type.",
   "path": "command-center/schema/council-preset.schema.json"
  },
  "participant_descriptor_schema": {
   "$defs": {
    "authority": {
     "additionalProperties": false,
     "properties": {
      "can_bind": {
       "type": "boolean"
      },
      "can_veto": {
       "type": "boolean"
      },
      "kind": {
       "enum": [
        "observe",
        "advise",
        "vote",
        "chair",
        "bind"
       ],
       "type": "string"
      }
     },
     "required": [
      "kind"
     ],
     "type": "object"
    },
    "participant_descriptor": {
     "additionalProperties": false,
     "properties": {
      "authority": {
       "$ref": "#/$defs/authority"
      },
      "context": {
       "minLength": 1,
       "type": "string"
      },
      "effort": {
       "enum": [
        "inherit",
        "low",
        "medium",
        "high"
       ],
       "type": "string"
      },
      "expertise": {
       "minLength": 1,
       "type": [
        "string",
        "null"
       ]
      },
      "model": {
       "minLength": 1,
       "type": "string"
      },
      "role": {
       "minLength": 1,
       "type": "string"
      },
      "seat_id": {
       "description": "Roster address. Not a behavioral dial. Duplicate identity with a different seat_id is still DUPLICATE_SEAT.",
       "minLength": 1,
       "type": "string"
      },
      "tools": {
       "items": {
        "minLength": 1,
        "type": "string"
       },
       "type": "array",
       "uniqueItems": true
      },
      "vendor": {
       "minLength": 1,
       "type": "string"
      },
      "vote_weight": {
       "exclusiveMinimum": 0,
       "type": "number"
      }
     },
     "required": [
      "seat_id",
      "model",
      "role",
      "authority"
     ],
     "type": "object"
    },
    "roster": {
     "additionalProperties": false,
     "properties": {
      "id": {
       "minLength": 1,
       "type": "string"
      },
      "seats": {
       "items": {
        "$ref": "#/$defs/participant_descriptor"
       },
       "minItems": 1,
       "type": "array"
      }
     },
     "required": [
      "id",
      "seats"
     ],
     "type": "object"
    }
   },
   "$ref": "#/$defs/participant_descriptor",
   "$schema": "https://json-schema.org/draft/2020-12/schema",
   "title": "CouncilSpec v2 participant descriptor (CNL-0005, 9 per-seat dials)"
  },
  "question": "What is the complete participant descriptor type covering model, vendor, expertise, role, authority, vote weight, tools, effort and context - and which of those nine can be left unspecified without making two seats behaviourally indistinguishable?",
  "reviewer_counterexample": "A uniqueItems-on-seat_id schema would accept scribe-1 and scribe-clone because their ids differ. Probe 1 flags them DUPLICATE_SEAT. Probe 2 independently recounts Draft202012 error counts against the artifact.",
  "schema_validation": {
   "additionalProperties_live": true,
   "catalog_output_schema": "command-center/schema/councilspec.v2.schema.json",
   "exclusiveMinimum_live": true,
   "good_record_error_count": 0,
   "good_roster_error_count": 0,
   "planted_invalid_error_count": 1,
   "planted_invalid_messages": [
    "'model' is a required property"
   ],
   "schema_path": "command-center/p2-wave/probes/CNL-0005/participant.schema.json",
   "validator": "jsonschema.Draft202012Validator"
  },
  "title": "Participant descriptor type: the 9 per-seat dials",
  "v1_$defs.seat": {
   "declared_path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
   "note": "Catalog evidence_requirement cites $defs.seat in the Windows harness-restore tree. That file is absent on this Linux worktree (searched declared path plus repo-relative successors). Field-by-field citation of $defs.seat is therefore NOT-MEASURABLE here. The nine dials are taken from this unit's question_or_target. The live on-disk analog is council-preset.schema.json $defs.role (id, count, votes, obligation) \u2014 a role slot, not a participant descriptor.",
   "path": null,
   "present": false,
   "properties": {},
   "property_names": [],
   "searched": [
    {
     "exists": false,
     "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"
    },
    {
     "exists": false,
     "path": "/opt/p2/ast-integrate/11-COUNCIL-SPECIFICATION.schema.json"
    },
    {
     "exists": false,
     "path": "/opt/p2/ast-integrate/command-center/sources/11-COUNCIL-SPECIFICATION.schema.json"
    },
    {
     "exists": false,
     "path": "/opt/p2/ast-integrate/command-center/schema/11-COUNCIL-SPECIFICATION.schema.json"
    },
    {
     "error": "no-$defs.seat",
     "exists": true,
     "path": "/opt/p2/ast-integrate/platform/schema/councilspec.schema.json"
    },
    {
     "error": "no-$defs.seat",
     "exists": true,
     "path": "/opt/p2/ast-integrate/platform/schema/councilspec.schema.json"
    },
    {
     "exists": false,
     "path": "/opt/p2/ast-integrate/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json"
    }
   ]
  },
  "v1_field_by_field": [
   {
    "dial": "model",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "vendor",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "expertise",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "role",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "authority",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "vote_weight",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "tools",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "effort",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   },
   {
    "dial": "context",
    "on_disk_preset_roles": false,
    "preset_anchor": null,
    "v1_$defs.seat": "NOT-MEASURABLE-FILE-ABSENT"
   }
  ]
 },
 "residual_unknowns": [
  {
   "claim": "Catalog evidence_requirement cites $defs.seat in 11-COUNCIL-SPECIFICATION.schema.json on a Windows harness-restore tree.",
   "settling_experiment": "Mount the declared harness-restore path or a byte-identical copy and re-run v1_seat.field_by_field().",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot (AGENTS.md 4b)"
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "A uniqueItems-on-seat_id schema would accept scribe-1 and scribe-clone because their ids differ. Probe 1 flags them DUPLICATE_SEAT. Probe 2 independently recounts Draft202012 error counts against the artifact.",
  "reviewer_id": "CNL-0005-probe1-indistinguishability-counterexample",
  "vendor": "local",
  "verdict": "PASS"
 },
 "schema_validation": {
  "additionalProperties_live": true,
  "catalog_output_schema": "command-center/schema/councilspec.v2.schema.json",
  "exclusiveMinimum_live": true,
  "good_record_error_count": 0,
  "good_roster_error_count": 0,
  "planted_invalid_error_count": 1,
  "planted_invalid_messages": [
   "'model' is a required property"
  ],
  "schema_path": "command-center/p2-wave/probes/CNL-0005/participant.schema.json",
  "validator": "jsonschema.Draft202012Validator"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0005",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:34538",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe1_indistinguishability.py",
   "id": "probe1-indistinguishability",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0005/probe2_schema_vacuity.py",
   "id": "probe2-schema-vacuity",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "duration_seconds": 0,
  "ended_at": "2026-08-25T00:58:55Z",
  "started_at": "2026-08-25T00:58:55Z"
 },
 "unit_id": "CNL-0005"
}
