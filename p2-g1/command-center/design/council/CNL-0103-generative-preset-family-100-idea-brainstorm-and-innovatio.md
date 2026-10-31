{
  "schema_version": 1,
  "unit_id": "CNL-0103",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0103",
  "spec_anchor": "_USER-PROMPTS.md:10746-10767",
  "min_bytes_threshold": 1024,
  "profile": "council-preset",
  "produced_by": {
    "vendor": "xai",
    "model": "grok-4.6",
    "role": "council-preset-designer",
    "execution_substrate": "local-parallel"
  },
  "artifacts": [
    {
      "path": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json",
      "bytes": 9290,
      "sha256": "2b047ee1a054c86fba57c8ddc0f380a864448eaeb5a1ec1767583c63d09bf428",
      "exists": true,
      "eol": "LF",
      "role": "fixture"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0103/fixtures/sibling_library.json",
      "bytes": 10044,
      "sha256": "19ce98fe32466253db81eea7417b445ee9093351e863379b34e7030dffc2fc78",
      "exists": true,
      "eol": "LF",
      "role": "fixture"
    },
    {
      "path": "command-center/schema/council-preset.schema.json",
      "bytes": 1131,
      "sha256": "a8b4ac701820d00175357a93ce867469d2b57430c101178cb7769b99f6888edd",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0103/fixtures/preset.record.schema.json",
      "bytes": 3815,
      "sha256": "67f98b5c62bcb7f5cfe788d33d0ec24adca1156873c462f9c2c5231d0fdbf5f6",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    }
  ],
  "evidence": [
    {
      "claim": "C-G26-100-idea-brainstorm and C-G29-innovation-moonshot instantiate to different roster/schedule/vote/stop/novelty-feasibility profiles; nearest sibling is C-G26-thin.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json",
      "probes": [
        {
          "role": "source",
          "method": "test-run",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe1_instantiate_and_sibling.py",
          "raw_output": "brainstorm=C-G26-100-idea-brainstorm moonshot=C-G29-innovation-moonshot sib=C-G26-thin dist=11 clone_rejected=True gaming_unique=10 genuine_unique=100",
          "fingerprint": "3cffecc6c318da7936c9c2f83f2e8e37",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "schema-validate",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py",
          "raw_output": "preset_error_count=0 invalid_n=15 envelope validated after write",
          "fingerprint": "6dba042b0ba1c37bb14bba0ca38f198a",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "Draft202012Validator reports 0 errors on both family typed-delta records and 15 errors on the planted invalid preset that omits weighting.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/preset.record.schema.json",
      "probes": [
        {
          "role": "source",
          "method": "test-run",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe1_instantiate_and_sibling.py",
          "raw_output": "brainstorm=C-G26-100-idea-brainstorm moonshot=C-G29-innovation-moonshot sib=C-G26-thin dist=11 clone_rejected=True gaming_unique=10 genuine_unique=100",
          "fingerprint": "3cffecc6c318da7936c9c2f83f2e8e37",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "schema-validate",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py",
          "raw_output": "preset_error_count=0 invalid_n=15 envelope validated after write",
          "fingerprint": "6dba042b0ba1c37bb14bba0ca38f198a",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "instantiate-roster-schedule-vote-stop",
      "name": "instantiate family against fixture task",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe1_instantiate_and_sibling.py",
      "result": "PASS",
      "assertions": 8
    },
    {
      "id": "nearest-sibling-named-differential",
      "name": "nearest sibling named; distance >= 1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe1_instantiate_and_sibling.py",
      "result": "PASS",
      "assertions": 2
    },
    {
      "id": "schema-zero-plus-invalid-mutant",
      "name": "typed-delta schema 0 errors plus non-vacuous invalid",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py",
      "result": "PASS",
      "assertions": 2
    },
    {
      "id": "negative-control-verbatim",
      "name": "invalid preset and name-only clone rejected",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py",
      "result": "PASS",
      "assertions": 2
    }
  ],
  "negative_controls": [
    {
      "id": "schema-invalid-preset",
      "kind": "malformed-input",
      "description": "NEGATIVE CONTROL: Draft202012Validator is applied to a deliberately invalid preset that omits required keys (including weighting). The check must emit one or more ValidationError objects on that record. A validator that is silent on the invalid record is vacuous and this probe fails.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "Draft202012Validator emitted 15 errors",
      "good_state_output": "family typed-delta error_count=0"
    },
    {
      "id": "name-only-clone",
      "kind": "mutation",
      "description": "NEGATIVE CONTROL: a name-only clone of C-G26-100-idea-brainstorm (id and title changed, every mechanism field identical) is classified as a mechanism-duplicate and rejected. Distance 0 is the rejected state.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "distance==0 MechanismDuplicate",
      "good_state_output": "nearest sibling C-G26-thin distance=11"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0103-probe1-independent-instantiate",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": false,
    "notes": "Probe 1 re-instantiates both family members against the fixture task and recomputes nearest-sibling distance without reading this document's report.nearest_sibling field."
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0103/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0103"
  },
  "downstream_consumers": [
    {
      "consumer": "CNL-0103/engine.py:envelope_validator",
      "artifact_path": "command-center/design/council/CNL-0103-generative-preset-family-100-idea-brainstorm-and-innovatio.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "schema-validate",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0103/probe2_schema_and_negative.py",
        "raw_output": "emit-time envelope error_count=0 after write+re-read",
        "fingerprint": "6dba042b0ba1c37bb14bba0ca38f198a",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-26T02:33:25Z",
    "ended_at": "2026-08-26T02:33:25Z"
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)."
  },
  "residual_unknowns": [
    {
      "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; nearest sibling is over the reconstructed fixture, not a 72-preset library recount.",
      "verdict": "CONFIRMED",
      "settling_experiment": "Place the library file on the worktree and re-run nearest_sibling over its presets array."
    }
  ],
  "report": {
    "kind": "council-preset",
    "control_ids": [
      "schema-invalid-preset",
      "name-only-clone",
      "raw-count-gaming-ledger"
    ],
    "observations": [
      {
        "name": "brainstorm_novelty",
        "measured": 0.85,
        "method": "instantiate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json"
      },
      {
        "name": "moonshot_novelty",
        "measured": 0.95,
        "method": "instantiate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json"
      },
      {
        "name": "brainstorm_feasibility",
        "measured": 0.15,
        "method": "instantiate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json"
      },
      {
        "name": "moonshot_feasibility",
        "measured": 0.05,
        "method": "instantiate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/family_presets.json"
      },
      {
        "name": "brainstorm_nearest_sibling_distance",
        "measured": 11,
        "method": "fingerprint-hamming",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/sibling_library.json"
      },
      {
        "name": "gaming_unique_ideas",
        "measured": 10,
        "method": "canonical-mechanism-plus-jaccard",
        "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py"
      },
      {
        "name": "genuine_unique_ideas",
        "measured": 100,
        "method": "canonical-mechanism-plus-jaccard",
        "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py"
      },
      {
        "name": "brainstorm_stop_on_gaming_ledger",
        "measured": false,
        "method": "stop_fires",
        "anchor": "command-center/p2-wave/probes/CNL-0103/engine.py"
      },
      {
        "name": "typed_delta_schema_error_count",
        "measured": 0,
        "method": "schema-validate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/preset.record.schema.json"
      },
      {
        "name": "invalid_preset_schema_error_count",
        "measured": 15,
        "method": "schema-validate",
        "anchor": "command-center/p2-wave/probes/CNL-0103/fixtures/invalid_preset.json"
      }
    ],
    "title": "Generative preset family: 100-idea brainstorm and innovation moonshot",
    "question": "What preset configuration reliably produces 100 genuinely distinct ideas - and how do the brainstorm and the moonshot presets differ in their novelty-versus-feasibility weighting rather than merely in their name?",
    "preset": {
      "id": "C-G26-100-idea-brainstorm",
      "kind": "typed_delta",
      "relation": "extends",
      "base_spec": {
        "id": "councilspec.v2.generative-base",
        "version": "2.0.0"
      },
      "extends_c_ids": [
        "C-G26",
        "C-M01"
      ],
      "roles": [
        {
          "id": "SwarmGenerator",
          "obligation": "emit mechanism-tagged ideas"
        },
        {
          "id": "Analogist",
          "obligation": "emit cross-domain analogs"
        },
        {
          "id": "Combiner",
          "obligation": "emit morphological combinations"
        },
        {
          "id": "DistinctnessAuditor",
          "obligation": "drop only canonical or high-jaccard duplicates"
        },
        {
          "id": "CoverageMapper",
          "obligation": "tag coverage holes; cannot veto"
        },
        {
          "id": "FeasibilityAnnotator",
          "obligation": "score feasibility; cannot drop"
        }
      ],
      "voting": {
        "method": "keep-all-that-pass-distinctness",
        "quorum": 3
      },
      "stopping": {
        "expression": "unique_ideas >= 100 AND (saturated OR completeness_score >= 0.90)",
        "max_rounds": 24
      },
      "protocol_schedule": [
        "P26",
        "P30"
      ],
      "editable_dials": [
        "stopping.unique_ideas_target",
        "stopping.max_rounds",
        "weighting.novelty",
        "weighting.feasibility"
      ],
      "non_editable_dials": [
        "voting.method",
        "stopping.unique_ideas_source",
        "anti_failure.critique_cannot_seat_in_generation"
      ],
      "default_binding": "quantity-first-generation",
      "weighting": {
        "novelty": 0.85,
        "feasibility": 0.15
      },
      "distinctness_gate": {
        "signals": [
          "canonical_mechanism",
          "token_jaccard"
        ],
        "jaccard_threshold": 0.85,
        "canonical_match_is_duplicate": true,
        "accept_rule": "distinctness_pass",
        "novelty_floor": 0.0
      },
      "generation_critique_split": {
        "leak_policy": "reject-seating",
        "generation_round_roles": [
          "SwarmGenerator",
          "Analogist",
          "Combiner"
        ],
        "critique_round_roles": [
          "DistinctnessAuditor",
          "CoverageMapper",
          "FeasibilityAnnotator"
        ]
      }
    },
    "family_presets": [
      {
        "id": "C-G26-100-idea-brainstorm",
        "kind": "typed_delta",
        "relation": "extends",
        "base_spec": {
          "id": "councilspec.v2.generative-base",
          "version": "2.0.0"
        },
        "extends_c_ids": [
          "C-G26",
          "C-M01"
        ],
        "roles": [
          {
            "id": "SwarmGenerator",
            "obligation": "emit mechanism-tagged ideas"
          },
          {
            "id": "Analogist",
            "obligation": "emit cross-domain analogs"
          },
          {
            "id": "Combiner",
            "obligation": "emit morphological combinations"
          },
          {
            "id": "DistinctnessAuditor",
            "obligation": "drop only canonical or high-jaccard duplicates"
          },
          {
            "id": "CoverageMapper",
            "obligation": "tag coverage holes; cannot veto"
          },
          {
            "id": "FeasibilityAnnotator",
            "obligation": "score feasibility; cannot drop"
          }
        ],
        "voting": {
          "method": "keep-all-that-pass-distinctness",
          "quorum": 3
        },
        "stopping": {
          "expression": "unique_ideas >= 100 AND (saturated OR completeness_score >= 0.90)",
          "max_rounds": 24
        },
        "protocol_schedule": [
          "P26",
          "P30"
        ],
        "editable_dials": [
          "stopping.unique_ideas_target",
          "stopping.max_rounds",
          "weighting.novelty",
          "weighting.feasibility"
        ],
        "non_editable_dials": [
          "voting.method",
          "stopping.unique_ideas_source",
          "anti_failure.critique_cannot_seat_in_generation"
        ],
        "default_binding": "quantity-first-generation",
        "weighting": {
          "novelty": 0.85,
          "feasibility": 0.15
        },
        "distinctness_gate": {
          "signals": [
            "canonical_mechanism",
            "token_jaccard"
          ],
          "jaccard_threshold": 0.85,
          "canonical_match_is_duplicate": true,
          "accept_rule": "distinctness_pass",
          "novelty_floor": 0.0
        },
        "generation_critique_split": {
          "leak_policy": "reject-seating",
          "generation_round_roles": [
            "SwarmGenerator",
            "Analogist",
            "Combiner"
          ],
          "critique_round_roles": [
            "DistinctnessAuditor",
            "CoverageMapper",
            "FeasibilityAnnotator"
          ]
        }
      },
      {
        "id": "C-G29-innovation-moonshot",
        "kind": "typed_delta",
        "relation": "extends",
        "base_spec": {
          "id": "councilspec.v2.generative-base",
          "version": "2.0.0"
        },
        "extends_c_ids": [
          "C-G29",
          "C-G31",
          "C-M01"
        ],
        "roles": [
          {
            "id": "WildInventor",
            "obligation": "emit high-novelty mechanisms"
          },
          {
            "id": "ContradictionSolver",
            "obligation": "emit TRIZ contradiction resolutions"
          },
          {
            "id": "ConstraintRelaxes",
            "obligation": "emit constraint-dropped variants"
          },
          {
            "id": "Counterfactualist",
            "obligation": "emit counterfactual mechanisms"
          },
          {
            "id": "NoveltyScorer",
            "obligation": "drop only below novelty_floor"
          },
          {
            "id": "FeasibilityAnnotator",
            "obligation": "score feasibility as ranking tie-break; cannot drop"
          }
        ],
        "voting": {
          "method": "novelty-lexicographic",
          "quorum": 4
        },
        "stopping": {
          "expression": "unique_ideas >= 100 AND novelty_median >= 0.80",
          "max_rounds": 30
        },
        "protocol_schedule": [
          "P29",
          "P31",
          "P32"
        ],
        "editable_dials": [
          "stopping.unique_ideas_target",
          "stopping.max_rounds",
          "weighting.novelty",
          "weighting.feasibility",
          "distinctness_gate.novelty_floor"
        ],
        "non_editable_dials": [
          "voting.method",
          "stopping.unique_ideas_source",
          "anti_failure.critique_cannot_seat_in_generation"
        ],
        "default_binding": "novelty-first-generation",
        "weighting": {
          "novelty": 0.95,
          "feasibility": 0.05
        },
        "distinctness_gate": {
          "signals": [
            "canonical_mechanism",
            "token_jaccard"
          ],
          "jaccard_threshold": 0.85,
          "canonical_match_is_duplicate": true,
          "accept_rule": "distinctness_pass AND novelty_score >= novelty_floor",
          "novelty_floor": 0.7
        },
        "generation_critique_split": {
          "leak_policy": "reject-seating",
          "generation_round_roles": [
            "WildInventor",
            "ContradictionSolver",
            "ConstraintRelaxes",
            "Counterfactualist"
          ],
          "critique_round_roles": [
            "NoveltyScorer",
            "FeasibilityAnnotator"
          ]
        }
      }
    ],
    "weighting_delta": {
      "brainstorm_id": "C-G26-100-idea-brainstorm",
      "moonshot_id": "C-G29-innovation-moonshot",
      "brainstorm_novelty": 0.85,
      "brainstorm_feasibility": 0.15,
      "moonshot_novelty": 0.95,
      "moonshot_feasibility": 0.05,
      "accept_rule_brainstorm": "distinctness_pass",
      "accept_rule_moonshot": "distinctness_pass AND novelty_score >= novelty_floor",
      "ranking_key_brainstorm": [
        "coverage_gap",
        "distinctness"
      ],
      "ranking_key_moonshot": [
        "novelty_score",
        "feasibility_score"
      ],
      "stop_brainstorm": "unique_ideas >= 100 AND (saturated OR completeness_score >= 0.90)",
      "stop_moonshot": "unique_ideas >= 100 AND novelty_median >= 0.80",
      "weights_are_not_identical": true
    },
    "nearest_sibling": {
      "id": "C-G26-thin",
      "named": true,
      "source": "reconstructed from CNL-0042 named P-ids plus the on-tree ARC-0003 catalog-class transcription; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent",
      "library_bytes_read": false
    },
    "nearest_sibling_differential": [
      {
        "preset_id": "C-G26-100-idea-brainstorm",
        "nearest_sibling_id": "C-G26-thin",
        "distance": 11,
        "differing_fields": [
          "roles",
          "protocols",
          "round_kinds",
          "vote_method",
          "prune_on",
          "stop_expr",
          "raw_count_stop",
          "novelty",
          "feasibility_w",
          "accept_rule",
          "ranking_key"
        ],
        "name_only_clone_rejected": true
      },
      {
        "preset_id": "C-G29-innovation-moonshot",
        "nearest_sibling_id": "C-G26-thin",
        "distance": 12,
        "differing_fields": [
          "roles",
          "protocols",
          "round_kinds",
          "vote_method",
          "prune_on",
          "stop_expr",
          "raw_count_stop",
          "novelty",
          "feasibility_w",
          "accept_rule",
          "novelty_floor",
          "ranking_key"
        ],
        "name_only_clone_rejected": true
      }
    ],
    "answers": {
      "how_100_distinct_ideas": "Stop on unique_ideas >= 100 where unique_ideas is the post-dedup ledger (canonical_mechanism OR token Jaccard >= 0.85). Raw count cannot satisfy the stop. Generation seats cannot include critique-only roles, so feasibility cannot veto during generation. Completeness_floor 0.90 blocks a quota dump of 100 near-duplicates in one bucket.",
      "novelty_versus_feasibility": "Brainstorm novelty=0.85 feasibility=0.15, accept_rule=distinctness_pass, ranking_key=coverage_gap then distinctness, prune_on=distinctness_fail_only. Moonshot novelty=0.95 feasibility=0.05, accept_rule=distinctness_pass AND novelty_score >= novelty_floor (0.70), ranking_key=novelty_score then feasibility_score, prune_on=distinctness_fail_or_novelty_below_floor. Feasibility never appears in either stop expression.",
      "c_id_map": "C-G26-100-idea-brainstorm extends C-G26 and C-M01. C-G29-innovation-moonshot extends C-G29, C-G31, and C-M01. C-G26/C-G29/C-G31 are catalog protocol bindings named by CNL-0042 (P26/P29/P31). C-M01 is the 20-key surface named by CNL-0002. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not on this worktree; those C-ids are catalog-derived, not byte-copied library records."
    },
    "instantiation": {
      "task_id": "task.fixture.100-ideas.household-energy",
      "roster_ids": [
        "SwarmGenerator",
        "Analogist",
        "Combiner",
        "DistinctnessAuditor",
        "CoverageMapper",
        "FeasibilityAnnotator"
      ],
      "protocol_schedule": [
        "P26",
        "P30"
      ],
      "voting": {
        "method": "keep-all-that-pass-distinctness",
        "quorum": 3,
        "prune_on": "distinctness_fail_only"
      },
      "stopping": {
        "expression": "unique_ideas >= 100 AND (saturated OR completeness_score >= 0.90)",
        "max_rounds": 24
      }
    },
    "instantiations": [
      {
        "task_id": "task.fixture.100-ideas.household-energy",
        "roster_ids": [
          "SwarmGenerator",
          "Analogist",
          "Combiner",
          "DistinctnessAuditor",
          "CoverageMapper",
          "FeasibilityAnnotator"
        ],
        "protocol_schedule": [
          "P26",
          "P30"
        ],
        "voting": {
          "method": "keep-all-that-pass-distinctness",
          "quorum": 3,
          "prune_on": "distinctness_fail_only"
        },
        "stopping": {
          "expression": "unique_ideas >= 100 AND (saturated OR completeness_score >= 0.90)",
          "max_rounds": 24
        }
      },
      {
        "task_id": "task.fixture.100-ideas.household-energy",
        "roster_ids": [
          "WildInventor",
          "ContradictionSolver",
          "ConstraintRelaxes",
          "Counterfactualist",
          "NoveltyScorer",
          "FeasibilityAnnotator"
        ],
        "protocol_schedule": [
          "P29",
          "P31",
          "P32"
        ],
        "voting": {
          "method": "novelty-lexicographic",
          "quorum": 4,
          "prune_on": "distinctness_fail_or_novelty_below_floor"
        },
        "stopping": {
          "expression": "unique_ideas >= 100 AND novelty_median >= 0.80",
          "max_rounds": 30
        }
      }
    ],
    "schema_validation": {
      "validator": "jsonschema.Draft202012Validator",
      "schema_path": "command-center/schema/council-preset.schema.json",
      "envelope_resolution": "disk-local RefResolver store (no network)",
      "typed_delta_schema": "command-center/p2-wave/probes/CNL-0103/fixtures/preset.record.schema.json",
      "records_checked": 3,
      "error_count": 0,
      "deliberately_invalid_error_count": 15
    },
    "library": {
      "on_this_worktree": false,
      "presets_compared_from_disk": 0
    }
  }
}
