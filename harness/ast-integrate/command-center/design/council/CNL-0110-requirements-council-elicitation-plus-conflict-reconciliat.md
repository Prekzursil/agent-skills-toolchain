{
  "answers": {
    "how_separated": "Two protocol steps with different voting and stopping. p-elicit records attributed wants under record-only voting and stops when every required stakeholder class has a want. p-reconcile then classifies each contradicting pair under pairwise-originator-conjunction and must not run until elicit has a ledger. Aggregation is forbidden in elicit; blending is forbidden in reconcile.",
    "unreconcilable_pair_outcome": "irreducible-disagreement",
    "why_not_blend": "A blended requirement claims both wants are satisfied while no world-state satisfies both satisfaction conditions. That hides the conflict. The pair stays two wants plus an irreducible-disagreement record citing failed rewrite attempts and zero remaining untried rewrites (CNL-0071 information-gain gate)."
  },
  "instantiation": {
    "elicit_complete": true,
    "pair_outcomes": [
      {
        "attempts": [
          {
            "accepted": false,
            "rewrite_id": "R-plaintext-promise"
          }
        ],
        "information_gain_positive": false,
        "kind": "irreducible-disagreement",
        "originators": [
          "constraint-bearer",
          "operator"
        ],
        "outcome_type": "irreducible-disagreement",
        "pair": [
          "W-plain",
          "W-erase"
        ],
        "pair_key": [
          "W-erase",
          "W-plain"
        ],
        "rewrite": null
      },
      {
        "attempts": [
          {
            "accepted": true,
            "rewrite_id": "R-ship-with-tests"
          }
        ],
        "information_gain_positive": false,
        "kind": "reconciled",
        "originators": [
          "affected-party",
          "owner"
        ],
        "outcome_type": "decision",
        "pair": [
          "W-fast",
          "W-tests"
        ],
        "pair_key": [
          "W-fast",
          "W-tests"
        ],
        "rewrite": "Ship this quarter with the auth-failure regression test as a release gate."
      }
    ],
    "protocol_schedule": [
      "p-elicit",
      "p-reconcile"
    ],
    "roster": [
      {
        "class": "operator",
        "id": "ops-1",
        "role": "operator"
      },
      {
        "class": "owner",
        "id": "own-1",
        "role": "owner"
      },
      {
        "class": "implementer",
        "id": "imp-1",
        "role": "implementer"
      },
      {
        "class": "affected-party",
        "id": "usr-1",
        "role": "affected-party"
      },
      {
        "class": "constraint-bearer",
        "id": "leg-1",
        "role": "constraint-bearer"
      }
    ],
    "stopping": {
      "elicit": "each required class has >=1 attributed want",
      "reconcile": "each contradicting pair is reconciled|deferred-conditional|irreducible-disagreement"
    },
    "task_id": "task.api-token-storage",
    "voting": {
      "elicit": "record-only",
      "reconcile": "pairwise-originator-conjunction"
    },
    "want_ledger": [
      {
        "class": "operator",
        "conflicts_with": [
          "W-erase"
        ],
        "id": "W-plain",
        "phase": "p-elicit",
        "statement": "Keep tokens in plaintext so on-call can debug auth failures without a key ceremony."
      },
      {
        "class": "constraint-bearer",
        "conflicts_with": [
          "W-plain"
        ],
        "id": "W-erase",
        "phase": "p-elicit",
        "statement": "Tokens must be erasable on user request (GDPR storage limitation)."
      },
      {
        "class": "owner",
        "conflicts_with": [
          "W-tests"
        ],
        "id": "W-fast",
        "phase": "p-elicit",
        "statement": "Ship a working CLI this quarter."
      },
      {
        "class": "affected-party",
        "conflicts_with": [
          "W-fast"
        ],
        "id": "W-tests",
        "phase": "p-elicit",
        "statement": "Auth failures must have a regression test before ship."
      },
      {
        "class": "implementer",
        "conflicts_with": [],
        "id": "W-simple",
        "phase": "p-elicit",
        "statement": "Avoid a KMS dependency in v1."
      }
    ]
  },
  "kind": "council_preset_design",
  "library_status": {
    "glob_hits": [],
    "search_paths": [
      "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ],
    "search_space_note": "Library file absent at the three well-known paths. Nearest 12-COUNCIL sibling is computed over the on-disk transcription of council.preset.catalog-class.editable (ARC-0003 samples.json), not over the missing 72-record file, and not over other units' probe fixtures that reuse the library filename. This cannot prove uniqueness among the unread 72.",
    "twelve_council_present": false
  },
  "maps_c_ids": [
    {
      "c_id": "C13",
      "mechanism": "CNL-0102 reconstruction: requirements-elicitation arm (P23/P01/P22, approval, stakeholder_coverage stop). This preset keeps capture as its own protocol step but replaces approval with record-only voting so elicitation cannot smuggle reconciliation.",
      "relation": "extends"
    },
    {
      "c_id": "C14",
      "mechanism": "CNL-0102 reconstruction: requirements-conflict-reconciliation arm (P12/P09/P56, consent, unreconciled_pairs stop). This preset keeps pair classification as a second step, binds pairwise-originator-conjunction instead of consent, and emits irreducible-disagreement rather than blending.",
      "relation": "extends"
    },
    {
      "c_id": "CNL-0017",
      "mechanism": "Seats one of each required stakeholder class and blocks elicit when any required class is missing. CNL-0017 artifact is absent; this is an operational taxonomy for this preset.",
      "relation": "operationalizes"
    },
    {
      "c_id": "CNL-0071",
      "mechanism": "Unreconcilable pairs emit irreducible-disagreement only after every listed rewrite was tried and rejected by an originator class. Declaring irreducibility while untried rewrites remain is incomplete, not irreducible. CNL-0071 artifact is absent.",
      "relation": "operationalizes"
    },
    {
      "c_id": "CNL-0101",
      "mechanism": "Preset is a typed delta (roles, protocol_schedule, voting, stopping, anti_failure, audit, outcomes) plus editable_dials and default_binding. On base bump: migrate or list unmigratable dials. CNL-0101 artifact is absent.",
      "relation": "operationalizes"
    }
  ],
  "nearest_sibling": {
    "axes_differ": [
      "role_set",
      "protocol_schedule",
      "elicit_voting_rule",
      "reconcile_voting_rule",
      "elicit_stop",
      "reconcile_stop",
      "phase_split",
      "unreconcilable_outcome",
      "balance_metric"
    ],
    "closer_non_library": {
      "axes_differ": [
        "role_set",
        "protocol_schedule",
        "elicit_voting_rule",
        "reconcile_voting_rule",
        "elicit_stop",
        "reconcile_stop",
        "phase_split",
        "unreconcilable_outcome",
        "balance_metric"
      ],
      "axes_same": [],
      "distance": 9,
      "id": "C13",
      "planted_duplicate": false,
      "source": "CNL-0102-catalog-cited-reconstruction:requirements-elicitation",
      "twelve_council_sourced": false
    },
    "distance": 9,
    "named": "council.preset.catalog-class.editable",
    "planted_name_clone_distance": 0,
    "search_space": "on-disk-transcription-not-the-unread-72",
    "source": "12-COUNCIL-transcription:ARC-0003/samples.json"
  },
  "negative_control": {
    "known_irreducible_fires": false,
    "on_state": "collapsing W-plain and W-erase into one requirement that claims both plaintext persistence and erasability",
    "planted_blend_fires": true,
    "rejects": "blended-requirement for a contradicting pair",
    "verbatim": "FIRES when pair_outcome.kind == 'blended-requirement'; SILENT when kind is 'irreducible-disagreement' or 'reconciled'."
  },
  "preset": {
    "base_spec": {
      "id": "councilspec.v2",
      "note": "CNL-0101 artifact and 11-COUNCIL-SPECIFICATION.schema.json are absent on this worktree. This preset is a typed delta over the axes catalog-cited for every 12-COUNCIL record (anti_failure/audit/voting/consensus/stopping) plus roles and a two-step protocol_schedule. It is not a fork of a copied spec.",
      "version_pin": "unpinned-library-absent"
    },
    "default_binding": {
      "delta.roles": [
        "operator",
        "owner",
        "implementer",
        "affected-party",
        "constraint-bearer"
      ],
      "stopping.elicit.max_rounds": 2,
      "stopping.reconcile.max_rounds": 3
    },
    "delta": {
      "anti_failure": {
        "no_blend_of_contradicting_wants": true,
        "no_silent_average": true,
        "on_split": "surface-disagreement",
        "underfilled_class_blocks_elicit": true
      },
      "audit": {
        "hash_inputs": true,
        "pair_outcomes_must_cite_attempts": true,
        "persist_transcript": true,
        "want_ledger_append_only": true
      },
      "balance_metric": {
        "fail_when": "any required class has count == 0",
        "id": "required-class-coverage",
        "note": "Shannon-style diversity is refused: it can pass with one token member of a class. Coverage of each required class is the dispute-resistant metric used here (operationalizes CNL-0017; CNL-0017 artifact is absent).",
        "pass_when": "min(count per required class) >= 1",
        "required_classes": [
          "operator",
          "owner",
          "implementer",
          "affected-party",
          "constraint-bearer"
        ],
        "threshold_declared_before_score": true
      },
      "consensus": {
        "local_completion_forbidden": true,
        "reducer": "pairwise-originator-conjunction"
      },
      "outcomes": {
        "council_compound": "decision-or-conditional-decision over reconciled pairs, plus irreducible-disagreement annex for unreconcilable pairs",
        "reconciled_pair": "decision",
        "unreconcilable_pair": "irreducible-disagreement",
        "untried_pair": "incomplete"
      },
      "phases": {
        "elicit": {
          "aggregates_wants": false,
          "id": "p-elicit",
          "purpose": "surface attributed wants; do not aggregate them"
        },
        "reconcile": {
          "id": "p-reconcile",
          "information_gain_gate": true,
          "purpose": "classify each contradicting pair; never blend"
        }
      },
      "protocol_schedule": [
        "p-elicit",
        "p-reconcile"
      ],
      "roles": [
        "operator",
        "owner",
        "implementer",
        "affected-party",
        "constraint-bearer"
      ],
      "stopping": {
        "elicit": {
          "done_when": "each required class has >=1 attributed want",
          "max_rounds": 2,
          "on_timeout": "halt-incomplete-ledger"
        },
        "reconcile": {
          "done_when": "each contradicting pair is reconciled|deferred-conditional|irreducible-disagreement",
          "irreducible_requires_zero_information_gain": true,
          "max_rounds": 3,
          "on_timeout": "halt-unclassified-pairs-are-not-irreducible"
        }
      },
      "voting": {
        "elicit": {
          "note": "elicitation has no vote; a vote here would smuggle reconciliation into capture",
          "quorum": 0,
          "rule": "record-only"
        },
        "reconcile": {
          "note": "a rewrite of pair (A,B) is accepted only if both originating stakeholder classes accept it. Majority and ranked-choice are refused: wants are not mutually exclusive options (CNL-0109 trap).",
          "quorum": 2,
          "rule": "pairwise-originator-conjunction"
        }
      }
    },
    "editable_dials": [
      "stopping.elicit.max_rounds",
      "stopping.reconcile.max_rounds",
      "delta.roles"
    ],
    "extends_c_ids": [
      "C13",
      "C14"
    ],
    "extends_c_ids_basis": "WORK-UNIT-CATALOG CNL-0110 plus CNL-0102 named family presets: C13 requirements-elicitation (P23/P01/P22, approval) and C14 requirements-conflict-reconciliation (P12/P09/P56, consent). This preset composes the two arms into one two-phase schedule with phase-local voting. Library bytes were not read.",
    "id": "council.preset.requirements.elicit-then-reconcile",
    "kind": "council_preset",
    "on_base_version_bump": "migrate every bound dial or list the dials that cannot migrate; silent override of a non-editable dial is REJECTED (CNL-0101 test).",
    "title": "Requirements council: elicit wants, then reconcile contradictions"
  },
  "produced_at": "2026-08-25T00:57:19Z",
  "question": "How does the preset separate eliciting what stakeholders want from reconciling requirements that contradict - and what outcome type does an unreconcilable pair produce?",
  "residual_unknowns": [
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; nearest-sibling is among transcribed/reconstructed rows, not the 72-record library.",
    "The 20 preset keys cited by CNL-0101 were not re-enumerated from the library. This preset binds the catalog-cited axes plus roles/protocol_schedule/editable_dials/default_binding.",
    "Dependencies CNL-0101, CNL-0017, CNL-0071 have no delivered artifacts on this worktree; mappings operationalize their catalog questions, they do not consume their outputs.",
    "Preset id council.preset.requirements.elicit-then-reconcile extends reconstructed C13+C14; it does not supersede a named 12-COUNCIL library row because those bytes were not readable here. If the 72-record file lands, recompute PROFILE_AXES distance against every preset and replace nearest_sibling if a closer neighbour exists."
  ],
  "reviewer": {
    "independent": true,
    "reviewer_id": "CNL-0110-probe2-sibling-differential",
    "scope": "Recomputes Hamming distance over PROFILE_AXES against the on-disk sibling catalog; does not accept nearest_sibling.named without recomputation.",
    "verdict": "PASS"
  },
  "schema_validation": {
    "affected_error_count": 0,
    "invalid_record_error_count": 3,
    "schema": "command-center/p2-wave/probes/CNL-0110/artifact.schema.json",
    "vacuous": false,
    "validator": "jsonschema.Draft202012Validator"
  },
  "sentinel": "SUCCESS:CNL-0110",
  "state": "SUCCESS",
  "tests": [
    {
      "id": "instantiate-fixture",
      "result": "PASS"
    },
    {
      "id": "nearest-sibling-differential",
      "result": "PASS"
    },
    {
      "id": "schema-draft202012",
      "result": "PASS"
    },
    {
      "id": "negative-control-blend",
      "result": "PASS"
    }
  ],
  "title": "Requirements council: elicitation plus conflict reconciliation",
  "unit_id": "CNL-0110"
}
