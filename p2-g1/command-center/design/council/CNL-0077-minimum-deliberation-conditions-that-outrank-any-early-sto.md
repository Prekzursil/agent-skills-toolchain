{
  "schema_version": 1,
  "unit_id": "CNL-0077",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0077",
  "spec_anchor": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md:11338",
  "min_bytes_threshold": 1024,
  "profile": "council-design-note",
  "artifacts": [
    {
      "path": "command-center/p2-wave/probes/CNL-0077/floor.py",
      "bytes": 11970,
      "sha256": "adafa811d204a779df941aa29e5883641d4113c0029ebf17b6cfa2462d012358",
      "exists": true,
      "eol": "CRLF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0077/probe1_satisfied_but_floored.py",
      "bytes": 5948,
      "sha256": "7505135318056cd0b48be22bafec66482354c78acaa2731e0a9b598e3c92216e",
      "exists": true,
      "eol": "CRLF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0077/probe2_ceiling_hang.py",
      "bytes": 6199,
      "sha256": "b9c729c36fc4a69605dc6cd866e4f49d2417b9de8b815a13fd04d7d3884de3b9",
      "exists": true,
      "eol": "CRLF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json",
      "bytes": 404,
      "sha256": "578239cb0692aa2b68d0ed7efa41c745376319b03db993615af8c0be7213dff2",
      "exists": true,
      "eol": "CRLF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json",
      "bytes": 371,
      "sha256": "b31a45cac8fb4fd54f2fdd5b517f899aed34e648a5cb5c174519d5de6f996c79",
      "exists": true,
      "eol": "CRLF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
      "bytes": 592919,
      "sha256": "e76431a24ffe63f51eb2a444aac30ede56140ed32f59692add3c22194856197a",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "bytes": 1118,
      "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    }
  ],
  "evidence": [
    {
      "claim": "A satisfied stop with unmet floors CONTINUES and records STOP-BLOCKED-BY-FLOOR naming each unmet floor; it does not rewrite the expression to false.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "python3 -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0077'); import floor as F; fix=json.load(open('command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json')); print(json.dumps(F.evaluate(fix['spec'],fix['state'],True),sort_keys=True,default=str))\"",
          "raw_output": "{\"action\": \"CONTINUE\", \"reason\": \"STOP-BLOCKED-BY-FLOOR\", \"unmet\": [\"min_rounds\", \"min_independent_briefs\", \"min_evidence_items\", \"mandated_roles_spoken\"], \"would_fire_without_floor\": true}",
          "fingerprint": "a35feedf7bc3420a945f69fdfca649fe",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json",
          "raw_output": "{\"reviewer_recount_unmet\": [\"min_rounds\", \"min_independent_briefs\", \"min_evidence_items\", \"mandated_roles_spoken\"]}",
          "fingerprint": "37f670d3743e60f1d204a89d1c9e4c94",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "A floor with no ceiling is rejected at validation (floor-with-no-ceiling) and is never honoured at runtime.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "python3 -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0077'); import floor as F; fix=json.load(open('command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json')); print(json.dumps(F.validate_spec(fix['spec'])))\"",
          "raw_output": "{\"validation_errors\": [\"floor-with-no-ceiling\"]}",
          "fingerprint": "fec5eaacd7577a52e3a4020f0c8e96fe",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json",
          "raw_output": "max_rounds key absent from spec",
          "fingerprint": "7914a5610f73d61fb0d22d20ebc22cf3",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0077/probe1_satisfied_but_floored.py",
      "result": "PASS"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0077/probe2_ceiling_hang.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-ungated-premature-stop",
      "kind": "known-broken-fixture",
      "description": "gate_enabled=false on satisfied-but-floored must TERMINATE with PREMATURE-STOP (FC-11338); gated kernel must CONTINUE with STOP-BLOCKED-BY-FLOOR.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"action\": \"TERMINATE\", \"reason\": \"PREMATURE-STOP\"}",
      "good_state_output": "{\"action\": \"CONTINUE\", \"reason\": \"STOP-BLOCKED-BY-FLOOR\", \"unmet\": [\"min_rounds\", \"min_independent_briefs\", \"min_evidence_items\", \"mandated_roles_spoken\"], \"would_fire_without_floor\": true}"
    },
    {
      "id": "NC-hang-mutant",
      "kind": "mutation",
      "description": "Raising max_rounds past hang_guard must set hung=true; a bounded ceiling must terminate FLOOR-UNMET-AT-CEILING.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "hung=true terminated=false hang_guard=5",
      "good_state_output": "hung=False reason=FLOOR-UNMET-AT-CEILING"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0077-probe2-independent-kernel-recount",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": true,
    "notes": "Mechanical re-tabulation of floors_unmet from fixture bytes, not from the design-note prose. Counterexample: ungated satisfied-but-floored terminates PREMATURE-STOP."
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0077/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0077"
  },
  "downstream_consumers": [
    {
      "consumer": "command-center/p2-wave/probes/CNL-0077/schema_check.py",
      "artifact_path": "command-center/design/council/CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "schema-validate",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0077'); import schema_check as SC; print(SC.error_list(json.load(open('command-center/design/council/CNL-0077-minimum-deliberation-conditions-that-outrank-any-early-sto.md'))))\"",
        "raw_output": "errors=[]",
        "fingerprint": "89a561c26850dc30ebd1134b4e4781cb",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-25T00:59:46Z",
    "ended_at": "2026-08-25T00:59:46Z",
    "duration_seconds": 0
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts, then emit FAILED:CNL-0077."
  },
  "residual_unknowns": [
    {
      "claim": "Windows harness-restore _USER-PROMPTS.md:10746-10767 and :11338 are not mounted on this Linux worktree.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Mount the harness-restore tree and re-read :10762 numerals and :11338 verbatim; replace DESIGN-DEFAULT floors if the source disagrees."
    },
    {
      "claim": "Recovered prompt-two-slice.md:10762 is 'deadlock, escalation, replacement, owner-intervention', not the TST-0264 floor list.",
      "verdict": "PARTIAL",
      "settling_experiment": "Treat TST-0264 question_or_target as the on-tree attribution of the floor list until a fuller :10762 recovery exists."
    },
    {
      "claim": "CNL-0076 cadence (end-of-round vs end-of-turn) is not on this tree's catalog output_path; floors attach to whichever tick evaluates the expression.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Re-bind the floor gate to the CNL-0076 cadence constant once that artifact is on disk."
    }
  ],
  "produced_by": {
    "vendor": "grok",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "local-parallel"
  },
  "report": {
    "kind": "council-design-note",
    "title": "Minimum deliberation conditions that outrank any early stop",
    "question": "Which floors (minimum rounds, minimum independent briefs, minimum evidence) must hold before ANY stopping expression may fire, and what is the audit record when a floor blocks a satisfied stop condition?",
    "claim_under_test": "Floors are a hard precondition on FIRE, not a conjunct of the stopping expression. A true stop with unmet floors CONTINUES and records STOP-BLOCKED-BY-FLOOR naming each unmet floor. A spec with no max_rounds is rejected as a hang. CNL-0108 may later request an audited waiver; this unit does not grant a silent skip.",
    "fire_rule": "TERMINATE/FIRE iff stopping expression is true AND floors_unmet is empty. The expression is not rewritten to false; would_fire_without_floor stays true.",
    "floors": [
      {
        "id": "min_rounds",
        "hard_lower_bound": 1,
        "design_default": 2,
        "blocks_fire_when": "observed round < required min_rounds",
        "spec_quote": "minimum rounds",
        "numeral_status": "DESIGN-DEFAULT: recovered prompt slice at :10762 is 'deadlock, escalation, replacement, owner-intervention' not a numeral; TST-0264 attributes the floor list to :10762"
      },
      {
        "id": "min_independent_briefs",
        "hard_lower_bound": 1,
        "design_default": 2,
        "blocks_fire_when": "distinct opening speakers with non-identical non-empty text < required",
        "spec_quote": "independent opening positions submitted",
        "independence_rule": "unique speaker_id, non-empty text, text not byte-identical to an earlier opening brief"
      },
      {
        "id": "min_evidence_items",
        "hard_lower_bound": 1,
        "design_default": 1,
        "blocks_fire_when": "evidence nodes with both claim_id and locator < required",
        "spec_quote": "minimum evidence"
      },
      {
        "id": "mandated_roles_spoken",
        "hard_lower_bound": 1,
        "design_default": [
          "advocate",
          "critic"
        ],
        "blocks_fire_when": "any mandated role has no turn in the transcript",
        "spec_quote": "every mandated role having spoken"
      }
    ],
    "audit_when_floor_blocks": {
      "event": "STOP-BLOCKED-BY-FLOOR",
      "must_name_unmet_floors": true,
      "does_not_rewrite_expression": true,
      "record": {
        "event": "STOP-BLOCKED-BY-FLOOR",
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "action": "CONTINUE",
        "floors_unmet": [
          {
            "id": "min_rounds",
            "required": 2,
            "observed": 1
          },
          {
            "id": "min_independent_briefs",
            "required": 2,
            "observed": 0
          },
          {
            "id": "min_evidence_items",
            "required": 1,
            "observed": 0
          },
          {
            "id": "mandated_roles_spoken",
            "required": [
              "advocate",
              "critic"
            ],
            "observed": [],
            "missing": [
              "advocate",
              "critic"
            ]
          }
        ],
        "round": 1,
        "max_rounds": 12
      },
      "why_outside_the_expression": "AND-ing floors into the expression would report expression=false and hide that the stop condition was already satisfied. The question asks for the audit when a floor blocks a SATISFIED stop."
    },
    "ceiling": {
      "required_field": "max_rounds",
      "missing_is": "floor-with-no-ceiling rejected at validation, never honoured at runtime",
      "unmet_at_ceiling": "FLOOR-UNMET-AT-CEILING terminates; CONTINUE past max_rounds is a hang",
      "design_default": 12,
      "design_default_basis": "CNL-0010 tests_required phrases 'not discovered after 12 rounds' as the static-analysis horizon, not a recovered :10762 numeral",
      "hang_proof": {
        "bounded_max_rounds": 4,
        "iterations": 4,
        "hung": false,
        "reason": "FLOOR-UNMET-AT-CEILING"
      }
    },
    "cadence_residual": {
      "owned_by": "CNL-0076",
      "cnl_0076_artifact_present": false,
      "assumption": "This gate attaches to the same evaluation tick as the stopping expression and does not sample mid-turn on its own. If CNL-0076 later pins a different cadence, the floor moves with that tick."
    },
    "validation_rejects": [
      "min_rounds < 1 (TST-0264 floor bypass)",
      "max_rounds absent (hang)",
      "min_rounds > max_rounds",
      "min_independent_briefs > |speaking_roles| (unsatisfiable, hang)",
      "mandated_roles empty or not a subset of speaking_roles"
    ],
    "fixture_table": [
      {
        "id": "satisfied-but-floored",
        "action": "CONTINUE",
        "reason": "STOP-BLOCKED-BY-FLOOR",
        "unmet_ids": [
          "min_rounds",
          "min_independent_briefs",
          "min_evidence_items",
          "mandated_roles_spoken"
        ],
        "validation_errors": [],
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "audit": {
          "event": "STOP-BLOCKED-BY-FLOOR",
          "floors_unmet": [
            {
              "id": "min_rounds",
              "required": 2,
              "observed": 1
            },
            {
              "id": "min_independent_briefs",
              "required": 2,
              "observed": 0
            },
            {
              "id": "min_evidence_items",
              "required": 1,
              "observed": 0
            },
            {
              "id": "mandated_roles_spoken",
              "required": [
                "advocate",
                "critic"
              ],
              "observed": [],
              "missing": [
                "advocate",
                "critic"
              ]
            }
          ],
          "round": 1,
          "max_rounds": 12,
          "gate_enabled": true
        }
      },
      {
        "id": "floors-met-stop-true",
        "action": "TERMINATE",
        "reason": "FIRE",
        "unmet_ids": [],
        "validation_errors": [],
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "audit": {
          "event": "FIRE",
          "floors_unmet": [],
          "round": 2,
          "max_rounds": 12,
          "gate_enabled": true
        }
      },
      {
        "id": "stop-false-floors-unmet",
        "action": "CONTINUE",
        "reason": "SILENT",
        "unmet_ids": [
          "min_rounds",
          "min_independent_briefs",
          "min_evidence_items",
          "mandated_roles_spoken"
        ],
        "validation_errors": [],
        "stop_expression_true": false,
        "would_fire_without_floor": false,
        "audit": {
          "event": "SILENT",
          "floors_unmet": [
            {
              "id": "min_rounds",
              "required": 2,
              "observed": 1
            },
            {
              "id": "min_independent_briefs",
              "required": 2,
              "observed": 0
            },
            {
              "id": "min_evidence_items",
              "required": 1,
              "observed": 0
            },
            {
              "id": "mandated_roles_spoken",
              "required": [
                "advocate",
                "critic"
              ],
              "observed": [],
              "missing": [
                "advocate",
                "critic"
              ]
            }
          ],
          "round": 1,
          "max_rounds": 12,
          "gate_enabled": true
        }
      },
      {
        "id": "duplicate-briefs-not-independent",
        "action": "CONTINUE",
        "reason": "STOP-BLOCKED-BY-FLOOR",
        "unmet_ids": [
          "min_independent_briefs"
        ],
        "validation_errors": [],
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "audit": {
          "event": "STOP-BLOCKED-BY-FLOOR",
          "floors_unmet": [
            {
              "id": "min_independent_briefs",
              "required": 2,
              "observed": 1
            }
          ],
          "round": 2,
          "max_rounds": 12,
          "gate_enabled": true
        }
      },
      {
        "id": "min-rounds-zero",
        "action": "TERMINATE",
        "reason": "SPEC-INVALID",
        "unmet_ids": [],
        "validation_errors": [
          "min_rounds-below-hard-lower"
        ]
      },
      {
        "id": "no-ceiling",
        "action": "TERMINATE",
        "reason": "SPEC-INVALID",
        "unmet_ids": [],
        "validation_errors": [
          "floor-with-no-ceiling"
        ]
      },
      {
        "id": "unsatisfiable-briefs",
        "action": "TERMINATE",
        "reason": "SPEC-INVALID",
        "unmet_ids": [],
        "validation_errors": [
          "min_independent_briefs-unsatisfiable"
        ]
      }
    ],
    "satisfied_but_floored": {
      "id": "satisfied-but-floored",
      "action": "CONTINUE",
      "reason": "STOP-BLOCKED-BY-FLOOR",
      "unmet_ids": [
        "min_rounds",
        "min_independent_briefs",
        "min_evidence_items",
        "mandated_roles_spoken"
      ],
      "audit": {
        "action": "CONTINUE",
        "reason": "STOP-BLOCKED-BY-FLOOR",
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "floors_unmet": [
          {
            "id": "min_rounds",
            "required": 2,
            "observed": 1
          },
          {
            "id": "min_independent_briefs",
            "required": 2,
            "observed": 0
          },
          {
            "id": "min_evidence_items",
            "required": 1,
            "observed": 0
          },
          {
            "id": "mandated_roles_spoken",
            "required": [
              "advocate",
              "critic"
            ],
            "observed": [],
            "missing": [
              "advocate",
              "critic"
            ]
          }
        ],
        "validation_errors": [],
        "round": 1,
        "max_rounds": 12,
        "gate_enabled": true,
        "event": "STOP-BLOCKED-BY-FLOOR"
      }
    },
    "negative_controls": [
      {
        "id": "NC-ungated-premature-stop",
        "rejects": "satisfied stop that TERMINATES while floors are unmet (FC-11338)",
        "observed": "gate_enabled=false action=TERMINATE reason=PREMATURE-STOP; gate_enabled=true action=CONTINUE reason=STOP-BLOCKED-BY-FLOOR"
      },
      {
        "id": "NC-hang-mutant",
        "rejects": "CONTINUE past hang_guard when max_rounds is raised past the guard",
        "observed": "probe2 mutant-no-effective-ceiling hung=true terminated=false"
      }
    ],
    "reviewer": {
      "reviewer_id": "CNL-0077-probe2-independent-kernel-recount",
      "verdict": "PASS",
      "independent": true,
      "method": "re-tabulate floors_unmet from fixtures/satisfied-but-floored.json; disagree with the artifact table blocks the unit",
      "counterexample_instance": "fixtures/satisfied-but-floored.json with gate_enabled=false terminates PREMATURE-STOP (FC-11338). The gated kernel blocks that instance.",
      "refuted_not_attempted": false
    },
    "source_availability": {
      "requested_paths_present": false,
      "requested_paths": {
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": false,
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": false,
        "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false
      },
      "on_tree_proxies": [
        "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
        "command-center/WORK-UNIT-CATALOG.json"
      ]
    },
    "dependency_cnl_0076": {
      "required_by_catalog": true,
      "artifact_present": false,
      "residual": "evaluation cadence, purity, and flap semantics are CNL-0076's; floors attach to the same tick"
    },
    "strongest_surviving_counterargument": "A live-war-room preset (CNL-0108) may need to act before independent briefs exist. This unit refuses a silent skip: any waiver must be a first-class FLOOR-WAIVED-BY-PRESET audit event with owner_approval_required. CNL-0108 decides whether that waiver exists; until it does, floors outrank every expression including emergency ones.",
    "live": {
      "floored": {
        "action": "CONTINUE",
        "reason": "STOP-BLOCKED-BY-FLOOR",
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "floors_unmet": [
          {
            "id": "min_rounds",
            "required": 2,
            "observed": 1
          },
          {
            "id": "min_independent_briefs",
            "required": 2,
            "observed": 0
          },
          {
            "id": "min_evidence_items",
            "required": 1,
            "observed": 0
          },
          {
            "id": "mandated_roles_spoken",
            "required": [
              "advocate",
              "critic"
            ],
            "observed": [],
            "missing": [
              "advocate",
              "critic"
            ]
          }
        ],
        "validation_errors": [],
        "round": 1,
        "max_rounds": 12,
        "gate_enabled": true,
        "event": "STOP-BLOCKED-BY-FLOOR"
      },
      "ungated": {
        "action": "TERMINATE",
        "reason": "PREMATURE-STOP",
        "stop_expression_true": true,
        "would_fire_without_floor": true,
        "floors_unmet": [
          {
            "id": "min_rounds",
            "required": 2,
            "observed": 1
          },
          {
            "id": "min_independent_briefs",
            "required": 2,
            "observed": 0
          },
          {
            "id": "min_evidence_items",
            "required": 1,
            "observed": 0
          },
          {
            "id": "mandated_roles_spoken",
            "required": [
              "advocate",
              "critic"
            ],
            "observed": [],
            "missing": [
              "advocate",
              "critic"
            ]
          }
        ],
        "validation_errors": [],
        "round": 1,
        "max_rounds": 12,
        "gate_enabled": false,
        "event": "PREMATURE-STOP"
      },
      "bounded": {
        "iterations": 4,
        "hung": false,
        "reason": "FLOOR-UNMET-AT-CEILING"
      }
    },
    "observations": [
      {
        "name": "satisfied-but-floored-action",
        "measured": "CONTINUE",
        "method": "floor.evaluate on fixtures/satisfied-but-floored.json",
        "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json"
      },
      {
        "name": "satisfied-but-floored-reason",
        "measured": "STOP-BLOCKED-BY-FLOOR",
        "method": "floor.evaluate on fixtures/satisfied-but-floored.json",
        "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json"
      },
      {
        "name": "ungated-premature-stop-reason",
        "measured": "PREMATURE-STOP",
        "method": "floor.evaluate gate_enabled=false",
        "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/satisfied-but-floored.json"
      },
      {
        "name": "no-ceiling-validation",
        "measured": true,
        "method": "floor.validate_spec on fixtures/no-ceiling.json",
        "anchor": "command-center/p2-wave/probes/CNL-0077/fixtures/no-ceiling.json"
      }
    ],
    "control_ids": [
      "NC-ungated-premature-stop",
      "NC-hang-mutant"
    ]
  }
}
