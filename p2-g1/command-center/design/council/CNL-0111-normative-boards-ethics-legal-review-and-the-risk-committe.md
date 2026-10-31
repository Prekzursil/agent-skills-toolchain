{
  "answer": "Ethics/legal review (C15) asks may_we. Its evidence bar is cited-instrument-or-fail-closed: a pin to a statute, licence clause, policy or prohibited-use record is required, and absence of a permit is PROHIBITED, not a yes. Outcomes are PERMITTED, PERMITTED-CONDITIONAL, PROHIBITED, IRREDUCIBLE-DISAGREEMENT. Vote is unanimity (any no vetoes permission); stop is may_we == true OR minority_report_filed == true. Risk committee (C16) asks how_exposed. Its evidence bar is named-residual-plus-scenario-envelope: ACCEPT without a named residual is rejected as PARK-UNQUANTIFIED. Outcomes are ACCEPT, MITIGATE, TRANSFER, AVOID, PARK-UNQUANTIFIED. Vote is supermajority; stop is exposure_accepted == true AND residual_risk_named == true. The types are not commensurable. When legal says PROHIBITED and risk says ACCEPT, action_authorized is false: risk ACCEPT is preserved as an exposure judgment and is not an override. Override path is re-scope the option and re-run both boards. Fixture T-CNL-0111-01 (legal=PROHIBITED, risk=ACCEPT) action_authorized=False. Nearest sibling of C15 (excluding owned ids) is C05 release-go-no-go at distance 0.55; C16 nearest is C04 plan-critique-board at distance 0.6166666666666667; C15 vs C16 distance=0.9642857142857143. Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is ABSENT; siblings are from the CNL-0102 catalog-cited reconstruction. SUCCESS:CNL-0111",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0111-normative-boards-ethics-legal-review-and-the-risk-committe.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-preset.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0111/boards.py",
      "role": "presets"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0111/compose.py",
      "role": "composition-rule"
    }
  ],
  "catalog_schema_note": "command-center/schema/council-preset.schema.json is a generated shim ($ref to generic_report) with no $defs.preset; record and envelope validation uses the unit-local schema.",
  "cloud_ok": false,
  "completion_sentinel": "SUCCESS:CNL-0111",
  "composition_rule": {
    "boards_always_run": true,
    "formula": "action_authorized := (legal in {PERMITTED, PERMITTED-CONDITIONAL}) AND (risk in {ACCEPT, MITIGATE, TRANSFER} with residual named)",
    "legal_no_risk_accept": "action_authorized=false; preserve both records",
    "name": "permission-gate-dominates-action-authorization",
    "override_path": "re-scope the option and re-run both boards; owner cannot overlay risk ACCEPT onto a legal PROHIBITED"
  },
  "declared_metric": {
    "chair_beats_when": "name-reading would treat ethics/legal and risk as interchangeable normative boards or let risk ACCEPT outvote a legal NO; the algorithm keeps disjoint outcome types and a permission gate",
    "formula": "sibling distance = mean of (1-Jaccard_protocols, 1-Jaccard_roles, vote_mismatch, stop_mismatch); below_threshold iff distance==0; composition gate is action_authorized as above",
    "name": "4-tuple-plus-composition-gate"
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:39889",
      "claim": "Catalog unit CNL-0111 asks for distinct evidence standards and outcome types for may-we vs how-exposed, and a rule for legal NO + risk ACCEPT.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0111/boards.py:23",
      "claim": "C15 uses unanimity and a may_we stopping expression; C16 uses supermajority and residual_risk_named. Those 4-tuples are locked to the CNL-0102 reconstruction of C15/C16.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0111/compose.py:29",
      "claim": "Honest composer returns false whenever legal outcome is outside PERMITTED / PERMITTED-CONDITIONAL, so legal PROHIBITED vetoes the option even if risk ACCEPT.",
      "verdict": "CONFIRMED"
    }
  ],
  "executable_schema": "command-center/p2-wave/probes/CNL-0111/council-preset.schema.json",
  "fixture_conflict": {
    "action_authorized": false,
    "conflict_legal_no_risk_accept": true,
    "legal_outcome": "PROHIBITED",
    "preserved_legal": {
      "board": "ethics-legal-review",
      "may_we": false,
      "minority_report_filed": false,
      "outcome": "PROHIBITED",
      "pin": "example-competitor ToS section 5 automated-access prohibition",
      "reason": "cited-instrument-prohibits"
    },
    "preserved_risk": {
      "board": "risk-committee",
      "expected_loss_usd": 12000,
      "outcome": "ACCEPT",
      "reason": "named-residual-scored",
      "residual": "ToS civil claim plus IP-block operational loss",
      "residual_risk_named": true
    },
    "risk_outcome": "ACCEPT",
    "rule": "action_authorized := (legal in {PERMITTED, PERMITTED-CONDITIONAL}) AND (risk in {ACCEPT, MITIGATE, TRANSFER} with residual named). Legal PROHIBITED or IRREDUCIBLE-DISAGREEMENT vetoes the option; the risk record is preserved and is not an override. Override path is re-scope the option and re-run both boards, not overlay risk ACCEPT on a legal NO."
  },
  "fixture_known_good": {
    "action_authorized": true,
    "conflict_legal_no_risk_accept": false,
    "legal_outcome": "PERMITTED",
    "preserved_legal": {
      "board": "ethics-legal-review",
      "may_we": true,
      "minority_report_filed": false,
      "outcome": "PERMITTED",
      "pin": "internal-licence clause 2.1 grant of extract-and-publish",
      "reason": "cited-instrument-permits"
    },
    "preserved_risk": {
      "board": "risk-committee",
      "expected_loss_usd": 400,
      "outcome": "ACCEPT",
      "reason": "named-residual-scored",
      "residual": "residual reputational exposure if attribution footer is dropped",
      "residual_risk_named": true
    },
    "risk_outcome": "ACCEPT",
    "rule": "action_authorized := (legal in {PERMITTED, PERMITTED-CONDITIONAL}) AND (risk in {ACCEPT, MITIGATE, TRANSFER} with residual named). Legal PROHIBITED or IRREDUCIBLE-DISAGREEMENT vetoes the option; the risk record is preserved and is not an override. Override path is re-scope the option and re-run both boards, not overlay risk ACCEPT on a legal NO."
  },
  "information_flow": {
    "chair_led": "Two boards run independently (legal always records may_we; risk always records exposure). A composer reads both typed outcomes and cannot rewrite either record.",
    "flat": "A single mixed board votes once on a blended 'should we' question. Legal no and risk accept collapse into one ballot.",
    "what_changes": "Disagreement becomes a preserved pair plus a boolean action_authorized, not a blended vote."
  },
  "instantiations": [
    {
      "evidence_bar": "cited-instrument-or-fail-closed",
      "outcome_types": [
        "PERMITTED",
        "PERMITTED-CONDITIONAL",
        "PROHIBITED",
        "IRREDUCIBLE-DISAGREEMENT"
      ],
      "preset_id": "C15",
      "preset_name": "ethics-legal-review",
      "protocol_schedule": [
        "P14",
        "P19",
        "P56"
      ],
      "question": "may_we",
      "roster": [
        "Judge",
        "Reviewer",
        "Skeptic",
        "Clerk"
      ],
      "stopping_expression": "may_we == true OR minority_report_filed == true",
      "task_id": "T-CNL-0111-01",
      "voting_method": "unanimity"
    },
    {
      "evidence_bar": "named-residual-plus-scenario-envelope",
      "outcome_types": [
        "ACCEPT",
        "MITIGATE",
        "TRANSFER",
        "AVOID",
        "PARK-UNQUANTIFIED"
      ],
      "preset_id": "C16",
      "preset_name": "risk-committee",
      "protocol_schedule": [
        "P39",
        "P40",
        "P43"
      ],
      "question": "how_exposed",
      "roster": [
        "Forecaster",
        "Skeptic",
        "Owner",
        "Chair"
      ],
      "stopping_expression": "exposure_accepted == true AND residual_risk_named == true",
      "task_id": "T-CNL-0111-01",
      "voting_method": "supermajority"
    }
  ],
  "measured": {
    "c15_c16_distance": 0.9642857142857143,
    "library_preset_count": 72,
    "library_source": "catalog-cited-reconstruction",
    "nearest_sibling_legal": {
      "distance": 0.55,
      "id": "C15",
      "neighbour_id": "C05",
      "neighbour_name": "release-go-no-go",
      "neighbour_protocols": [
        "P18",
        "P19",
        "P46"
      ],
      "neighbour_roles": [
        "Owner",
        "Reviewer",
        "Judge",
        "Clerk"
      ],
      "neighbour_stop": "two_key_consent == true OR rfc_last_call_elapsed",
      "neighbour_vote": "unanimity",
      "same_signature": false
    },
    "nearest_sibling_risk": {
      "distance": 0.6166666666666667,
      "id": "C16",
      "neighbour_id": "C04",
      "neighbour_name": "plan-critique-board",
      "neighbour_protocols": [
        "P46",
        "P39",
        "P42"
      ],
      "neighbour_roles": [
        "Reviewer",
        "Pragmatist",
        "Skeptic",
        "Chair"
      ],
      "neighbour_stop": "key_assumptions_checked == true AND max_rounds == 8",
      "neighbour_vote": "supermajority",
      "same_signature": false
    },
    "original_library_present": false,
    "schema_invalid_error_count": 6,
    "schema_record_error_count": 0
  },
  "negative_controls": [
    {
      "fires_on_planted_bad": true,
      "id": "risk-accept-overrides-legal-no",
      "known_good": "honest composer action_authorized=false on T-CNL-0111-01",
      "rejects": "a composer that authorizes when legal=PROHIBITED and risk=ACCEPT",
      "silent_on_known_good": true,
      "verbatim": "The check REJECTS a composer that authorizes action when the legal board outcome is PROHIBITED and the risk committee outcome is ACCEPT (risk-accept-overrides-legal-no). It is SILENT on the honest composer, which records both outcomes and sets action_authorized=false."
    }
  ],
  "not_checked": [
    {
      "claim": "Byte-level C15/C16 records in original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json.",
      "reason": "The library file is absent; siblings are from the CNL-0102 catalog-cited reconstruction."
    },
    {
      "claim": "CNL-0072 17-to-6 outcome mapping applied as a live artifact.",
      "reason": "CNL-0072 design artifact is absent on this worktree; mapping is disclosed as types only."
    },
    {
      "claim": "CNL-0024 owner-signed veto-abuse detector.",
      "reason": "CNL-0024 requires owner sign-off and is not closed here; this unit only states that risk ACCEPT is not an override of legal PROHIBITED."
    }
  ],
  "output_schema": "command-center/schema/council-preset.schema.json",
  "presets": [
    {
      "base_spec": "CouncilSpec/v2",
      "bound_protocols": [
        "P14",
        "P19",
        "P56"
      ],
      "default_binding": {
        "protocols": [
          "P14",
          "P19",
          "P56"
        ],
        "roles": [
          "Judge",
          "Reviewer",
          "Skeptic",
          "Clerk"
        ],
        "stopping_expression": "may_we == true OR minority_report_filed == true",
        "voting_method": "unanimity"
      },
      "editable_dials": [
        "roles",
        "budgets.max_rounds"
      ],
      "evidence_standard": {
        "absence_of_permit": "PROHIBITED",
        "accepts": [
          "statute",
          "licence-clause",
          "policy",
          "prohibited-use",
          "rights-record"
        ],
        "bar": "cited-instrument-or-fail-closed",
        "question": "may_we",
        "rejects": [
          "feels-legal",
          "owner-wants-it",
          "risk-committee-accepts-exposure",
          "unnamed-custom"
        ]
      },
      "id": "C15",
      "name": "ethics-legal-review",
      "non_editable_dials": [
        "voting_method",
        "stopping_expression"
      ],
      "outcome_types": [
        "PERMITTED",
        "PERMITTED-CONDITIONAL",
        "PROHIBITED",
        "IRREDUCIBLE-DISAGREEMENT"
      ],
      "question": "may_we",
      "reconstruction_basis": "CNL-0111 ethics/legal; 4-tuple locked to CNL-0102 C15",
      "roles": [
        "Judge",
        "Reviewer",
        "Skeptic",
        "Clerk"
      ],
      "stopping_expression": "may_we == true OR minority_report_filed == true",
      "supersedes_or_extends": [
        "C15"
      ],
      "veto_scope": "the proposed option (the act), not the whole council and not the risk committee's exposure record",
      "voting_method": "unanimity"
    },
    {
      "base_spec": "CouncilSpec/v2",
      "bound_protocols": [
        "P39",
        "P40",
        "P43"
      ],
      "default_binding": {
        "protocols": [
          "P39",
          "P40",
          "P43"
        ],
        "roles": [
          "Forecaster",
          "Skeptic",
          "Owner",
          "Chair"
        ],
        "stopping_expression": "exposure_accepted == true AND residual_risk_named == true",
        "voting_method": "supermajority"
      },
      "editable_dials": [
        "roles",
        "budgets.max_rounds"
      ],
      "evidence_standard": {
        "absence_of_quantification": "PARK-UNQUANTIFIED",
        "accepts": [
          "expected-loss-envelope",
          "key-assumption-check",
          "premortem-failure-mode",
          "quality-of-information"
        ],
        "bar": "named-residual-plus-scenario-envelope",
        "question": "how_exposed",
        "rejects": [
          "feels-acceptable",
          "legal-board-said-yes",
          "unnamed-residual",
          "owner-wants-it"
        ]
      },
      "id": "C16",
      "name": "risk-committee",
      "non_editable_dials": [
        "voting_method",
        "stopping_expression"
      ],
      "outcome_types": [
        "ACCEPT",
        "MITIGATE",
        "TRANSFER",
        "AVOID",
        "PARK-UNQUANTIFIED"
      ],
      "question": "how_exposed",
      "reconstruction_basis": "CNL-0111 risk committee; 4-tuple locked to CNL-0102 C16",
      "roles": [
        "Forecaster",
        "Skeptic",
        "Owner",
        "Chair"
      ],
      "stopping_expression": "exposure_accepted == true AND residual_risk_named == true",
      "supersedes_or_extends": [
        "C16"
      ],
      "veto_scope": "authorization of the act given residual exposure; cannot license a legally prohibited option",
      "voting_method": "supermajority"
    }
  ],
  "question": "One board asks may we, the other asks how exposed are we - what different evidence standards and outcome types does each need, and what happens when the legal board says no and the risk committee says the exposure is acceptable?",
  "required_fix": null,
  "reviewer": {
    "independent": true,
    "recount_agrees": true,
    "recounted_c15_c16_distance": 0.9642857142857143,
    "recounted_legal_neighbour": "C05",
    "recounted_risk_neighbour": "C04",
    "reviewer_id": "CNL-0111-probe2-independent-recount",
    "verdict": "PASS"
  },
  "schema_validation": {
    "catalog_schema": "command-center/schema/council-preset.schema.json",
    "invalid_error_count": 6,
    "invalid_record": {
      "id": "C-INVALID",
      "name": "vacuity-probe"
    },
    "per_record": [
      {
        "errors": 0,
        "id": "C15"
      },
      {
        "errors": 0,
        "id": "C16"
      }
    ],
    "record_error_count": 0,
    "schema": "command-center/p2-wave/probes/CNL-0111/council-preset.schema.json",
    "schema_ok": true,
    "vacuous": false,
    "validator": "jsonschema.Draft202012Validator"
  },
  "sentinel": "SUCCESS:CNL-0111",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0111/probe1_instantiate_and_sibling.py",
      "exit_code": 0,
      "id": "probe1-instantiate-and-sibling",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py",
      "exit_code": 0,
      "id": "probe2-schema-and-negative-control",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0111/probe2_schema_and_negative.py",
      "id": "jsonschema-draft202012",
      "result": "PASS"
    }
  ],
  "title": "Normative boards: ethics/legal review and the risk committee",
  "unit_id": "CNL-0111"
}
