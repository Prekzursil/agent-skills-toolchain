{
  "unit_id": "CNL-0106",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0106",
  "id": "council.preset.code-review-tribunal.executable-oracle",
  "title": "Code-review tribunal backed by an executable oracle",
  "family": "ENGINEERING-REVIEW",
  "anonymity": false,
  "rebuttal": false,
  "extends": [
    {
      "id": "P46",
      "kind": "protocol",
      "relation": "extends",
      "note": "Catalog-cited architecture-review-board (CNL-0045). Same four review voices and majority vote; this preset adds a bound executable oracle as a gate after the vote."
    },
    {
      "id": "C-cited:P46-architecture-review-board",
      "kind": "preset",
      "relation": "extends"
    },
    {
      "id": "CNL-0068",
      "kind": "mechanism",
      "relation": "realizes",
      "note": "Evidence outranks popularity: one bound failing test overturns a unanimous YES. Converse: an unbound failing test cannot veto."
    },
    {
      "id": "council.preset.catalog-class.editable",
      "kind": "catalog-class",
      "relation": "extends",
      "note": "ARC-0003 transcribed catalog-class.editable four-voice base."
    }
  ],
  "roles": [
    {
      "id": "Architect",
      "title": "Architect",
      "voting": true
    },
    {
      "id": "Skeptic",
      "title": "Skeptic",
      "voting": true
    },
    {
      "id": "Pragmatist",
      "title": "Pragmatist",
      "voting": true
    },
    {
      "id": "Critic",
      "title": "Critic",
      "voting": true
    },
    {
      "id": "TestBinder",
      "title": "Test binder",
      "voting": false,
      "bind_oracle": true,
      "seated_when": "always",
      "note": "Declares load-bearing commands BEFORE round 1. Reviewers cannot add bindings mid-flight to manufacture a veto."
    },
    {
      "id": "EvidenceClerk",
      "title": "Evidence clerk",
      "voting": false,
      "seated_when": "oracle-challenge",
      "note": "Seated only when the disputed artifact is the test."
    }
  ],
  "protocol_schedule": [
    {
      "id": "bind-oracle",
      "purpose": "TestBinder records load-bearing commands before talk"
    },
    {
      "id": "P46",
      "purpose": "architecture/code review board; majority vote is an exhibit"
    },
    {
      "id": "oracle-gate",
      "purpose": "bound FAIL overrides majority; unbound FAIL is void"
    },
    {
      "id": "P50",
      "purpose": "evidence-clerk path when subject_kind=test or challenge filed",
      "optional": true
    }
  ],
  "voting": {
    "rule": "majority",
    "quorum": 3,
    "on_tie": "NOT-YES",
    "note": "Same majority rule as P46. The oracle is not a fifth vote; it is a gate on the recorded outcome."
  },
  "stopping": {
    "max_rounds": 6,
    "expression": "bound_oracle_fail\u2192NOT-YES || max_rounds<=6 && unresolved\u2192BLOCKED",
    "on_timeout": "halt",
    "on_oracle_fail": "NOT-YES",
    "on_unresolved": "BLOCKED"
  },
  "oracle": {
    "kind": "executable-command",
    "fail_overrides_majority": true,
    "unbound_fail_cannot_veto": true,
    "disputed_test_demotes_oracle_to_exhibit": true,
    "binder_role": "TestBinder",
    "load_bearing_declared_before_deliberation": true,
    "inconclusive_blocks_yes": true
  },
  "default_binding": {
    "base_spec_ref": "CouncilSpec.v2",
    "base_spec_version": "catalog-cited-absent-on-this-worktree",
    "protocol": "P46"
  },
  "editable_dials": [
    "stopping.max_rounds",
    "voting.quorum",
    "oracle_binding.load_bearing_commands"
  ],
  "locked_dials": [
    "oracle.fail_overrides_majority",
    "oracle.unbound_fail_cannot_veto",
    "oracle.disputed_test_demotes_oracle_to_exhibit",
    "oracle.load_bearing_declared_before_deliberation",
    "voting.rule"
  ],
  "anti_failure": {
    "on_split": "surface-disagreement",
    "no_silent_average": true,
    "name_only_duplicate_forbidden": true
  },
  "audit": {
    "persist_transcript": true,
    "hash_inputs": true,
    "record_vote_separately_from_outcome": true
  },
  "nearest_sibling": {
    "id": "C-cited:P46-architecture-review-board",
    "source": "catalog-cited reconstruction on this worktree; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json Path.is_file() is false",
    "named_explicitly": true,
    "distance": 3.0833333333333335,
    "ranked": [
      {
        "id": "C-cited:P46-architecture-review-board",
        "distance": 3.0833333333333335
      },
      {
        "id": "C-cited:P51-timeboxed-spike-council",
        "distance": 3.5
      },
      {
        "id": "C-cited:P50-evidence-clerk-led",
        "distance": 4.25
      },
      {
        "id": "council.preset.catalog-class.editable",
        "distance": 4.333333333333334
      },
      {
        "id": "C-cited:P45-scientific-peer-review",
        "distance": 7.0
      }
    ],
    "measurable_diffs": [
      {
        "field": "roles",
        "preset": [
          "Architect",
          "Critic",
          "EvidenceClerk",
          "Pragmatist",
          "Skeptic",
          "TestBinder"
        ],
        "sibling": [
          "Architect",
          "Critic",
          "Pragmatist",
          "Skeptic"
        ]
      },
      {
        "field": "protocols",
        "preset": [
          "P46",
          "P50",
          "bind-oracle",
          "oracle-gate"
        ],
        "sibling": [
          "P46"
        ]
      },
      {
        "field": "stopping_expression",
        "preset": "bound_oracle_fail\u2192NOT-YES || max_rounds<=6 && unresolved\u2192BLOCKED",
        "sibling": "max_rounds<=8 && unresolved\u2192BLOCKED"
      },
      {
        "field": "max_rounds",
        "preset": 6,
        "sibling": 8
      },
      {
        "field": "fail_overrides_majority",
        "preset": true,
        "sibling": false
      }
    ],
    "library_file_on_this_worktree": false,
    "library_path_catalogued": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "reconstruction_basis": "WORK-UNIT-CATALOG.json CNL-0045 names P45\u2013P51 (P46 architecture-review-board). ARC-0003 transcribes council.preset.catalog-class.editable. This unit does not claim a byte copy of the absent 72-preset library."
  },
  "question": "This is the one review preset with a real oracle - how does a failing test override a majority of reviewer opinion, and what happens when the test itself is the disputed artifact?",
  "answers": {
    "how_failing_test_overrides_majority": "The vote is an exhibit, not the recorded outcome. After TestBinder declares load-bearing commands in bind-oracle (before round 1), a bound command that reports FAIL forces outcome=NOT-YES even when every voting seat ballots YES. The majority is persisted as vote=YES so the override is auditable. Reviewers cannot add bindings mid-flight. oracle.fail_overrides_majority is a locked dial.",
    "when_the_test_is_the_disputed_artifact": "If subject_kind=test or a seated reviewer files oracle_challenge, the oracle is demoted from gate to exhibit. FAIL does not override. EvidenceClerk is seated and P50 is inserted. Clerk CONFIRMED-LOAD-BEARING restores the gate (FAIL \u2192 NOT-YES). Clerk REJECTED-AS-ORACLE (flake, wrong subject, tautology) voids the oracle and the vote stands. Unresolved clerk work records ORACLE-CHALLENGE, never YES.",
    "who_may_declare_a_test_load_bearing": "Only TestBinder, and only before deliberation. That is the CNL-0068 converse: an irrelevant failing test cannot veto."
  },
  "instantiations": {
    "code_subject": {
      "task_id": "fixture.code-review.pr-1042",
      "subject_kind": "code",
      "roster": [
        {
          "role_id": "Architect",
          "title": "Architect",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Skeptic",
          "title": "Skeptic",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Pragmatist",
          "title": "Pragmatist",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Critic",
          "title": "Critic",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "TestBinder",
          "title": "Test binder",
          "voting": false,
          "bind_oracle": true
        }
      ],
      "voting_seats": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "protocol_schedule": [
        {
          "id": "bind-oracle",
          "purpose": "declare load-bearing commands before talk"
        },
        {
          "id": "P46",
          "purpose": "architecture/code review board deliberation"
        },
        {
          "id": "tribunal-vote",
          "purpose": "majority of voting seats, recorded as exhibit"
        },
        {
          "id": "oracle-gate",
          "purpose": "bound FAIL overrides majority; unbound FAIL is void"
        },
        {
          "id": "record",
          "purpose": "persist transcript, vote, oracle, outcome"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 3,
        "on_tie": "NOT-YES",
        "note": "Same majority rule as P46. The oracle is not a fifth vote; it is a gate on the recorded outcome."
      },
      "stopping": {
        "max_rounds": 6,
        "expression": "bound_oracle_fail\u2192NOT-YES || max_rounds<=6 && unresolved\u2192BLOCKED",
        "on_timeout": "halt",
        "on_oracle_fail": "NOT-YES",
        "on_unresolved": "BLOCKED"
      },
      "oracle": {
        "kind": "executable-command",
        "fail_overrides_majority": true,
        "unbound_fail_cannot_veto": true,
        "disputed_test_demotes_oracle_to_exhibit": true,
        "binder_role": "TestBinder",
        "load_bearing_declared_before_deliberation": true,
        "inconclusive_blocks_yes": true
      },
      "oracle_binding": {
        "load_bearing_commands": [
          "pytest tests/test_parser.py -q"
        ],
        "binder": "TestBinder"
      }
    },
    "test_subject": {
      "task_id": "fixture.code-review.disputed-test",
      "subject_kind": "test",
      "roster": [
        {
          "role_id": "Architect",
          "title": "Architect",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Skeptic",
          "title": "Skeptic",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Pragmatist",
          "title": "Pragmatist",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "Critic",
          "title": "Critic",
          "voting": true,
          "bind_oracle": false
        },
        {
          "role_id": "TestBinder",
          "title": "Test binder",
          "voting": false,
          "bind_oracle": true
        },
        {
          "role_id": "EvidenceClerk",
          "title": "Evidence clerk",
          "voting": false,
          "bind_oracle": false
        }
      ],
      "voting_seats": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "protocol_schedule": [
        {
          "id": "bind-oracle",
          "purpose": "declare load-bearing commands before talk"
        },
        {
          "id": "P46",
          "purpose": "independent review of the disputed test as artifact"
        },
        {
          "id": "P50",
          "purpose": "evidence-clerk examines flake vs wrong-subject vs tautology"
        },
        {
          "id": "tribunal-vote",
          "purpose": "majority of voting seats, recorded as exhibit"
        },
        {
          "id": "oracle-challenge-gate",
          "purpose": "FAIL does not override until clerk confirms load-bearing"
        },
        {
          "id": "record",
          "purpose": "persist transcript, vote, clerk verdict, outcome"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 3,
        "on_tie": "NOT-YES",
        "note": "Same majority rule as P46. The oracle is not a fifth vote; it is a gate on the recorded outcome."
      },
      "stopping": {
        "max_rounds": 6,
        "expression": "subject=test \u2192 oracle_fail does not halt as NOT-YES; P50 clerk must confirm or reject; unresolved \u2192 ORACLE-CHALLENGE",
        "on_timeout": "halt",
        "on_oracle_fail": "ORACLE-CHALLENGE",
        "on_unresolved": "BLOCKED"
      },
      "oracle": {
        "kind": "executable-command",
        "fail_overrides_majority": true,
        "unbound_fail_cannot_veto": true,
        "disputed_test_demotes_oracle_to_exhibit": true,
        "binder_role": "TestBinder",
        "load_bearing_declared_before_deliberation": true,
        "inconclusive_blocks_yes": true
      },
      "oracle_binding": {
        "load_bearing_commands": [
          "pytest tests/test_parser.py -q"
        ],
        "binder": "TestBinder"
      }
    }
  },
  "oracle_cases": {
    "majority_yes_bound_fail": {
      "outcome": "NOT-YES",
      "vote": "YES",
      "oracle_role": "gate",
      "bound": true,
      "reason": "bound FAIL overrides majority including unanimous YES"
    },
    "majority_yes_unbound_fail": {
      "outcome": "YES",
      "vote": "YES",
      "oracle_role": "void-unbound",
      "bound": false,
      "reason": "unbound command cannot veto or confirm; CNL-0068 converse (irrelevant failing test must not veto a sound decision)"
    },
    "test_subject_bound_fail_no_clerk": {
      "outcome": "ORACLE-CHALLENGE",
      "vote": "YES",
      "oracle_role": "exhibit",
      "bound": true,
      "reason": "subject_kind=test or oracle_challenge filed: FAIL does not override until evidence-clerk (P50) confirms load-bearing"
    },
    "test_subject_clerk_confirms_fail": {
      "outcome": "NOT-YES",
      "vote": "YES",
      "oracle_role": "gate-after-clerk",
      "bound": true,
      "reason": "clerk confirmed the disputed test as load-bearing; bound FAIL overrides majority"
    },
    "test_subject_clerk_rejects": {
      "outcome": "YES",
      "vote": "YES",
      "oracle_role": "void-rejected",
      "bound": true,
      "reason": "clerk rejected the test as oracle (flake, wrong subject, or tautology); vote stands"
    },
    "majority_yes_bound_pass": {
      "outcome": "YES",
      "vote": "YES",
      "oracle_role": "gate",
      "bound": true,
      "reason": "bound PASS; vote stands"
    }
  },
  "negative_control": {
    "rejected_state": "council records outcome=YES after unanimous YES ballots while a bound load-bearing command reports FAIL",
    "check_does": "adjudicate(...) returns outcome=NOT-YES with oracle_role=gate; the YES vote remains in the vote field and is not copied to outcome",
    "observed_outcome": "NOT-YES"
  },
  "library_disclosure": {
    "12_COUNCIL_PROTOCOLS_AND_PRESETS_json": false,
    "11_COUNCIL_SPECIFICATION_schema_json": false,
    "honest_limit": "Nearest sibling is named from catalog-cited P46, not from a live parse of the 72-record library. If that file lands, re-run nearest_sibling over its presets; a closer C-id replaces C-cited:P46-architecture-review-board."
  },
  "schema_validation": {
    "catalog_output_schema": "command-center/schema/council-preset.schema.json",
    "catalog_schema_is_ref_shim": true,
    "executable_schema": "command-center/p2-wave/probes/CNL-0106/council-preset.schema.json",
    "validator": "jsonschema.Draft202012Validator",
    "draft": "2020-12"
  },
  "tests": [
    {
      "id": "instantiate-code",
      "result": "PASS",
      "roster": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "schedule": [
        "bind-oracle",
        "P46",
        "tribunal-vote",
        "oracle-gate",
        "record"
      ]
    },
    {
      "id": "instantiate-test-differs",
      "result": "PASS",
      "roster": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "schedule": [
        "bind-oracle",
        "P46",
        "P50",
        "tribunal-vote",
        "oracle-challenge-gate",
        "record"
      ]
    },
    {
      "id": "nearest-sibling-P46",
      "result": "PASS",
      "sibling": "C-cited:P46-architecture-review-board",
      "distance": 3.0833333333333335
    }
  ]
}
