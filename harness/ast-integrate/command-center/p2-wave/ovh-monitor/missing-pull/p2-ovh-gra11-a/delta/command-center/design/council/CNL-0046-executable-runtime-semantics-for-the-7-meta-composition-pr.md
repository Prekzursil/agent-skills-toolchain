{
  "unit_id": "CNL-0046",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0046",
  "title": "Executable runtime semantics for the 7 META-COMPOSITION protocols",
  "family": "META-COMPOSITION",
  "expected_n": 7,
  "question": "Ranging over exactly these 7 records, named so no member can fall through a family mis-assignment (P52 nested-subcouncils-meta-council, P53 escalation-ladder, P54 cross-vendor-mirrored, P55 shadow-council, P56 minority-report-mandatory, P57 stopping-rule-tournament, P58 owner-in-the-loop-stepwise): For each of the 7 META-COMPOSITION protocol records, what are the composition preconditions, and which pairs of composed protocols conflict on turn control or on stopping?",
  "answer": "The META-COMPOSITION family is exactly P52-P58. Each card is EXECUTABLE: nested fan-in (P52), escalation seize (P53), mirrored parallel clocks (P54), silent shadow (P55), mandatory minority slot (P56), stopping-rule tournament (P57), owner stepwise gate (P58). Composition preconditions are the named predicates on each record. 15 of 21 meta pairs conflict on turn_control and/or stopping; unmarked P57xP58 and a 6-member family are planted rejects the checker fires on while remaining silent on known-good.",
  "source_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this Linux worktree. Enumeration uses the catalog named list at command-center/WORK-UNIT-CATALOG.json CNL-0046 question_or_target, independently recounted by regex, then checked against family=META-COMPOSITION on the fixture records.",
  "enumerated_ids": [
    "P52",
    "P53",
    "P54",
    "P55",
    "P56",
    "P57",
    "P58"
  ],
  "enumerated_slugs": [
    "nested-subcouncils-meta-council",
    "escalation-ladder",
    "cross-vendor-mirrored",
    "shadow-council",
    "minority-report-mandatory",
    "stopping-rule-tournament",
    "owner-in-the-loop-stepwise"
  ],
  "count_signals": [
    {
      "mechanism": "catalog-regex",
      "n": 7,
      "ids": [
        "P52",
        "P53",
        "P54",
        "P55",
        "P56",
        "P57",
        "P58"
      ],
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0046.question_or_target"
    },
    {
      "mechanism": "fixture-family-field",
      "n": 7,
      "ids": [
        "P52",
        "P53",
        "P54",
        "P55",
        "P56",
        "P57",
        "P58"
      ],
      "anchor": "command-center/p2-wave/probes/CNL-0046/fixtures/known_good_records.json"
    }
  ],
  "records": [
    {
      "id": "P52",
      "slug": "nested-subcouncils-meta-council",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "at_least_two_child_protocol_ids",
        "fan_in_rule_in_majority_owner_cite_child_evidence",
        "child_completion_before_parent_synthesis",
        "no_two_children_with_exclusive_floor_on_one_roster",
        "parent_may_not_overrule_child_without_citing_child_evidence"
      ],
      "turn_control": {
        "tags": [
          "child_inner",
          "parent_outer"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "parent_chair",
            "action": "OPEN_CHILD",
            "bound": "n_children>=2",
            "next": "run"
          },
          {
            "id": "run",
            "actor": "children",
            "action": "RUN_INNER",
            "bound": "each_child.stopping",
            "next": "fan_in"
          },
          {
            "id": "fan_in",
            "actor": "parent_chair",
            "action": "FAN_IN",
            "bound": "cite_each_child_record",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "parent_stopping_after_children",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "wait_children"
        ]
      },
      "conflicts_with": [
        {
          "id": "P53",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P54",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P58",
          "axes": [
            "stopping",
            "turn_control"
          ]
        }
      ]
    },
    {
      "id": "P53",
      "slug": "escalation-ladder",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "ordered_rungs_with_executable_triggers",
        "each_rung_names_successor_protocol_or_owner_gate",
        "deadlock_detector_distinct_from_slow_progress",
        "seize_floor_only_on_trigger_fire"
      ],
      "turn_control": {
        "tags": [
          "seize_on_trigger"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "detector",
            "action": "WATCH",
            "bound": "progress_metric",
            "next": "seize"
          },
          {
            "id": "seize",
            "actor": "escalator",
            "action": "SEIZE_FLOOR",
            "bound": "one_turn",
            "next": "rung"
          },
          {
            "id": "rung",
            "actor": "escalator",
            "action": "ESCALATE",
            "bound": "rung_table",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "rung_terminal_or_resume",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "override_escalate"
        ]
      },
      "conflicts_with": [
        {
          "id": "P52",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P55",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P56",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P58",
          "axes": [
            "turn_control"
          ]
        }
      ]
    },
    {
      "id": "P54",
      "slug": "cross-vendor-mirrored",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "at_least_two_vendor_partitions",
        "identical_inner_protocol_card_and_charter",
        "no_cross_talk_until_compare",
        "compare_rule_executable"
      ],
      "turn_control": {
        "tags": [
          "parallel_clocks"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "splitter",
            "action": "OPEN_CHILD",
            "bound": "n_mirrors>=2",
            "next": "run"
          },
          {
            "id": "run",
            "actor": "mirrors",
            "action": "MIRROR_STEP",
            "bound": "inner.stopping_each",
            "next": "compare"
          },
          {
            "id": "compare",
            "actor": "comparator",
            "action": "COMPARE",
            "bound": "divergence_threshold",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "both_mirrors_and_compare",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "both_mirrors"
        ]
      },
      "conflicts_with": [
        {
          "id": "P52",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P58",
          "axes": [
            "stopping",
            "turn_control"
          ]
        }
      ]
    },
    {
      "id": "P55",
      "slug": "shadow-council",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "shadow_seats_cannot_take_primary_floor",
        "shadow_read_access_subset_named",
        "shadow_verdict_recorded_not_mixed_into_primary_votes",
        "shadow_stop_must_not_trigger_primary_stop"
      ],
      "turn_control": {
        "tags": [
          "silent_no_floor"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "primary",
            "action": "RUN_INNER",
            "bound": "primary.stopping",
            "next": "observe"
          },
          {
            "id": "observe",
            "actor": "shadow",
            "action": "SHADOW_OBSERVE",
            "bound": "no_floor_token",
            "next": "seal"
          },
          {
            "id": "seal",
            "actor": "shadow",
            "action": "SHADOW_SEAL",
            "bound": "shadow_record_only",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "primary_stop_shadow_isolated",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "shadow_isolated"
        ]
      },
      "conflicts_with": [
        {
          "id": "P53",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P56",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping"
          ]
        }
      ]
    },
    {
      "id": "P56",
      "slug": "minority-report-mandatory",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "inner_protocol_emits_majority_or_decision",
        "dissent_exists_or_designated_minority_seat",
        "preservation_path_to_synthesis_is_structural",
        "synthesis_blocked_until_minority_attached"
      ],
      "turn_control": {
        "tags": [
          "post_decision_slot"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "inner",
            "action": "RUN_INNER",
            "bound": "inner.stopping",
            "next": "lock"
          },
          {
            "id": "lock",
            "actor": "majority",
            "action": "MAJORITY_LOCK",
            "bound": "decision_record",
            "next": "minority"
          },
          {
            "id": "minority",
            "actor": "minority_seat",
            "action": "MINORITY_ATTACH",
            "bound": "must_exist",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "decision_plus_minority",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "delay_for_minority"
        ]
      },
      "conflicts_with": [
        {
          "id": "P53",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P55",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P58",
          "axes": [
            "stopping"
          ]
        }
      ]
    },
    {
      "id": "P57",
      "slug": "stopping-rule-tournament",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "at_least_two_candidate_stopping_expressions",
        "tournament_scoring_rule_executable",
        "each_candidate_statically_valid",
        "exactly_one_winner_armed_as_live_stop"
      ],
      "turn_control": {
        "tags": [
          "tournament_last_floor"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "arms",
            "action": "TOURNAMENT_EVAL",
            "bound": "n_candidates>=2",
            "next": "pick"
          },
          {
            "id": "pick",
            "actor": "chair",
            "action": "TOURNAMENT_EVAL",
            "bound": "scoring_rule",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "winning_stop_only",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "tournament_pick"
        ]
      },
      "conflicts_with": [
        {
          "id": "P52",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P53",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P54",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P55",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P56",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P58",
          "axes": [
            "stopping",
            "turn_control"
          ]
        }
      ]
    },
    {
      "id": "P58",
      "slug": "owner-in-the-loop-stepwise",
      "family": "META-COMPOSITION",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "composition_preconditions": [
        "owner_seat_with_halt_continue_restart_rights",
        "step_boundaries_named_on_inner_protocol",
        "invalidating_changes_force_restart_not_quiet_continue",
        "audit_records_owner_gate_outcome"
      ],
      "turn_control": {
        "tags": [
          "owner_boundary"
        ],
        "schedule": [
          {
            "id": "start",
            "actor": "inner",
            "action": "RUN_INNER",
            "bound": "until_step_boundary",
            "next": "gate"
          },
          {
            "id": "gate",
            "actor": "owner",
            "action": "OWNER_GATE",
            "bound": "halt_continue_restart",
            "next": "end"
          },
          {
            "id": "end",
            "actor": "runtime",
            "action": "TERMINAL",
            "bound": "owner_halt_or_inner_complete",
            "next": null
          }
        ]
      },
      "stopping": {
        "tags": [
          "owner_gate"
        ]
      },
      "conflicts_with": [
        {
          "id": "P52",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P53",
          "axes": [
            "turn_control"
          ]
        },
        {
          "id": "P54",
          "axes": [
            "stopping",
            "turn_control"
          ]
        },
        {
          "id": "P56",
          "axes": [
            "stopping"
          ]
        },
        {
          "id": "P57",
          "axes": [
            "stopping",
            "turn_control"
          ]
        }
      ]
    }
  ],
  "conflict_pairs": [
    {
      "a": "P52",
      "b": "P53",
      "conflict": true,
      "axes": [
        "stopping",
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "parent_outer",
          "right": "seize_on_trigger",
          "a": "P52",
          "b": "P53"
        },
        {
          "axis": "stopping",
          "left": "wait_children",
          "right": "override_escalate",
          "a": "P52",
          "b": "P53"
        }
      ]
    },
    {
      "a": "P52",
      "b": "P54",
      "conflict": true,
      "axes": [
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "parent_outer",
          "right": "parallel_clocks",
          "a": "P52",
          "b": "P54"
        }
      ]
    },
    {
      "a": "P52",
      "b": "P55",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P52",
      "b": "P56",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P52",
      "b": "P57",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "wait_children",
          "right": "tournament_pick",
          "a": "P52",
          "b": "P57"
        }
      ]
    },
    {
      "a": "P52",
      "b": "P58",
      "conflict": true,
      "axes": [
        "stopping",
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "parent_outer",
          "right": "owner_boundary",
          "a": "P52",
          "b": "P58"
        },
        {
          "axis": "stopping",
          "left": "wait_children",
          "right": "owner_gate",
          "a": "P52",
          "b": "P58"
        }
      ]
    },
    {
      "a": "P53",
      "b": "P54",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P53",
      "b": "P55",
      "conflict": true,
      "axes": [
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "seize_on_trigger",
          "right": "silent_no_floor",
          "a": "P53",
          "b": "P55"
        }
      ]
    },
    {
      "a": "P53",
      "b": "P56",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "override_escalate",
          "right": "delay_for_minority",
          "a": "P53",
          "b": "P56"
        }
      ]
    },
    {
      "a": "P53",
      "b": "P57",
      "conflict": true,
      "axes": [
        "stopping",
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "seize_on_trigger",
          "right": "tournament_last_floor",
          "a": "P53",
          "b": "P57"
        },
        {
          "axis": "stopping",
          "left": "override_escalate",
          "right": "tournament_pick",
          "a": "P53",
          "b": "P57"
        }
      ]
    },
    {
      "a": "P53",
      "b": "P58",
      "conflict": true,
      "axes": [
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "seize_on_trigger",
          "right": "owner_boundary",
          "a": "P53",
          "b": "P58"
        }
      ]
    },
    {
      "a": "P54",
      "b": "P55",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P54",
      "b": "P56",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P54",
      "b": "P57",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "both_mirrors",
          "right": "tournament_pick",
          "a": "P54",
          "b": "P57"
        }
      ]
    },
    {
      "a": "P54",
      "b": "P58",
      "conflict": true,
      "axes": [
        "stopping",
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "parallel_clocks",
          "right": "owner_boundary",
          "a": "P54",
          "b": "P58"
        },
        {
          "axis": "stopping",
          "left": "both_mirrors",
          "right": "owner_gate",
          "a": "P54",
          "b": "P58"
        }
      ]
    },
    {
      "a": "P55",
      "b": "P56",
      "conflict": true,
      "axes": [
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "silent_no_floor",
          "right": "post_decision_slot",
          "a": "P55",
          "b": "P56"
        }
      ]
    },
    {
      "a": "P55",
      "b": "P57",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "shadow_isolated",
          "right": "tournament_pick",
          "a": "P55",
          "b": "P57"
        }
      ]
    },
    {
      "a": "P55",
      "b": "P58",
      "conflict": false,
      "axes": [],
      "reasons": []
    },
    {
      "a": "P56",
      "b": "P57",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "delay_for_minority",
          "right": "tournament_pick",
          "a": "P56",
          "b": "P57"
        }
      ]
    },
    {
      "a": "P56",
      "b": "P58",
      "conflict": true,
      "axes": [
        "stopping"
      ],
      "reasons": [
        {
          "axis": "stopping",
          "left": "delay_for_minority",
          "right": "owner_gate",
          "a": "P56",
          "b": "P58"
        }
      ]
    },
    {
      "a": "P57",
      "b": "P58",
      "conflict": true,
      "axes": [
        "stopping",
        "turn_control"
      ],
      "reasons": [
        {
          "axis": "turn_control",
          "left": "tournament_last_floor",
          "right": "owner_boundary",
          "a": "P57",
          "b": "P58"
        },
        {
          "axis": "stopping",
          "left": "tournament_pick",
          "right": "owner_gate",
          "a": "P57",
          "b": "P58"
        }
      ]
    }
  ],
  "conflict_pair_count": 15,
  "compatible_pair_count": 6,
  "tests": [
    {
      "id": "family-coverage",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0046/probe1_family_schedules.py",
      "result": "PASS"
    },
    {
      "id": "independent-recount",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0046/probe2_independent_recount.py",
      "result": "PASS"
    }
  ],
  "both_states": {
    "known_good_verbatim": "[]",
    "planted_bad_count_verbatim": "[{\"actual\": 6, \"code\": \"FAMILY_COUNT\", \"expected\": 7, \"ids\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"]}, {\"actual\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"], \"code\": \"FAMILY_IDS\", \"expected\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P56\", \"P57\", \"P58\"]}]",
    "planted_bad_schedule_verbatim": "[{\"code\": \"NOT_EXECUTABLE_OR_MISSING_SCHEDULE\", \"id\": \"P53\", \"missing_element\": \"empty_schedule\"}]",
    "planted_bad_conflict_verbatim": "[{\"code\": \"CONFLICT_UNMARKED\", \"id\": \"P57xP58\", \"members\": [\"P57\", \"P58\"], \"missing_axes\": [\"stopping\", \"turn_control\"]}]",
    "silent_on_good": true,
    "fires_on_bad_count": true,
    "fires_on_bad_schedule": true,
    "fires_on_bad_conflict": true
  },
  "negative_control": {
    "reject_state": "META-COMPOSITION family with P56 omitted (n=6)",
    "check_behavior": "FIRES FAMILY_COUNT expected=7 actual=6; does not silently accept a short family",
    "verbatim": "[{\"actual\": 6, \"code\": \"FAMILY_COUNT\", \"expected\": 7, \"ids\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"]}, {\"actual\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"], \"code\": \"FAMILY_IDS\", \"expected\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P56\", \"P57\", \"P58\"]}]",
    "codes": [
      "FAMILY_COUNT",
      "FAMILY_IDS"
    ]
  },
  "negative_controls": [
    {
      "id": "short-family-omit-P56",
      "rejects": "META-COMPOSITION family with P56 omitted (n=6)",
      "verbatim": "[{\"actual\": 6, \"code\": \"FAMILY_COUNT\", \"expected\": 7, \"ids\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"]}, {\"actual\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P57\", \"P58\"], \"code\": \"FAMILY_IDS\", \"expected\": [\"P52\", \"P53\", \"P54\", \"P55\", \"P56\", \"P57\", \"P58\"]}]"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0046-probe2-independent-recount",
    "verdict": "PASS",
    "independent": true,
    "scope_not_agreement": true,
    "method": "re-extract P-ids by regex from catalog question_or_target; re-tabulate conflict pairs from resource tags; a count disagreement blocks the unit",
    "recount_n": 7,
    "recount_ids": [
      "P52",
      "P53",
      "P54",
      "P55",
      "P56",
      "P57",
      "P58"
    ]
  },
  "claims": [
    {
      "id": "C1",
      "claim": "Family META-COMPOSITION has exactly 7 named P-ids P52-P58",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0046.question_or_target"
    },
    {
      "id": "C2",
      "claim": "Each of the 7 records has an executable turn schedule",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0046/composition.py:PROTOCOLS"
    },
    {
      "id": "C3",
      "claim": "Checker is silent on known-good and fires on planted-bad",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0046/fixtures/planted_bad_count.json"
    }
  ],
  "evidence": [
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "kind": "catalog-named-list",
      "claim": "CNL-0046 question_or_target names P52-P58 as META-COMPOSITION"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0046/composition.py",
      "kind": "live-tree",
      "claim": "Executable schedules and conflict tags for P52-P58"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0046/fixtures/planted_bad_count.json",
      "kind": "planted-bad",
      "claim": "Omitting P56 makes FAMILY_COUNT fire"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0046-executable-runtime-semantics-for-the-7-meta-composition-pr.md",
      "exists": true,
      "role": "primary"
    }
  ],
  "generated_at": "2026-08-25T00:51:48Z"
}
