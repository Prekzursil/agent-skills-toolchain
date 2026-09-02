{
  "unit_id": "CNL-0109",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0109",
  "kind": "council_preset_family",
  "family_id": "council.preset.family.strategy-and-constrained-prioritisation",
  "question": "Direction-setting under uncertainty and ranking under a fixed budget are different decisions - which voting method suits each, and why is ranked-choice a trap for a prioritisation whose options are not mutually exclusive?",
  "answer": {
    "direction_voting_method": "pairwise-condorcet",
    "prioritisation_voting_method": "calibrated-score-knapsack",
    "why_ranked_choice_is_a_trap": "Ranked-choice/IRV assumes a single mutually exclusive winner and treats lower ranks as substitutes after elimination. A budget portfolio can fund several options at once; walking the IRV order until the budget is spent elects the shiny singleton and drops the complementary high-density pair. Cardinal scores plus a knapsack select a feasible set. The trap is the exclusivity assumption."
  },
  "presets": [
    {
      "id": "council.preset.strategy.direction-under-uncertainty",
      "kind": "council_preset",
      "family_id": "council.preset.family.strategy-and-constrained-prioritisation",
      "title": "Direction-setting under uncertainty",
      "outcome_type": "exclusive_direction",
      "base_spec_ref": "CouncilSpec.v2",
      "base_spec_version": "2.0.0",
      "extends_c_ids": [
        {
          "id": "council.preset.catalog-class.editable",
          "relation": "extends",
          "source": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
          "on_this_tree": "transcribed-only-library-absent"
        },
        {
          "id": "CNL-0061",
          "relation": "contrasts",
          "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0061",
          "on_this_tree": "catalog-unit"
        }
      ],
      "default_binding": {
        "protocol": "P-pairwise-deliberation",
        "task_selector": "decision_kind==exclusive_direction"
      },
      "editable_dials": [
        "delta.stopping.confidence_floor",
        "delta.stopping.max_rounds",
        "delta.voting.cycle_completion",
        "delta.roles.optional"
      ],
      "protocol_schedule": [
        "P-forecast-priors",
        "P-pairwise-deliberation",
        "P-condorcet-tally",
        "P-confidence-gate"
      ],
      "delta": {
        "roles": {
          "required": [
            "Strategist",
            "Forecaster",
            "Skeptic",
            "DevilAdvocate"
          ],
          "optional": [
            "DomainWitness"
          ]
        },
        "voting": {
          "rule": "pairwise-condorcet",
          "quorum": 4,
          "cycle_completion": "minmax",
          "declared_before_ballots": true,
          "uncertainty": {
            "model": "beta-binomial-posterior",
            "confidence_floor": 0.67
          }
        },
        "stopping": {
          "expression": "condorcet_winner_exists AND posterior_mass(winner)>=confidence_floor OR rounds>=max_rounds THEN BLOCKED",
          "max_rounds": 6,
          "on_timeout": "BLOCKED",
          "on_unresolved": "BLOCKED",
          "skip_min_deliberation": false
        },
        "anti_failure": {
          "on_split": "surface-disagreement",
          "no_silent_average": true,
          "ranked_choice_forbidden": true
        },
        "audit": {
          "persist_transcript": true,
          "hash_inputs": true
        }
      }
    },
    {
      "id": "council.preset.prioritisation.budget-constrained-portfolio",
      "kind": "council_preset",
      "family_id": "council.preset.family.strategy-and-constrained-prioritisation",
      "title": "Constrained prioritisation under a fixed budget",
      "outcome_type": "budget_portfolio",
      "base_spec_ref": "CouncilSpec.v2",
      "base_spec_version": "2.0.0",
      "extends_c_ids": [
        {
          "id": "council.preset.catalog-class.editable",
          "relation": "extends",
          "source": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
          "on_this_tree": "transcribed-only-library-absent"
        },
        {
          "id": "CNL-0062",
          "relation": "extends",
          "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0062",
          "on_this_tree": "catalog-unit"
        },
        {
          "id": "CNL-0061",
          "relation": "contrasts",
          "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0061",
          "on_this_tree": "catalog-unit"
        }
      ],
      "default_binding": {
        "protocol": "P-cardinal-knapsack",
        "task_selector": "decision_kind==budget_portfolio"
      },
      "editable_dials": [
        "delta.budget.amount",
        "delta.budget.unit",
        "delta.voting.score_scale",
        "delta.stopping.max_rounds"
      ],
      "protocol_schedule": [
        "P-score-elicit",
        "P-scale-calibrate",
        "P-dependency-graph",
        "P-knapsack-aggregate",
        "P-dissent-record"
      ],
      "delta": {
        "roles": {
          "required": [
            "Treasurer",
            "ValueScorer",
            "PortfolioSkeptic",
            "DependencyMapper"
          ],
          "optional": [
            "OwnerProxy"
          ]
        },
        "voting": {
          "rule": "calibrated-score-knapsack",
          "quorum": 4,
          "score_scale": {
            "min": 0,
            "max": 10
          },
          "calibration": "within-participant-z-then-median-pool",
          "aggregator": "value-density-knapsack",
          "exclusivity": false
        },
        "stopping": {
          "expression": "feasible_set_stable_for 2 rounds AND calibration_ok OR rounds>=max_rounds THEN emit-feasible-set-with-dissent",
          "max_rounds": 5,
          "on_timeout": "emit-feasible-set-with-dissent",
          "on_unresolved": "BLOCKED",
          "skip_min_deliberation": false
        },
        "anti_failure": {
          "ranked_choice_forbidden": true,
          "reject_reason": "options_not_mutually_exclusive"
        },
        "budget": {
          "required": true,
          "hard_constraint": true,
          "amount": null,
          "unit": "currency"
        },
        "audit": {
          "persist_transcript": true,
          "hash_inputs": true
        }
      }
    }
  ],
  "nearest_sibling": {
    "named": "council.preset.catalog-class.editable",
    "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
    "profile_distance": 5,
    "differing_axes": [
      "roles.required",
      "protocol_schedule",
      "voting.rule",
      "stopping.expression",
      "outcome_type"
    ],
    "per_preset": [
      {
        "named": "council.preset.catalog-class.editable",
        "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
        "profile_distance": 5,
        "differing_axes": [
          "roles.required",
          "protocol_schedule",
          "voting.rule",
          "stopping.expression",
          "outcome_type"
        ],
        "left_fingerprint": {
          "roles.required": [
            "DevilAdvocate",
            "Forecaster",
            "Skeptic",
            "Strategist"
          ],
          "protocol_schedule": [
            "P-forecast-priors",
            "P-pairwise-deliberation",
            "P-condorcet-tally",
            "P-confidence-gate"
          ],
          "voting.rule": "pairwise-condorcet",
          "stopping.expression": "condorcet_winner_exists AND posterior_mass(winner)>=confidence_floor OR rounds>=max_rounds THEN BLOCKED",
          "outcome_type": "exclusive_direction"
        },
        "right_fingerprint": {
          "roles.required": [
            "Architect",
            "Critic",
            "Pragmatist",
            "Skeptic"
          ],
          "protocol_schedule": [
            "P-four-voice-prompt"
          ],
          "voting.rule": "unanimous-or-record-dissent",
          "stopping.expression": "max_rounds=8 THEN halt",
          "outcome_type": "unspecified"
        }
      },
      {
        "named": "council.preset.catalog-class.editable",
        "source_id": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json#presets",
        "profile_distance": 5,
        "differing_axes": [
          "roles.required",
          "protocol_schedule",
          "voting.rule",
          "stopping.expression",
          "outcome_type"
        ],
        "left_fingerprint": {
          "roles.required": [
            "DependencyMapper",
            "PortfolioSkeptic",
            "Treasurer",
            "ValueScorer"
          ],
          "protocol_schedule": [
            "P-score-elicit",
            "P-scale-calibrate",
            "P-dependency-graph",
            "P-knapsack-aggregate",
            "P-dissent-record"
          ],
          "voting.rule": "calibrated-score-knapsack",
          "stopping.expression": "feasible_set_stable_for 2 rounds AND calibration_ok OR rounds>=max_rounds THEN emit-feasible-set-with-dissent",
          "outcome_type": "budget_portfolio"
        },
        "right_fingerprint": {
          "roles.required": [
            "Architect",
            "Critic",
            "Pragmatist",
            "Skeptic"
          ],
          "protocol_schedule": [
            "P-four-voice-prompt"
          ],
          "voting.rule": "unanimous-or-record-dissent",
          "stopping.expression": "max_rounds=8 THEN halt",
          "outcome_type": "unspecified"
        }
      }
    ]
  },
  "instantiations": [
    {
      "task_id": "task.direction.north-star-2026",
      "preset_id": "council.preset.strategy.direction-under-uncertainty",
      "roster": [
        "Strategist",
        "Forecaster",
        "Skeptic",
        "DevilAdvocate"
      ],
      "protocol_schedule": [
        "P-forecast-priors",
        "P-pairwise-deliberation",
        "P-condorcet-tally",
        "P-confidence-gate"
      ],
      "voting_method": "pairwise-condorcet",
      "stopping_expression": "condorcet_winner_exists AND posterior_mass(winner)>=confidence_floor OR rounds>=max_rounds THEN BLOCKED",
      "outcome_type": "exclusive_direction",
      "quorum": 4,
      "max_rounds": 6
    },
    {
      "task_id": "task.portfolio.q3-roadmap",
      "preset_id": "council.preset.prioritisation.budget-constrained-portfolio",
      "roster": [
        "Treasurer",
        "ValueScorer",
        "PortfolioSkeptic",
        "DependencyMapper"
      ],
      "protocol_schedule": [
        "P-score-elicit",
        "P-scale-calibrate",
        "P-dependency-graph",
        "P-knapsack-aggregate",
        "P-dissent-record"
      ],
      "voting_method": "calibrated-score-knapsack",
      "stopping_expression": "feasible_set_stable_for 2 rounds AND calibration_ok OR rounds>=max_rounds THEN emit-feasible-set-with-dissent",
      "outcome_type": "budget_portfolio",
      "quorum": 4,
      "max_rounds": 5
    }
  ],
  "schema_validation": {
    "valid_error_count": 0,
    "invalid_error_count": 1,
    "validator": "jsonschema.Draft202012Validator",
    "mutant_id": "council.preset.NEG.ranked-choice-on-portfolio"
  },
  "negative_control": {
    "rejects": "ranked-choice bound to outcome_type=budget_portfolio",
    "on_state": "a portfolio preset whose voting.rule is ranked-choice (options treated as exclusive substitutes)",
    "verbatim": "['delta', 'voting', 'rule']: 'ranked-choice' should not be valid under {'enum': ['ranked-choice', 'majority', 'pairwise-condorcet']}",
    "owner_override_verbatim": "REJECT non-editable dial 'delta.voting.rule' (allowed=['delta.budget.amount', 'delta.budget.unit', 'delta.stopping.max_rounds', 'delta.voting.score_scale'])",
    "name_only_clone_verbatim": "mechanism-duplicate of council.preset.strategy.direction-under-uncertainty: differential is only the name; merge"
  },
  "library_status": {
    "library": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "present": false,
    "source": "transcribed-fixture-library-absent",
    "path": "command-center/p2-wave/probes/CNL-0109/fixtures/sibling_catalog.json",
    "preset_count": 1,
    "honesty": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not a file on this worktree. Nearest-sibling comparison uses the on-tree transcription of council.preset.catalog-class.editable (ARC-0003 catalog-cited axes), not a recount of 72."
  },
  "rcv_trap": {
    "irv_winner": "C",
    "irv_portfolio_value": 8,
    "knapsack_set": [
      "A",
      "B"
    ],
    "knapsack_value": 10,
    "trap_fires": true,
    "why": "IRV elects a single substitute (C) because it assumes mutually exclusive alternatives. Funding along the IRV order then spends the budget on C and cannot also take A or B. Calibrated score + knapsack funds A+B, the feasible set with higher total value. Ranked-choice has no representation of 'both A and B'."
  },
  "reviewer": {
    "reviewer_id": "CNL-0109-probe2-sibling-and-rcv-trap",
    "verdict": "PASS",
    "independent": true,
    "scope": "Recomputes nearest-sibling distance, name-only clone rejection, and IRV-vs-knapsack trap from fixtures; does not copy the author's narrative."
  },
  "extends": {
    "c_ids": [
      "council.preset.catalog-class.editable",
      "CNL-0061",
      "CNL-0062"
    ],
    "note": "Extends the on-tree transcription of the catalog-class editable preset; contrasts CNL-0061 (IRV pathologies) and uses CNL-0062 (cardinal calibration) for the portfolio member. Not a name-only fork of the sibling: voting.rule, roster, protocol_schedule, stopping.expression and outcome_type all differ."
  }
}
