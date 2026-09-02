{
  "unit_id": "CNL-0112",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0112",
  "title": "Forecasting and expert-elicitation preset with a proper scoring rule",
  "question": "Which proper scoring rule scores the forecasts, what is the resolution source and date, and what does the preset do with a forecast that can never resolve?",
  "kind": "council-preset-design",
  "schema_version": 1,
  "preset": {
    "id": "council.preset.forecast-elicit.proper-score",
    "kind": "typed_delta",
    "relation": "extends",
    "base_spec": {
      "id": "councilspec.v2.reconstructed-base",
      "version": "2.0.0"
    },
    "extends_c_ids": [
      "C-M01"
    ],
    "extends_c_ids_basis": "WORK-UNIT-CATALOG.json CNL-0002 evidence_requirement names C-M01 as a catalogued 20-key preset; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json bytes were not read on this worktree.",
    "binds_protocols": [
      "P33",
      "P35",
      "P36"
    ],
    "binds_protocols_basis": "CNL-0043 names the FORECASTING family as P33 prediction-tournament, P34 scenario-planning, P35 reference-class-planning-poker, P36 calibration-tournament, P37 pairwise-comparison. This preset binds P33+P35+P36. P34 is optional. P37 is excluded: pairwise option ranking is not a probability forecast and cannot take a proper score.",
    "roles": [
      {
        "id": "elicitor",
        "obligation": "emit only items that carry a named resolution source, date, and checkable criterion"
      },
      {
        "id": "forecaster",
        "obligation": "report probabilities; updates may use the full distribution and arguments, never the reported median alone"
      },
      {
        "id": "aggregator",
        "obligation": "combine credences with a logarithmic opinion pool, not a majority vote on a point forecast"
      },
      {
        "id": "resolution_clerk",
        "obligation": "ACCEPT or REJECT each item at emission; cannot be overridden to score an UNSCOREABLE item"
      },
      {
        "id": "calibration_analyst",
        "obligation": "score only SCOREABLE resolved items; keep an UNSCOREABLE tally that never enters the score"
      },
      {
        "id": "anti_herding_skeptic",
        "obligation": "flag variance collapse across Delphi rounds when the evidence hash is unchanged"
      }
    ],
    "voting": {
      "method": "logarithmic_opinion_pool",
      "quorum": 3,
      "note": "The forecast number is a pool of probabilities, not a role-majority."
    },
    "stopping": {
      "max_rounds": 6,
      "expression": "stop when every emitted item is SCOREABLE or UNSCOREABLE AND delphi_round >= 2 AND (delphi_round >= max_rounds OR herding_flag OR resolution_clerk.batch_closed)",
      "on_timeout": "close_batch_with_unscored_remainder_as_UNSCOREABLE",
      "on_unresolved": "UNSCOREABLE"
    },
    "protocol_schedule": [
      "P35",
      "P33",
      "P36"
    ],
    "topology": {
      "id": "delphi-controlled-feedback",
      "from_unit": "CNL-0035",
      "feedback_mode": "full_distribution_and_arguments",
      "forbidden_feedback": "median_only",
      "reason": "Median-only feedback produces regression to the reported median (herding), not genuine revision. Full distribution plus arguments is the feedback this preset returns. Detection of herding is a separate variance+evidence-hash check; distribution feedback does not by itself prove the panel is not herding."
    },
    "scoring": {
      "primary_rule": "logarithmic",
      "primary_rule_status": "strictly_proper",
      "secondary_rule": "brier",
      "secondary_rule_status": "strictly_proper_not_local",
      "rejected_rule": "linear_probability_score",
      "rejected_rule_status": "improper",
      "citation": "Gneiting and Raftery 2007 JASA: Strictly Proper Scoring Rules, Prediction, and Estimation. Log is local and strictly proper; Brier is strictly proper and bounded; linear is not proper."
    },
    "resolution": {
      "require_source_and_date": true,
      "source_must_be_named": true,
      "date_format": "ISO-8601",
      "criterion_must_be_checkable": true
    },
    "unresolvable_policy": "REJECT-UNSCOREABLE-at-emission",
    "unresolvable_disposition": "UNSCOREABLE",
    "calibration_alignment": {
      "from_unit": "CNL-0074",
      "deferred_resolution_remains_scoreable_without_session": true,
      "council_with_no_resolvable_outcome": "UNSCOREABLE",
      "unscoreable_never_counted_as_calibrated": true
    },
    "editable_dials": [
      "stopping.max_rounds",
      "roles.forecaster_count",
      "scoring.report_secondary_brier",
      "protocol_schedule.include_P34"
    ],
    "non_editable_dials": [
      "scoring.primary_rule",
      "unresolvable_policy",
      "resolution.require_source_and_date",
      "topology.feedback_mode"
    ],
    "default_binding": "FORECASTING",
    "on_base_bump": "migrate_or_list_unmigratable"
  },
  "nearest_sibling": {
    "id": "council.preset.catalog-class.editable",
    "named": true,
    "source": "library 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; body transcribes catalog-cited axes from command-center/p2-wave/probes/ARC-0003/samples.json (anti_failure/audit/voting/consensus/stopping). Not library bytes.",
    "library_bytes_read": false,
    "catalog_cited_c_id_shape": "C-M01",
    "why_nearest": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent. The only on-tree transcribed preset is council.preset.catalog-class.editable from ARC-0003 samples.json. A name-only clone of that sibling would be a mechanism-duplicate; this preset differs on roster, vote, stop, bound protocols, scoring, and unresolvable policy."
  },
  "answers": {
    "scoring_rule": "logarithmic",
    "scoring_rule_secondary": "brier",
    "scoring_rule_why": "Logarithmic score is strictly proper and local (Gneiting & Raftery 2007). A reporter whose expected score is maximized only by stating their true credence cannot profit by hedging. Brier is reported as a bounded secondary. Linear probability score is rejected: it is not proper and rewards extremist 0/1 reports.",
    "resolution_source_rule": "Named, checkable source required at emission. Missing source => REJECT.",
    "resolution_date_rule": "ISO-8601 resolution date required at emission. Missing date => REJECT.",
    "never_resolves": "REJECT at emission; disposition UNSCOREABLE; excluded from both the numerator and the denominator of log/Brier; counted only in the UNSCOREABLE tally (CNL-0074: a council with no resolvable outcome is UNSCOREABLE, never counted as calibrated)."
  },
  "instantiation": {
    "task_id": "fixture.forecast.elicit.CNL-0112",
    "roster_ids": [
      "elicitor",
      "forecaster",
      "aggregator",
      "resolution_clerk",
      "calibration_analyst",
      "anti_herding_skeptic"
    ],
    "protocol_schedule": [
      "P35",
      "P33",
      "P36"
    ],
    "voting": {
      "method": "logarithmic_opinion_pool",
      "quorum": 3,
      "note": "The forecast number is a pool of probabilities, not a role-majority."
    },
    "stopping": {
      "max_rounds": 6,
      "expression": "stop when every emitted item is SCOREABLE or UNSCOREABLE AND delphi_round >= 2 AND (delphi_round >= max_rounds OR herding_flag OR resolution_clerk.batch_closed)",
      "on_timeout": "close_batch_with_unscored_remainder_as_UNSCOREABLE",
      "on_unresolved": "UNSCOREABLE"
    },
    "accepted_ids": [
      "F1",
      "F2"
    ],
    "rejected_ids": [
      "F3"
    ],
    "unscoreable_tally": 1,
    "scoreable_tally": 2,
    "profile": {
      "roles": [
        "elicitor",
        "forecaster",
        "aggregator",
        "resolution_clerk",
        "calibration_analyst",
        "anti_herding_skeptic"
      ],
      "voting": "logarithmic_opinion_pool",
      "stopping": "stop when every emitted item is SCOREABLE or UNSCOREABLE AND delphi_round >= 2 AND (delphi_round >= max_rounds OR herding_flag OR resolution_clerk.batch_closed)",
      "protocol_schedule": [
        "P35",
        "P33",
        "P36"
      ],
      "scoring": "logarithmic",
      "unresolvable_policy": "REJECT-UNSCOREABLE-at-emission"
    }
  },
  "sibling_instantiation": {
    "task_id": "fixture.forecast.elicit.CNL-0112",
    "roster_ids": [
      "Architect",
      "Skeptic",
      "Pragmatist",
      "Critic"
    ],
    "protocol_schedule": [],
    "voting": {
      "rule": "unanimous-or-record-dissent",
      "quorum": 4
    },
    "stopping": {
      "max_rounds": 8,
      "on_timeout": "halt",
      "on_unresolved": "BLOCKED",
      "expression": "rounds >= 8 OR unresolved -> BLOCKED"
    },
    "profile": {
      "roles": [
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "voting": "unanimous-or-record-dissent",
      "stopping": "rounds >= 8 OR unresolved -> BLOCKED",
      "protocol_schedule": [],
      "scoring": null,
      "unresolvable_policy": "BLOCKED-on-unresolved"
    },
    "differ_axes": [
      "roles",
      "voting",
      "stopping",
      "protocol_schedule",
      "scoring",
      "unresolvable_policy"
    ]
  },
  "proper_scoring_fixture": {
    "p_true": 0.7,
    "reports": {
      "calibrated": 0.7,
      "hedge": 0.5,
      "extremist": 1.0
    },
    "log": {
      "calibrated": -0.6108643020548935,
      "hedge": -0.6931471805599453,
      "extremist": -8.289312971368709,
      "prefers_calibrated_to_hedge": true,
      "prefers_calibrated_to_extremist": true
    },
    "brier_lower_better": {
      "calibrated": 0.21000000000000002,
      "hedge": 0.25,
      "calibrated_better_than_hedge": true
    },
    "linear_improper": {
      "calibrated": 0.58,
      "hedge": 0.5,
      "extremist": 0.7,
      "prefers_extremist_to_calibrated": true
    },
    "log_is_strictly_proper_on_this_fixture": true,
    "linear_is_improper_on_this_fixture": true
  },
  "herding_control_same_evidence_median_collapse": true,
  "tests": [
    {
      "id": "instantiate-fixture-task",
      "result": "PASS",
      "roster_ids": [
        "elicitor",
        "forecaster",
        "aggregator",
        "resolution_clerk",
        "calibration_analyst",
        "anti_herding_skeptic"
      ],
      "protocol_schedule": [
        "P35",
        "P33",
        "P36"
      ],
      "voting_method": "logarithmic_opinion_pool",
      "stopping_expression": "stop when every emitted item is SCOREABLE or UNSCOREABLE AND delphi_round >= 2 AND (delphi_round >= max_rounds OR herding_flag OR resolution_clerk.batch_closed)"
    },
    {
      "id": "nearest-sibling-differential",
      "result": "PASS",
      "sibling_id": "council.preset.catalog-class.editable",
      "differ_axes": [
        "roles",
        "voting",
        "stopping",
        "protocol_schedule",
        "scoring",
        "unresolvable_policy"
      ]
    },
    {
      "id": "jsonschema-Draft202012Validator",
      "result": "PASS",
      "good_error_count": 0,
      "invalid_error_count": 11
    },
    {
      "id": "unresolvable-rejected-at-emission",
      "result": "PASS",
      "accepted_ids": [
        "F1",
        "F2"
      ],
      "rejected_ids": [
        "F3"
      ]
    }
  ],
  "negative_controls": [
    {
      "id": "NC-unresolvable-emission",
      "rejects": "a forecast missing resolution_source or resolution_date, or whose criterion_class is preference / metaphysical / unbounded_ever",
      "on_that_state": "classify_item returns disposition=REJECT score_class=UNSCOREABLE; instantiate omits the item from accepted_ids; a resolvable sibling item in the same batch is ACCEPTED",
      "verbatim": "REJECT:UNSCOREABLE F3 reasons=['missing_resolution_source', 'missing_resolution_date', 'preference']"
    },
    {
      "id": "NC-schema-vacuity",
      "rejects": "an artifact with required key preset removed",
      "on_that_state": "Draft202012Validator error count >= 1",
      "verbatim": "validator.iter_errors(mutant_without_preset) is non-empty"
    },
    {
      "id": "NC-linear-score",
      "rejects": "the claim that any reported score is proper",
      "on_that_state": "under linear score, extremist q=1 beats calibrated q=p*; under log, calibrated wins against both hedge and extremist",
      "verbatim": "linear_prefers_extremist=True log_prefers_calibrated=True"
    },
    {
      "id": "NC-silent-non-editable-override",
      "rejects": "an override of scoring.primary_rule (a non-editable dial)",
      "on_that_state": "apply_overrides returns accepted=False reason=silent-override-of-non-editable-dial",
      "verbatim": "REJECT silent-override-of-non-editable-dial dial=scoring.primary_rule"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0112-probe2-sibling-differential",
    "verdict": "PASS",
    "independent": true,
    "scope_not_agreement": true,
    "method": "Re-instantiates this preset and the named sibling against the same fixture and diffs the profile. Does not accept the author's nearest-sibling sentence as evidence."
  },
  "library": {
    "candidates": [
      "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ],
    "found": [],
    "on_this_worktree": false,
    "presets_compared_from_disk": 0
  },
  "dependencies_disclosed": {
    "CNL-0101": "preset is a typed delta (kind=typed_delta), not a fork; silent non-editable override rejected",
    "CNL-0035": "Delphi feedback is full distribution + arguments, never median-only; herding is variance collapse with unchanged evidence hash",
    "CNL-0043": "binds FORECASTING P33/P35/P36; P37 excluded because pairwise ranking is not a probability forecast",
    "CNL-0074": "UNSCOREABLE items never counted as calibrated; deferred resolution remains scoreable without the original session"
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0112-forecasting-and-expert-elicitation-preset-with-a-proper-sc.md",
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-preset.schema.json",
      "role": "schema"
    }
  ],
  "residual_unknowns": [
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent, so a nearest-neighbour among the cited 72 presets cannot be computed from library bytes. The named sibling is the on-tree catalog transcription. If the library lands, re-run differ_axes against every preset record and replace this sibling if a closer neighbour exists."
  ]
}
