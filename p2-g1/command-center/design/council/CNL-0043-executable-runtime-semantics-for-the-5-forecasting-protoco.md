{
 "adv_rebuild_circle": false,
 "answer": "FORECASTING family n=5 confirmed by two independent counts (catalog named-member clause and fixture family field); live 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree so library bytes were not invented. As written (inherited DISCOVERY status, null resolution_criterion and scoring_rule on every family record) all five protocols are not executable and every attached forecast is unresolvable. This note supplies the runtime. P33 prediction-tournament: resolve by looking up observable_id at resolution_time from resolution_source into outcome_space; score Brier. P34 scenario-planning: narratives do not resolve; attached signposts resolve as P33 and score Brier; scoring the narrative is forbidden. P35 reference-class-planning-poker: resolve when item_status is completed via actual_accessor; score CRPS on the histogram; abandoned items are unresolvable, not scored as zero. P36 calibration-tournament: per-item P33 resolution; rank by mean Brier; report ECE; drop unresolvable items from both. P37 pairwise-comparison: a pair resolves from observed_choice or ground_truth_winner; score Bradley-Terry log loss; a pair with neither is unresolvable. Forecasts in the fixture catalogue that remain unresolvable after this design: ['F-P33-U1', 'F-P34-U1', 'F-P35-U1', 'F-P36-U1', 'F-P37-U1'] (missing source, narrative-as-forecast, incomplete item, missing resolution_time, pair without ground truth or choice). SUCCESS:CNL-0043",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0043-executable-runtime-semantics-for-the-5-forecasting-protoco.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0043/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0043/fixtures/protocols.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0043/fixtures/forecasts.json",
   "role": "supporting"
  }
 ],
 "both_states": {
  "family_misassignment": {
   "bad_n": 4,
   "fires_on_bad": true,
   "flipped_id": "P33",
   "good_n": 5,
   "silent_on_good": true
  },
  "resolvability": {
   "bad_ids": [
    "F-P33-U1",
    "F-P34-U1",
    "F-P35-U1",
    "F-P36-U1",
    "F-P37-U1"
   ],
   "fires_on_bad": true,
   "good_ids": [
    "F-P33-1",
    "F-P34-1",
    "F-P35-1",
    "F-P36-1",
    "F-P37-1"
   ],
   "silent_on_good": true
  }
 },
 "claim_under_test": "The five catalog-named FORECASTING records (P33\u2013P37) have executable resolution criteria and scoring rules, and the fixture catalogue's unresolvable forecasts are exactly the five planted-bad records.",
 "cloud_ok": false,
 "completion_sentinel": "SUCCESS:CNL-0043",
 "does_not_claim": [
  "cloud ok=true is delivery",
  "global unit_manifest.py --write was run",
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from this worktree",
  "the five protocols have been executed outside this fixture runtime"
 ],
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:36433",
   "claim": "Catalog question names P33\u2013P37 so family membership cannot fall through a mis-assignment.",
   "mechanism": "regex P-id extraction from catalog question_or_target",
   "snippet": "\"question_or_target\": \"Ranging over exactly these 5 records, named so no member can fall through a family mis-assignment (P33 prediction-tournament, P34 scenario-planning, P35 reference-class-planning-poker, P36 calibration-tournament, P37 ",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0043/fixtures/protocols.json",
   "claim": "Fixture FORECASTING count is 5 and the id set equals the catalog named set; a GENERATIVE distractor is present so counting all records would not equal 5.",
   "mechanism": "count records where family==FORECASTING; compare id set to catalog named set",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:329",
   "claim": "Inherited catalogue status is DISCOVERY; as-written resolution_criterion and scoring_rule are therefore treated as null, not as fields we pretended to read from an absent file.",
   "mechanism": "read R-A09 evidence field; do not invent library bytes",
   "snippet": "\"evidence\": \"skills/council/SKILL.md 6,346 B, frontmatter origin: ECC, roles Architect/Skeptic/Pragmatist/Critic, no CouncilSpec, no schema, no runtime. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json \u2192 58/72 with \\\"status\\\": \\\"DISCOVERY - no protoco",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0043/runtime.py",
   "claim": "Resolvability check is silent on five known-good forecasts and fires on five planted-bad forecasts; scoring actually returns numeric Brier/CRPS/log-loss on the known-good set.",
   "mechanism": "forecast_issues() + score_forecast() on fixtures",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/ARC-0003/samples.json",
   "claim": "Library file 12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree.",
   "mechanism": "Path.is_file on library candidates plus prior ARC sample on_this_tree=false",
   "snippet": "on_this_tree: false",
   "verdict": "REFUTED"
  }
 ],
 "family_census": {
  "disagreements": [],
  "expected_n": 5,
  "family": "FORECASTING",
  "ok": true,
  "signal1_catalog_named": {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:36433",
   "count": 5,
   "members": [
    {
     "id": "P33",
     "slug": "prediction-tournament"
    },
    {
     "id": "P34",
     "slug": "scenario-planning"
    },
    {
     "id": "P35",
     "slug": "reference-class-planning-poker"
    },
    {
     "id": "P36",
     "slug": "calibration-tournament"
    },
    {
     "id": "P37",
     "slug": "pairwise-comparison"
    }
   ],
   "snippet": "\"question_or_target\": \"Ranging over exactly these 5 records, named so no member can fall through a family mis-assignment (P33 prediction-tournament, P34 scenario-planning, P35 reference-class-planning-poker, P36 calibration-tournament, P37 "
  },
  "signal2_fixture": {
   "count": 5,
   "ids": [
    "P33",
    "P34",
    "P35",
    "P36",
    "P37"
   ],
   "path": "command-center/p2-wave/probes/CNL-0043/fixtures/protocols.json",
   "total_records_including_distractors": 6
  },
  "signal3_live_library": {
   "count": null,
   "ids": [],
   "note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. Family membership is taken from the catalog named-member clause and the local fixture, not from invented library bytes.",
   "path": null,
   "present": false
  }
 },
 "kind": "council-design-note",
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0043/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 8000,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0043/probe1_family_schedules.py",
   "id": "probe1",
   "role": "family-census-and-schedules"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0043/probe2_both_states.py",
   "id": "probe2",
   "role": "both-states-resolvability"
  }
 ],
 "negative_controls": [
  {
   "id": "NC-planted-unresolvable-forecasts",
   "observed": "On the planted-bad fixture the resolvability check FIRES: it returns unresolvable_ids=['F-P33-U1', 'F-P34-U1', 'F-P35-U1', 'F-P36-U1', 'F-P37-U1'] with issues {'F-P33-U1': ['resolution_source'], 'F-P34-U1': ['proposition_kind:not-a-resolvable-forecast'], 'F-P35-U1': ['item_status:not-completed'], 'F-P36-U1': ['resolution_time'], 'F-P37-U1': ['observed_choice_or_ground_truth']}. That is the state the check is meant to reject (missing source/time/completion/ground-truth, or a scenario narrative treated as a forecast).",
   "on_state": "planted-bad forecast fixture (missing source/time, narrative as forecast, incomplete item, pair without ground truth)"
  },
  {
   "id": "NC-family-misassignment",
   "observed": "On a planted family-misassignment of P33 the census FIRES: FORECASTING count becomes 4 (want 5). The check is meant to reject a member falling through a family mis-assignment.",
   "on_state": "FORECASTING member relabelled so it falls out of the family count"
  }
 ],
 "protocols": [
  {
   "as_written": {
    "citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
    "resolution_criterion": null,
    "scoring_rule": null,
    "status": "DISCOVERY - no protocol here has been executed",
    "turn_schedule": null
   },
   "family": "FORECASTING",
   "id": "P33",
   "record_id": "P33",
   "resolution_criterion": "Lookup observable_id at resolution_time from resolution_source. The returned value must be a member of outcome_space. The lookup yields a one-hot vector over outcome_space. A missing source, missing time, empty outcome_space, or a value outside outcome_space is UNRESOLVABLE, not scored as 0.5.",
   "schedule": {
    "as_written_missing": [
     "resolution_criterion",
     "scoring_rule",
     "turn_schedule"
    ],
    "id": "P33",
    "missing_element": null,
    "scoring_id": "brier",
    "turn_count": 5,
    "verdict": "EXECUTABLE"
   },
   "scoring_id": "brier",
   "scoring_rule": "Brier score: sum_k (p_k - y_k)^2 over outcome_space, y one-hot of the resolved outcome. Lower is better. Range [0, 2] for binary.",
   "slug": "prediction-tournament",
   "turn_schedule": {
    "turns": [
     {
      "action": "publish_questions",
      "halt_when": null,
      "id": "T1",
      "reads": [
       "question_bank"
      ],
      "role": "moderator",
      "writes": [
       "open_forecasts"
      ]
     },
     {
      "action": "submit_probability_vector",
      "halt_when": {
       "collection": "open_forecasts",
       "op": "forall",
       "pred": {
        "op": "has_submission"
       }
      },
      "id": "T2",
      "reads": [
       "open_forecasts"
      ],
      "role": "forecaster",
      "writes": [
       "forecasts"
      ]
     },
     {
      "action": "freeze_submissions",
      "halt_when": null,
      "id": "T3",
      "reads": [
       "forecasts"
      ],
      "role": "moderator",
      "writes": [
       "frozen_forecasts"
      ]
     },
     {
      "action": "lookup_outcome",
      "halt_when": {
       "collection": "frozen_forecasts",
       "op": "forall",
       "pred": {
        "op": "resolved"
       }
      },
      "id": "T4",
      "reads": [
       "frozen_forecasts",
       "resolution_source"
      ],
      "role": "resolver",
      "writes": [
       "resolved_outcomes"
      ]
     },
     {
      "action": "brier",
      "halt_when": {
       "args": [
        {
         "op": "resolved"
        },
        {
         "op": "scored"
        }
       ],
       "op": "all"
      },
      "id": "T5",
      "reads": [
       "frozen_forecasts",
       "resolved_outcomes"
      ],
      "role": "scorer",
      "writes": [
       "scores"
      ]
     }
    ]
   }
  },
  {
   "as_written": {
    "citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
    "resolution_criterion": null,
    "scoring_rule": null,
    "status": "DISCOVERY - no protocol here has been executed",
    "turn_schedule": null
   },
   "family": "FORECASTING",
   "id": "P34",
   "record_id": "P34",
   "resolution_criterion": "A scenario narrative is not a proposition and does not resolve. Each attached signpost is a binary or multinomial forecast and resolves under the P33 criterion (observable, source, time, outcome_space). Scoring the narrative itself is forbidden.",
   "schedule": {
    "as_written_missing": [
     "resolution_criterion",
     "scoring_rule",
     "turn_schedule"
    ],
    "id": "P34",
    "missing_element": null,
    "scoring_id": "none-on-narrative",
    "turn_count": 6,
    "verdict": "EXECUTABLE"
   },
   "scoring_id": "none-on-narrative",
   "scoring_rule": "No score on the scenario narrative. Each resolvable signpost is Brier-scored. A narrative submitted as if it were a forecast is UNRESOLVABLE.",
   "slug": "scenario-planning",
   "turn_schedule": {
    "turns": [
     {
      "action": "elicit_drivers",
      "halt_when": null,
      "id": "T1",
      "reads": [
       "brief"
      ],
      "role": "facilitator",
      "writes": [
       "drivers"
      ]
     },
     {
      "action": "choose_scenario_axes",
      "halt_when": null,
      "id": "T2",
      "reads": [
       "drivers"
      ],
      "role": "participant",
      "writes": [
       "axes"
      ]
     },
     {
      "action": "write_narratives",
      "halt_when": null,
      "id": "T3",
      "reads": [
       "axes"
      ],
      "role": "participant",
      "writes": [
       "scenarios"
      ]
     },
     {
      "action": "attach_signposts",
      "halt_when": null,
      "id": "T4",
      "reads": [
       "scenarios"
      ],
      "role": "participant",
      "writes": [
       "signposts"
      ]
     },
     {
      "action": "resolve_signposts",
      "halt_when": {
       "op": "signposts_resolved"
      },
      "id": "T5",
      "reads": [
       "signposts",
       "resolution_source"
      ],
      "role": "resolver",
      "writes": [
       "resolved_signposts"
      ]
     },
     {
      "action": "brier_signposts_only",
      "halt_when": {
       "args": [
        {
         "op": "signposts_resolved"
        },
        {
         "op": "scored"
        }
       ],
       "op": "all"
      },
      "id": "T6",
      "reads": [
       "resolved_signposts"
      ],
      "role": "scorer",
      "writes": [
       "scores"
      ]
     }
    ]
   }
  },
  {
   "as_written": {
    "citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
    "resolution_criterion": null,
    "scoring_rule": null,
    "status": "DISCOVERY - no protocol here has been executed",
    "turn_schedule": null
   },
   "family": "FORECASTING",
   "id": "P35",
   "record_id": "P35",
   "resolution_criterion": "When item_id reaches completion, actual_accessor returns a scalar (hours or cost) in the units of bin_edges. Incomplete items are UNRESOLVABLE, not scored as zero. A missing reference_class name is a protocol defect: the round may still run, but the estimate is flagged unanchored.",
   "schedule": {
    "as_written_missing": [
     "resolution_criterion",
     "scoring_rule",
     "turn_schedule"
    ],
    "id": "P35",
    "missing_element": null,
    "scoring_id": "crps",
    "turn_count": 7,
    "verdict": "EXECUTABLE"
   },
   "scoring_id": "crps",
   "scoring_rule": "Continuous ranked probability score of the submitted histogram (bins + bin_edges) against the scalar actual. Lower is better.",
   "slug": "reference-class-planning-poker",
   "turn_schedule": {
    "turns": [
     {
      "action": "present_item",
      "halt_when": null,
      "id": "T1",
      "reads": [
       "backlog"
      ],
      "role": "moderator",
      "writes": [
       "item"
      ]
     },
     {
      "action": "name_reference_class",
      "halt_when": null,
      "id": "T2",
      "reads": [
       "item",
       "historical_set"
      ],
      "role": "analyst",
      "writes": [
       "reference_class"
      ]
     },
     {
      "action": "simultaneous_histogram_cards",
      "halt_when": null,
      "id": "T3",
      "reads": [
       "item",
       "reference_class"
      ],
      "role": "participant",
      "writes": [
       "private_cards"
      ]
     },
     {
      "action": "discuss_outliers",
      "halt_when": null,
      "id": "T4",
      "reads": [
       "private_cards"
      ],
      "role": "participant",
      "writes": [
       "discussion"
      ]
     },
     {
      "action": "commit_distribution",
      "halt_when": {
       "collection": "participants",
       "op": "forall",
       "pred": {
        "op": "has_submission"
       }
      },
      "id": "T5",
      "reads": [
       "discussion"
      ],
      "role": "participant",
      "writes": [
       "committed_bins"
      ]
     },
     {
      "action": "read_actual_on_completion",
      "halt_when": {
       "op": "completed"
      },
      "id": "T6",
      "reads": [
       "item",
       "actual_accessor"
      ],
      "role": "resolver",
      "writes": [
       "actual"
      ]
     },
     {
      "action": "crps",
      "halt_when": {
       "args": [
        {
         "op": "completed"
        },
        {
         "op": "scored"
        }
       ],
       "op": "all"
      },
      "id": "T7",
      "reads": [
       "committed_bins",
       "actual"
      ],
      "role": "scorer",
      "writes": [
       "scores"
      ]
     }
    ]
   }
  },
  {
   "as_written": {
    "citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
    "resolution_criterion": null,
    "scoring_rule": null,
    "status": "DISCOVERY - no protocol here has been executed",
    "turn_schedule": null
   },
   "family": "FORECASTING",
   "id": "P36",
   "record_id": "P36",
   "resolution_criterion": "Each bank item resolves independently under the P33 criterion. Ranking uses Brier; the calibration report is expected calibration error over the same resolved bank. Unresolvable items are dropped from both the ranking and the ECE denominator, never filled with a default outcome.",
   "schedule": {
    "as_written_missing": [
     "resolution_criterion",
     "scoring_rule",
     "turn_schedule"
    ],
    "id": "P36",
    "missing_element": null,
    "scoring_id": "brier+ece",
    "turn_count": 5,
    "verdict": "EXECUTABLE"
   },
   "scoring_id": "brier+ece",
   "scoring_rule": "Per-item Brier as in P33. Tournament rank by mean Brier over resolvable items. ECE is reported and does not break ties.",
   "slug": "calibration-tournament",
   "turn_schedule": {
    "turns": [
     {
      "action": "publish_bank",
      "halt_when": null,
      "id": "T1",
      "reads": [
       "question_bank"
      ],
      "role": "moderator",
      "writes": [
       "open_forecasts"
      ]
     },
     {
      "action": "submit_probability_vectors",
      "halt_when": {
       "collection": "open_forecasts",
       "op": "forall",
       "pred": {
        "op": "has_submission"
       }
      },
      "id": "T2",
      "reads": [
       "open_forecasts"
      ],
      "role": "forecaster",
      "writes": [
       "forecasts"
      ]
     },
     {
      "action": "freeze_bank",
      "halt_when": null,
      "id": "T3",
      "reads": [
       "forecasts"
      ],
      "role": "moderator",
      "writes": [
       "frozen_forecasts"
      ]
     },
     {
      "action": "batch_lookup",
      "halt_when": {
       "collection": "frozen_forecasts",
       "op": "forall",
       "pred": {
        "op": "resolved"
       }
      },
      "id": "T4",
      "reads": [
       "frozen_forecasts",
       "resolution_source"
      ],
      "role": "resolver",
      "writes": [
       "resolved_outcomes"
      ]
     },
     {
      "action": "brier_and_ece",
      "halt_when": {
       "args": [
        {
         "op": "resolved"
        },
        {
         "op": "scored"
        }
       ],
       "op": "all"
      },
      "id": "T5",
      "reads": [
       "frozen_forecasts",
       "resolved_outcomes"
      ],
      "role": "scorer",
      "writes": [
       "scores",
       "ece"
      ]
     }
    ]
   }
  },
  {
   "as_written": {
    "citation": "command-center/WORK-UNIT-CATALOG.json items[id=R-A09].evidence",
    "resolution_criterion": null,
    "scoring_rule": null,
    "status": "DISCOVERY - no protocol here has been executed",
    "turn_schedule": null
   },
   "family": "FORECASTING",
   "id": "P37",
   "record_id": "P37",
   "resolution_criterion": "Each pair (a,b) resolves to a winner from observed_choice (elicitation) or ground_truth_winner / ground_truth_ranking (forecast against a ranking). A pair with neither is UNRESOLVABLE. Preference elicitation without ground truth can still halt via observed_choice; it is scored as a recorded choice, not as a world-event forecast.",
   "schedule": {
    "as_written_missing": [
     "resolution_criterion",
     "scoring_rule",
     "turn_schedule"
    ],
    "id": "P37",
    "missing_element": null,
    "scoring_id": "bradley-terry-logloss",
    "turn_count": 6,
    "verdict": "EXECUTABLE"
   },
   "scoring_id": "bradley-terry-logloss",
   "scoring_rule": "Log loss of the submitted P(winner) under a Bradley-Terry forecast vector over {a, b}. Lower is better. If a full ranking exists, Spearman on the recovered ranking is reported and does not replace log loss.",
   "slug": "pairwise-comparison",
   "turn_schedule": {
    "turns": [
     {
      "action": "present_pair",
      "halt_when": null,
      "id": "T1",
      "reads": [
       "pair_queue"
      ],
      "role": "moderator",
      "writes": [
       "current_pair"
      ]
     },
     {
      "action": "choose_or_forecast_winner",
      "halt_when": {
       "collection": "current_pair",
       "op": "forall",
       "pred": {
        "op": "has_submission"
       }
      },
      "id": "T2",
      "reads": [
       "current_pair"
      ],
      "role": "participant",
      "writes": [
       "pair_forecasts"
      ]
     },
     {
      "action": "update_bradley_terry",
      "halt_when": null,
      "id": "T3",
      "reads": [
       "pair_forecasts"
      ],
      "role": "aggregator",
      "writes": [
       "strengths"
      ]
     },
     {
      "action": "next_pair_or_queue_irresolvable",
      "halt_when": {
       "op": "pairs_resolved_or_queued"
      },
      "id": "T4",
      "reads": [
       "pair_queue",
       "pair_forecasts"
      ],
      "role": "moderator",
      "writes": [
       "pair_queue",
       "unresolvable_pairs"
      ]
     },
     {
      "action": "apply_ground_truth",
      "halt_when": null,
      "id": "T5",
      "reads": [
       "pair_forecasts",
       "ground_truth_ranking"
      ],
      "role": "resolver",
      "writes": [
       "resolved_pairs"
      ]
     },
     {
      "action": "bradley_terry_logloss",
      "halt_when": {
       "args": [
        {
         "op": "pairs_resolved_or_queued"
        },
        {
         "op": "scored"
        }
       ],
       "op": "all"
      },
      "id": "T6",
      "reads": [
       "resolved_pairs"
      ],
      "role": "scorer",
      "writes": [
       "scores"
      ]
     }
    ]
   }
  }
 ],
 "question": "Ranging over exactly these 5 records, named so no member can fall through a family mis-assignment (P33 prediction-tournament, P34 scenario-planning, P35 reference-class-planning-poker, P36 calibration-tournament, P37 pairwise-comparison): For each of the 5 FORECASTING protocol records, what is the resolution criterion and the scoring rule, and which forecasts in the catalogue are unresolvable as written?",
 "required_fix": null,
 "reviewer": {
  "control_executed": true,
  "independent": true,
  "method": "Mechanical: regex-extract P-ids from catalog question_or_target; count fixture records with family==FORECASTING; apply runtime.forecast_issues to the forecast fixture without reading the author's answer string. Disagreement in either number blocks. Both-states: SILENT on known-good, FIRES on planted-bad, recorded verbatim in probe2-both-states.raw.json.",
  "reviewer_id": "CNL-0043-probe2-retabulation",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "schema_note": "Catalog output_schema is a GENERATED SHIM whose $ref points at https://ast-integrate.invalid/...; validating against it tries the network and does not constrain this note. This unit validates against the per-unit schema. Overwriting the shared catalog schema would be a sibling rebuild circle.",
 "scored_known_good": [
  {
   "brier": 0.18000000000000002,
   "id": "F-P33-1",
   "rule": "brier",
   "scored": true
  },
  {
   "brier": 0.32000000000000006,
   "id": "F-P34-1",
   "rule": "none-on-narrative",
   "scored": true
  },
  {
   "crps": 1.626666666666669,
   "id": "F-P35-1",
   "rule": "crps",
   "scored": true
  },
  {
   "brier": 0.07999999999999999,
   "id": "F-P36-1",
   "rule": "brier+ece",
   "scored": true
  },
  {
   "id": "F-P37-1",
   "logloss": 0.4307829160924542,
   "rule": "bradley-terry-logloss",
   "scored": true
  }
 ],
 "sentinel": "SUCCESS:CNL-0043",
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "The five named P-ids come from the work-unit question, not from a live read of 12-COUNCIL-PROTOCOLS-AND-PRESETS.json. If that file is later placed on disk and its FORECASTING set differs from {P33,P34,P35,P36,P37}, signal 3 must fail closed and this note must be rewritten from those bytes. Until then, refusing to invent library records is the honest move; the catalog anti-misassignment clause is the membership list this unit is allowed to range over.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0043/probe1_family_schedules.py",
   "id": "T1-family-schedules",
   "name": "Every FORECASTING record has an executable turn schedule; count equals family n",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0043/probe2_both_states.py",
   "id": "T2-both-states-unresolvable",
   "name": "Resolvability FIRES on planted-bad and is SILENT on known-good; independent recount agrees",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:53:30Z"
 },
 "title": "Executable runtime semantics for the 5 FORECASTING protocols",
 "unit_id": "CNL-0043",
 "unresolvable_as_written": {
  "forecast_count": 5,
  "forecast_ids": [
   "F-P33-U1",
   "F-P34-U1",
   "F-P35-U1",
   "F-P36-U1",
   "F-P37-U1"
  ],
  "issues_by_id": {
   "F-P33-U1": [
    "resolution_source"
   ],
   "F-P34-U1": [
    "proposition_kind:not-a-resolvable-forecast"
   ],
   "F-P35-U1": [
    "item_status:not-completed"
   ],
   "F-P36-U1": [
    "resolution_time"
   ],
   "F-P37-U1": [
    "observed_choice_or_ground_truth"
   ]
  },
  "protocol_fields": {
   "all_five_lack_resolution_and_scoring": true,
   "basis": "Fixture as_written.resolution_criterion and scoring_rule are null. R-A09 catalogue evidence records status 'DISCOVERY - no protocol here has been executed' for the inherited 58 protocol records. Live library file absent; this is not a claim that those bytes were read.",
   "ids": [
    "P33",
    "P34",
    "P35",
    "P36",
    "P37"
   ]
  },
  "resolvable_after_this_design": [
   "F-P33-1",
   "F-P34-1",
   "F-P35-1",
   "F-P36-1",
   "F-P37-1"
  ]
 }
}
