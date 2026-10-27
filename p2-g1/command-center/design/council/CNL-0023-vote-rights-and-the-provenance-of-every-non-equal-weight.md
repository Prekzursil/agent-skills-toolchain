{
 "answer": "Equal suffrage is the default: omitted vote_weight means 1.0, and an explicit 1.0 needs no provenance. A seat may differ from 1.0 only as a recorded exception to that vote RIGHT, and only at spec validation, before the council runs. The exception must (1) be a finite weight in (0, 4.0], (2) name one allowed justification_class {owner_decision, charter_authority, conflict_discount}, (3) carry a weight_provenance object whose expected_weight equals the declared vote_weight, (4) point at an on-disk justifying artifact whose LF-normalized sha256 matches source_sha256, and (5) name a challenge_path an auditor can execute after the decision (re-validate the spec, then recompute the equal-weight counterfactual \u2014 CNL-0064). conflict_discount additionally requires weight < 1.0. A self-description such as 'domain expert' is not an allowed class; that label without a calibration receipt is UNJUSTIFIED_NON_EQUAL_WEIGHT / PROVENANCE_CLASS_NOT_ALLOWED. An unjustified non-equal weight is REJECTED at spec validation; the council runner is not invoked. SUCCESS:CNL-0023",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json",
   "role": "schema-slice"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0023/validator.py",
   "role": "spec-gate"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0023/recount.py",
   "role": "independent-recount"
  }
 ],
 "conditions_for_non_equal_weight": [
  {
   "class": "owner_decision",
   "must_cite": "owner decision record id + sha256 of that record",
   "when": "The owner recorded a named multiplier for this seat on this council before roster freeze."
  },
  {
   "class": "charter_authority",
   "must_cite": "charter clause id + sha256 of the clause artifact",
   "when": "A named charter clause grants this office a multiplier."
  },
  {
   "class": "conflict_discount",
   "must_cite": "conflict record id + sha256; vote_weight must be < 1.0",
   "when": "A declared conflict reduces weight below 1.0 rather than silent recusal."
  }
 ],
 "default": {
  "omitted_vote_weight": 1.0,
  "rule": "equal suffrage",
  "vote_weight": 1.0
 },
 "dependency_cnl_0022": {
  "artifact_present": false,
  "effect": "Vote is a RIGHT in the obligation/permission/right split. This unit implements the exception ledger for that right without importing CNL-0022. Missing CNL-0022 does not park the gate: the default of 1.0 and the provenance check are executable on this tree.",
  "required_by_catalog": true
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0023/validator.py",
   "claim": "validate_spec ACCEPTs known-good (2 equal + 3 justified non-equal) and REJECTs planted-bad without starting the council.",
   "signal": "python validator over fixtures",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0023/recount.py",
   "claim": "Independent recount of the same fixtures yields the same seat counts and the same three unjustified seat ids.",
   "signal": "recount.py does not import validator.py",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json",
   "claim": "Draft 2020-12 schema is SILENT on known-good, FIRES when a non-equal seat omits weight_provenance, and rejects garbage (not vacuous). It does not hash files, so a forged source_sha256 is a python-only catch.",
   "signal": "jsonschema Draft202012Validator",
   "verdict": "CONFIRMED"
  }
 ],
 "forbidden_justifications": [
  "expertise_claim / 'I am a domain expert' without a calibration receipt",
  "missing weight_provenance on vote_weight != 1.0",
  "provenance whose source_sha256 does not match the artifact bytes",
  "conflict_discount with vote_weight >= 1.0",
  "weight <= 0 or weight > 4.0"
 ],
 "inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false,
  "note": "Catalog inputs cite a Windows harness-restore path that is absent here. The gate is implemented as a CouncilSpec v2 vote-weight slice with fixtures on this worktree, not by quoting a missing v1 schema."
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0023/probe1_both_states.py",
   "id": "probe1",
   "role": "both-states-and-negative-control"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0023/probe2_independent_recount.py",
   "id": "probe2",
   "role": "independent-recount"
  }
 ],
 "negative_control": {
  "expected": "REJECT before council run",
  "fixture": "command-center/p2-wave/probes/CNL-0023/fixtures/planted-bad.json",
  "observed": {
   "codes": [
    "UNJUSTIFIED_NON_EQUAL_WEIGHT",
    "PROVENANCE_CLASS_NOT_ALLOWED",
    "PROVENANCE_DIGEST_MISMATCH"
   ],
   "council_ran": false,
   "verdict": "REJECT"
  },
  "planted_state": "seat.expert-unjustified declares vote_weight=2.5 with no weight_provenance",
  "what_the_check_does": "validate_spec returns REJECT with code UNJUSTIFIED_NON_EQUAL_WEIGHT for that seat and run_if_valid leaves COUNCIL_RUNS unchanged, so the council never tabulates."
 },
 "output_schema": "command-center/schema/councilspec.v2.schema.json",
 "output_schema_note": "The catalog names the shared CouncilSpec v2 envelope (CNL-0001). This unit contributes $defs.weight_provenance / seat vote-weight rules as command-center/p2-wave/probes/CNL-0023/vote-weight.schema.json rather than inventing the whole v2 root envelope.",
 "provenance_record_required_fields": [
  "justification_class",
  "source_kind",
  "source_id",
  "source_path",
  "source_sha256",
  "issued_by",
  "challenge_path",
  "expected_weight"
 ],
 "question": "Under what conditions may a seat's vote weight differ from 1.0, and what provenance record must accompany the weight so an auditor can challenge it after the decision is made?",
 "reviewer": {
  "independent": true,
  "method": "recount.py over fixtures, not the author's narrative",
  "reviewer_id": "CNL-0023-probe2-independent-recount",
  "verdict": "PASS"
 },
 "reviewer_recount": {
  "independent": true,
  "known_good": {
   "equal_weight": 2,
   "justified_non_equal": 3,
   "seats": 5,
   "unjustified_count": 0
  },
  "method": "recount.py over fixtures, not the author's narrative",
  "planted_bad": {
   "equal_weight": 2,
   "justified_non_equal": 1,
   "seats": 6,
   "unjustified_count": 3,
   "unjustified_seat_ids": [
    "seat.expert-unjustified",
    "seat.expert-label",
    "seat.tampered-digest"
   ],
   "whys": [
    "missing-provenance",
    "class-not-allowed",
    "digest-mismatch"
   ]
  },
  "validator_agreement": true
 },
 "sentinel": "SUCCESS:CNL-0023",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0023/probe1_both_states.py",
   "id": "both-states",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0023/probe2_independent_recount.py",
   "id": "independent-recount",
   "result": "PASS"
  }
 ],
 "unit_id": "CNL-0023",
 "validation_measured": {
  "known_good": {
   "codes": [],
   "council_ran": false,
   "equal_weight": 2,
   "justified_non_equal": 3,
   "schema_error_count": 0,
   "verdict": "ACCEPT"
  },
  "planted_bad": {
   "codes": [
    "UNJUSTIFIED_NON_EQUAL_WEIGHT",
    "PROVENANCE_CLASS_NOT_ALLOWED",
    "PROVENANCE_DIGEST_MISMATCH"
   ],
   "council_ran": false,
   "schema_error_count": 3,
   "unjustified": [
    {
     "code": "UNJUSTIFIED_NON_EQUAL_WEIGHT",
     "detail": "non-equal weight has no weight_provenance; rejected before the council runs",
     "seat_id": "seat.expert-unjustified",
     "vote_weight": 2.5
    },
    {
     "code": "PROVENANCE_CLASS_NOT_ALLOWED",
     "detail": "justification_class 'expertise_claim' is not in ['charter_authority', 'conflict_discount', 'owner_decision']",
     "seat_id": "seat.expert-label",
     "vote_weight": 3.0
    },
    {
     "code": "PROVENANCE_DIGEST_MISMATCH",
     "detail": "source_sha256 0000000000000000000000000000000000000000000000000000000000000000 != live dd86378005ff924c59e34ece7b8f30ab7aa471e2119af2b0d0c0aa8fe34bb1ac",
     "seat_id": "seat.tampered-digest",
     "vote_weight": 2.0
    }
   ],
   "verdict": "REJECT"
  }
 },
 "vote_weight_schema": {
  "$defs": {
   "seat": {
    "additionalProperties": true,
    "allOf": [
     {
      "if": {
       "properties": {
        "vote_weight": {
         "not": {
          "const": 1.0
         }
        }
       },
       "required": [
        "vote_weight"
       ]
      },
      "then": {
       "required": [
        "weight_provenance"
       ]
      }
     }
    ],
    "properties": {
     "role": {
      "minLength": 1,
      "type": "string"
     },
     "seat_id": {
      "minLength": 1,
      "type": "string"
     },
     "vote_weight": {
      "$ref": "#/$defs/weight"
     },
     "weight_provenance": {
      "$ref": "#/$defs/weight_provenance"
     }
    },
    "required": [
     "seat_id"
    ],
    "type": "object"
   },
   "weight": {
    "exclusiveMinimum": 0,
    "maximum": 4.0,
    "type": "number"
   },
   "weight_provenance": {
    "additionalProperties": false,
    "properties": {
     "challenge_path": {
      "minLength": 8,
      "type": "string"
     },
     "expected_weight": {
      "$ref": "#/$defs/weight"
     },
     "issued_by": {
      "minLength": 1,
      "type": "string"
     },
     "justification_class": {
      "enum": [
       "charter_authority",
       "conflict_discount",
       "owner_decision"
      ],
      "type": "string"
     },
     "source_id": {
      "minLength": 1,
      "type": "string"
     },
     "source_kind": {
      "minLength": 1,
      "type": "string"
     },
     "source_path": {
      "minLength": 8,
      "type": "string"
     },
     "source_sha256": {
      "pattern": "^[0-9a-f]{64}$",
      "type": "string"
     }
    },
    "required": [
     "challenge_path",
     "expected_weight",
     "issued_by",
     "justification_class",
     "source_id",
     "source_kind",
     "source_path",
     "source_sha256"
    ],
    "type": "object"
   }
  },
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "additionalProperties": true,
  "properties": {
   "id": {
    "minLength": 3,
    "type": "string"
   },
   "seats": {
    "items": {
     "$ref": "#/$defs/seat"
    },
    "minItems": 1,
    "type": "array"
   }
  },
  "required": [
   "id",
   "seats"
  ],
  "title": "CouncilSpec v2 vote-weight provenance slice (CNL-0023)",
  "type": "object"
 },
 "weight_max": 4.0
}
