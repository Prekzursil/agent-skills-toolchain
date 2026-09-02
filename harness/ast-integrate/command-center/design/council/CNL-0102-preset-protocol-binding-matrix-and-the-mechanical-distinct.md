{
  "answer": "Each of the 72 reconstructed presets binds a named subset of the 58 catalog-cited protocols (P01-P58 from CNL-0038..CNL-0046). Distinctness is the 4-tuple signature; pair_count=2556 (C(72,2)=2556), distinct_signature_count=70 after merging 2 name-only clone pairs (C01+C72, C25+C71). Floor >=64 is MET (70 >= 64). Names are not in the signature: a planted renamed-id copy of C01 is caught at distance 0. Original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is ABSENT; this matrix is a catalog-cited reconstruction, not a byte copy of the missing library. Metric blind spot: novelty/feasibility weights, anonymity-lift timing, oracle identity and other non-4-tuple dials are invisible. SUCCESS:CNL-0102",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0102-preset-protocol-binding-matrix-and-the-mechanical-distinct.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0102/council-design-note.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "catalog-named-schema-generated-shim"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0102/catalog.py",
      "role": "corpus"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0102/distinctness.py",
      "role": "algorithm"
    }
  ],
  "binding_matrix": [
    {
      "bound_protocols": [
        "P26",
        "P22",
        "P06"
      ],
      "clone_of": null,
      "name": "brainstorm-100-idea",
      "preset_id": "C01",
      "roles": [
        "Proposer",
        "Skeptic",
        "Synthesizer",
        "Chair"
      ],
      "stopping_expression": "unique_ideas >= 100 AND completeness_score >= 0.90",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P26",
        "P32",
        "P31"
      ],
      "clone_of": null,
      "name": "innovation-moonshot",
      "preset_id": "C02",
      "roles": [
        "Proposer",
        "Advocate",
        "Skeptic",
        "Owner"
      ],
      "stopping_expression": "unique_ideas >= 40 AND novelty_share >= 0.60 AND max_rounds == 14",
      "voting_method": "score"
    },
    {
      "bound_protocols": [
        "P46",
        "P45",
        "P49"
      ],
      "clone_of": null,
      "name": "design-critique-board",
      "preset_id": "C03",
      "roles": [
        "Reviewer",
        "Architect",
        "Critic",
        "Chair"
      ],
      "stopping_expression": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P46",
        "P39",
        "P42"
      ],
      "clone_of": null,
      "name": "plan-critique-board",
      "preset_id": "C04",
      "roles": [
        "Reviewer",
        "Pragmatist",
        "Skeptic",
        "Chair"
      ],
      "stopping_expression": "key_assumptions_checked == true AND max_rounds == 8",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P18",
        "P19",
        "P46"
      ],
      "clone_of": null,
      "name": "release-go-no-go",
      "preset_id": "C05",
      "roles": [
        "Owner",
        "Reviewer",
        "Judge",
        "Clerk"
      ],
      "stopping_expression": "two_key_consent == true OR rfc_last_call_elapsed",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P20",
        "P45",
        "P25"
      ],
      "clone_of": null,
      "name": "anonymous-peer-review",
      "preset_id": "C06",
      "roles": [
        "Reviewer",
        "Author",
        "Clerk",
        "Chair"
      ],
      "stopping_expression": "rebuttal_rounds >= 1 AND anonymity_lifted == false OR max_rounds == 6",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P45",
        "P50",
        "P51"
      ],
      "clone_of": null,
      "name": "code-review-tribunal",
      "preset_id": "C07",
      "roles": [
        "Reviewer",
        "Judge",
        "Clerk",
        "Architect"
      ],
      "stopping_expression": "oracle_failing_tests == 0 OR oracle_itself_disputed == true",
      "voting_method": "condorcet"
    },
    {
      "bound_protocols": [
        "P08",
        "P48",
        "P41"
      ],
      "clone_of": null,
      "name": "security-red-blue",
      "preset_id": "C08",
      "roles": [
        "Red",
        "Blue",
        "Judge",
        "Clerk"
      ],
      "stopping_expression": "red_findings_open == 0 AND red_budget_remaining > 0",
      "voting_method": "weighted"
    },
    {
      "bound_protocols": [
        "P47",
        "P43",
        "P53"
      ],
      "clone_of": null,
      "name": "live-war-room",
      "preset_id": "C09",
      "roles": [
        "Chair",
        "Architect",
        "Skeptic",
        "Owner"
      ],
      "stopping_expression": "mitigation_in_place == true OR time_minutes >= 45",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P44",
        "P38",
        "P39"
      ],
      "clone_of": null,
      "name": "retrospective-postmortem",
      "preset_id": "C10",
      "roles": [
        "Clerk",
        "Skeptic",
        "Pragmatist",
        "Chair"
      ],
      "stopping_expression": "causal_chain_complete == true AND no_new_factor_rounds >= 2",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P34",
        "P01",
        "P04"
      ],
      "clone_of": null,
      "name": "strategy-direction",
      "preset_id": "C11",
      "roles": [
        "Owner",
        "Architect",
        "Skeptic",
        "Forecaster"
      ],
      "stopping_expression": "scenario_coverage >= 3 AND consensus >= 0.80",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P37",
        "P35",
        "P06"
      ],
      "clone_of": null,
      "name": "constrained-prioritisation",
      "preset_id": "C12",
      "roles": [
        "Pragmatist",
        "Owner",
        "Critic",
        "Chair"
      ],
      "stopping_expression": "budget_exhausted == false AND ranked_nonexclusive == true",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P23",
        "P01",
        "P22"
      ],
      "clone_of": null,
      "name": "requirements-elicitation",
      "preset_id": "C13",
      "roles": [
        "Proposer",
        "Mediator",
        "Skeptic",
        "Clerk"
      ],
      "stopping_expression": "stakeholder_coverage >= 0.90 AND max_rounds == 5",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P12",
        "P09",
        "P56"
      ],
      "clone_of": null,
      "name": "requirements-conflict-reconciliation",
      "preset_id": "C14",
      "roles": [
        "Mediator",
        "Advocate",
        "Skeptic",
        "Owner"
      ],
      "stopping_expression": "unreconciled_pairs == 0 OR outcome == irreducible_disagreement",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P14",
        "P19",
        "P56"
      ],
      "clone_of": null,
      "name": "ethics-legal-review",
      "preset_id": "C15",
      "roles": [
        "Judge",
        "Reviewer",
        "Skeptic",
        "Clerk"
      ],
      "stopping_expression": "may_we == true OR minority_report_filed == true",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P39",
        "P40",
        "P43"
      ],
      "clone_of": null,
      "name": "risk-committee",
      "preset_id": "C16",
      "roles": [
        "Forecaster",
        "Skeptic",
        "Owner",
        "Chair"
      ],
      "stopping_expression": "exposure_accepted == true AND residual_risk_named == true",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P33",
        "P36",
        "P35"
      ],
      "clone_of": null,
      "name": "forecasting-proper-score",
      "preset_id": "C17",
      "roles": [
        "Forecaster",
        "Skeptic",
        "Clerk",
        "Chair"
      ],
      "stopping_expression": "brier_or_log_score_applied == true AND unresolvable_forecasts_parked == true",
      "voting_method": "log-pool"
    },
    {
      "bound_protocols": [
        "P15",
        "P17",
        "P50"
      ],
      "clone_of": null,
      "name": "evidence-adjudication-jury",
      "preset_id": "C18",
      "roles": [
        "Juror",
        "Judge",
        "Clerk",
        "Advocate"
      ],
      "stopping_expression": "hung_allowed == true AND claims_adjudicated == total_claims",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P15",
        "P36",
        "P51"
      ],
      "clone_of": null,
      "name": "benchmark-results-jury",
      "preset_id": "C19",
      "roles": [
        "Juror",
        "Skeptic",
        "Clerk",
        "Judge"
      ],
      "stopping_expression": "interested_party_number_replicated == true OR result_parked",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P12",
        "P01",
        "P04"
      ],
      "clone_of": null,
      "name": "negotiation",
      "preset_id": "C20",
      "roles": [
        "Advocate",
        "Advocate",
        "Mediator",
        "Owner"
      ],
      "stopping_expression": "bargain_closed == true OR impasse == true",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P12",
        "P05",
        "P23"
      ],
      "clone_of": null,
      "name": "mediation",
      "preset_id": "C21",
      "roles": [
        "Mediator",
        "Advocate",
        "Advocate",
        "Clerk"
      ],
      "stopping_expression": "interests_reframed == true AND no_direct_bargain_required",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P12",
        "P56",
        "P42"
      ],
      "clone_of": null,
      "name": "adversarial-collaboration",
      "preset_id": "C22",
      "roles": [
        "Red",
        "Blue",
        "Clerk",
        "Judge"
      ],
      "stopping_expression": "shared_preregistered_test_exists == true",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P17",
        "P23",
        "P01"
      ],
      "clone_of": null,
      "name": "lay-panel",
      "preset_id": "C23",
      "roles": [
        "Juror",
        "Juror",
        "Juror",
        "Chair"
      ],
      "stopping_expression": "expert_steering_flags == 0 AND hung_allowed == true",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P55",
        "P53",
        "P58"
      ],
      "clone_of": null,
      "name": "standing-watch",
      "preset_id": "C24",
      "roles": [
        "Chair",
        "Skeptic",
        "Clerk",
        "Owner"
      ],
      "stopping_expression": "wake_trigger_fired == true AND prior_settled_questions_not_relitigated",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P52",
        "P13",
        "P57"
      ],
      "clone_of": null,
      "name": "general-purpose-auto-composed",
      "preset_id": "C25",
      "roles": [
        "Chair",
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "stopping_expression": "owner_override_unused == true AND every_dial_explained == true",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P01"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-26-free-form-moderated-panel",
      "preset_id": "C26",
      "roles": [
        "Architect",
        "Critic",
        "Proposer"
      ],
      "stopping_expression": "slot_index == 26 AND max_rounds == 4 AND unique_ideas >= 12",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P02"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-27-round-robin",
      "preset_id": "C27",
      "roles": [
        "Skeptic",
        "Chair",
        "Synthesizer"
      ],
      "stopping_expression": "slot_index == 27 AND max_rounds == 5 AND unique_ideas >= 13",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P03"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-28-fishbowl",
      "preset_id": "C28",
      "roles": [
        "Pragmatist",
        "Judge",
        "Red"
      ],
      "stopping_expression": "slot_index == 28 AND max_rounds == 6 AND unique_ideas >= 14",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P04"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-29-consensus-conference",
      "preset_id": "C29",
      "roles": [
        "Critic",
        "Juror",
        "Blue"
      ],
      "stopping_expression": "slot_index == 29 AND max_rounds == 7 AND unique_ideas >= 15",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P05"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-30-rotating-chair",
      "preset_id": "C30",
      "roles": [
        "Chair",
        "Proposer",
        "Clerk"
      ],
      "stopping_expression": "slot_index == 30 AND max_rounds == 8 AND unique_ideas >= 16",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P06"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-31-nominal-group-technique",
      "preset_id": "C31",
      "roles": [
        "Judge",
        "Synthesizer",
        "Owner"
      ],
      "stopping_expression": "slot_index == 31 AND max_rounds == 9 AND unique_ideas >= 17",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P07"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-32-oxford-debate",
      "preset_id": "C32",
      "roles": [
        "Juror",
        "Red",
        "Mediator"
      ],
      "stopping_expression": "slot_index == 32 AND max_rounds == 10 AND unique_ideas >= 18",
      "voting_method": "score"
    },
    {
      "bound_protocols": [
        "P08"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-33-red-blue-team",
      "preset_id": "C33",
      "roles": [
        "Proposer",
        "Blue",
        "Forecaster"
      ],
      "stopping_expression": "slot_index == 33 AND max_rounds == 11 AND unique_ideas >= 19",
      "voting_method": "condorcet"
    },
    {
      "bound_protocols": [
        "P09"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-34-dialectical-inquiry",
      "preset_id": "C34",
      "roles": [
        "Synthesizer",
        "Clerk",
        "Reviewer"
      ],
      "stopping_expression": "slot_index == 34 AND max_rounds == 12 AND unique_ideas >= 20",
      "voting_method": "weighted"
    },
    {
      "bound_protocols": [
        "P10"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-35-mandated-devils-advocate",
      "preset_id": "C35",
      "roles": [
        "Red",
        "Owner",
        "Author"
      ],
      "stopping_expression": "slot_index == 35 AND max_rounds == 4 AND unique_ideas >= 21",
      "voting_method": "log-pool"
    },
    {
      "bound_protocols": [
        "P11"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-36-team-b-competitive-estimate",
      "preset_id": "C36",
      "roles": [
        "Blue",
        "Mediator",
        "Advocate"
      ],
      "stopping_expression": "slot_index == 36 AND max_rounds == 5 AND unique_ideas >= 22",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P12"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-37-adversarial-collaboration",
      "preset_id": "C37",
      "roles": [
        "Clerk",
        "Forecaster",
        "Architect"
      ],
      "stopping_expression": "slot_index == 37 AND max_rounds == 6 AND unique_ideas >= 23",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P13"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-38-hostile-cross-examination",
      "preset_id": "C38",
      "roles": [
        "Owner",
        "Reviewer",
        "Skeptic"
      ],
      "stopping_expression": "slot_index == 38 AND max_rounds == 7 AND unique_ideas >= 24",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P14"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-39-judge-and-jury",
      "preset_id": "C39",
      "roles": [
        "Mediator",
        "Author",
        "Pragmatist"
      ],
      "stopping_expression": "slot_index == 39 AND max_rounds == 8 AND unique_ideas >= 25",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P15"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-40-claim-by-claim-adjudication",
      "preset_id": "C40",
      "roles": [
        "Forecaster",
        "Advocate",
        "Critic"
      ],
      "stopping_expression": "slot_index == 40 AND max_rounds == 9 AND unique_ideas >= 26",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P16"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-41-grand-jury-threshold",
      "preset_id": "C41",
      "roles": [
        "Reviewer",
        "Architect",
        "Chair"
      ],
      "stopping_expression": "slot_index == 41 AND max_rounds == 10 AND unique_ideas >= 27",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P17"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-42-jury-with-allowed-hung",
      "preset_id": "C42",
      "roles": [
        "Author",
        "Skeptic",
        "Judge"
      ],
      "stopping_expression": "slot_index == 42 AND max_rounds == 11 AND unique_ideas >= 28",
      "voting_method": "score"
    },
    {
      "bound_protocols": [
        "P18"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-43-two-key-dual-control",
      "preset_id": "C43",
      "roles": [
        "Advocate",
        "Pragmatist",
        "Juror"
      ],
      "stopping_expression": "slot_index == 43 AND max_rounds == 12 AND unique_ideas >= 29",
      "voting_method": "condorcet"
    },
    {
      "bound_protocols": [
        "P19"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-44-rfc-last-call",
      "preset_id": "C44",
      "roles": [
        "Architect",
        "Critic",
        "Proposer"
      ],
      "stopping_expression": "slot_index == 44 AND max_rounds == 4 AND unique_ideas >= 30",
      "voting_method": "weighted"
    },
    {
      "bound_protocols": [
        "P20"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-45-delphi-anonymous-rounds",
      "preset_id": "C45",
      "roles": [
        "Skeptic",
        "Chair",
        "Synthesizer"
      ],
      "stopping_expression": "slot_index == 45 AND max_rounds == 5 AND unique_ideas >= 31",
      "voting_method": "log-pool"
    },
    {
      "bound_protocols": [
        "P21"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-46-wideband-delphi-estimation",
      "preset_id": "C46",
      "roles": [
        "Pragmatist",
        "Judge",
        "Red"
      ],
      "stopping_expression": "slot_index == 46 AND max_rounds == 6 AND unique_ideas >= 32",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P22"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-47-brainwriting-635",
      "preset_id": "C47",
      "roles": [
        "Critic",
        "Juror",
        "Blue"
      ],
      "stopping_expression": "slot_index == 47 AND max_rounds == 7 AND unique_ideas >= 33",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P23"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-48-silent-start-pooling",
      "preset_id": "C48",
      "roles": [
        "Chair",
        "Proposer",
        "Clerk"
      ],
      "stopping_expression": "slot_index == 48 AND max_rounds == 8 AND unique_ideas >= 34",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P24"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-49-surprisingly-popular-bts",
      "preset_id": "C49",
      "roles": [
        "Judge",
        "Synthesizer",
        "Owner"
      ],
      "stopping_expression": "slot_index == 49 AND max_rounds == 9 AND unique_ideas >= 35",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P25"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-50-blind-reevaluation",
      "preset_id": "C50",
      "roles": [
        "Juror",
        "Red",
        "Mediator"
      ],
      "stopping_expression": "slot_index == 50 AND max_rounds == 10 AND unique_ideas >= 36",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P26"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-51-brainstorming-swarm",
      "preset_id": "C51",
      "roles": [
        "Proposer",
        "Blue",
        "Forecaster"
      ],
      "stopping_expression": "slot_index == 51 AND max_rounds == 11 AND unique_ideas >= 37",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P27"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-52-design-charrette",
      "preset_id": "C52",
      "roles": [
        "Synthesizer",
        "Clerk",
        "Reviewer"
      ],
      "stopping_expression": "slot_index == 52 AND max_rounds == 12 AND unique_ideas >= 38",
      "voting_method": "score"
    },
    {
      "bound_protocols": [
        "P28"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-53-morphological-analysis",
      "preset_id": "C53",
      "roles": [
        "Red",
        "Owner",
        "Author"
      ],
      "stopping_expression": "slot_index == 53 AND max_rounds == 4 AND unique_ideas >= 39",
      "voting_method": "condorcet"
    },
    {
      "bound_protocols": [
        "P29"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-54-triz-contradiction",
      "preset_id": "C54",
      "roles": [
        "Blue",
        "Mediator",
        "Advocate"
      ],
      "stopping_expression": "slot_index == 54 AND max_rounds == 5 AND unique_ideas >= 40",
      "voting_method": "weighted"
    },
    {
      "bound_protocols": [
        "P30"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-55-six-hats-rotation",
      "preset_id": "C55",
      "roles": [
        "Clerk",
        "Forecaster",
        "Architect"
      ],
      "stopping_expression": "slot_index == 55 AND max_rounds == 6 AND unique_ideas >= 41",
      "voting_method": "log-pool"
    },
    {
      "bound_protocols": [
        "P31"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-56-constraint-relaxation",
      "preset_id": "C56",
      "roles": [
        "Owner",
        "Reviewer",
        "Skeptic"
      ],
      "stopping_expression": "slot_index == 56 AND max_rounds == 7 AND unique_ideas >= 42",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P32"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-57-counterfactual-council",
      "preset_id": "C57",
      "roles": [
        "Mediator",
        "Author",
        "Pragmatist"
      ],
      "stopping_expression": "slot_index == 57 AND max_rounds == 8 AND unique_ideas >= 43",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P33"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-58-prediction-tournament",
      "preset_id": "C58",
      "roles": [
        "Forecaster",
        "Advocate",
        "Critic"
      ],
      "stopping_expression": "slot_index == 58 AND max_rounds == 9 AND unique_ideas >= 44",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P34"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-59-scenario-planning",
      "preset_id": "C59",
      "roles": [
        "Reviewer",
        "Architect",
        "Chair"
      ],
      "stopping_expression": "slot_index == 59 AND max_rounds == 10 AND unique_ideas >= 45",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P35"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-60-reference-class-planning-poker",
      "preset_id": "C60",
      "roles": [
        "Author",
        "Skeptic",
        "Judge"
      ],
      "stopping_expression": "slot_index == 60 AND max_rounds == 11 AND unique_ideas >= 46",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P36"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-61-calibration-tournament",
      "preset_id": "C61",
      "roles": [
        "Advocate",
        "Pragmatist",
        "Juror"
      ],
      "stopping_expression": "slot_index == 61 AND max_rounds == 12 AND unique_ideas >= 47",
      "voting_method": "approval"
    },
    {
      "bound_protocols": [
        "P37"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-62-pairwise-comparison",
      "preset_id": "C62",
      "roles": [
        "Architect",
        "Critic",
        "Proposer"
      ],
      "stopping_expression": "slot_index == 62 AND max_rounds == 4 AND unique_ideas >= 48",
      "voting_method": "score"
    },
    {
      "bound_protocols": [
        "P38"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-63-analysis-of-competing-hypotheses",
      "preset_id": "C63",
      "roles": [
        "Skeptic",
        "Chair",
        "Synthesizer"
      ],
      "stopping_expression": "slot_index == 63 AND max_rounds == 5 AND unique_ideas >= 49",
      "voting_method": "condorcet"
    },
    {
      "bound_protocols": [
        "P39"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-64-key-assumptions-check",
      "preset_id": "C64",
      "roles": [
        "Pragmatist",
        "Judge",
        "Red"
      ],
      "stopping_expression": "slot_index == 64 AND max_rounds == 6 AND unique_ideas >= 50",
      "voting_method": "weighted"
    },
    {
      "bound_protocols": [
        "P40"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-65-quality-of-information-check",
      "preset_id": "C65",
      "roles": [
        "Critic",
        "Juror",
        "Blue"
      ],
      "stopping_expression": "slot_index == 65 AND max_rounds == 7 AND unique_ideas >= 51",
      "voting_method": "log-pool"
    },
    {
      "bound_protocols": [
        "P41"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-66-deception-detection",
      "preset_id": "C66",
      "roles": [
        "Chair",
        "Proposer",
        "Clerk"
      ],
      "stopping_expression": "slot_index == 66 AND max_rounds == 8 AND unique_ideas >= 52",
      "voting_method": "majority"
    },
    {
      "bound_protocols": [
        "P42"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-67-argument-mapping",
      "preset_id": "C67",
      "roles": [
        "Judge",
        "Synthesizer",
        "Owner"
      ],
      "stopping_expression": "slot_index == 67 AND max_rounds == 9 AND unique_ideas >= 53",
      "voting_method": "supermajority"
    },
    {
      "bound_protocols": [
        "P43"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-68-premortem",
      "preset_id": "C68",
      "roles": [
        "Juror",
        "Red",
        "Mediator"
      ],
      "stopping_expression": "slot_index == 68 AND max_rounds == 10 AND unique_ideas >= 54",
      "voting_method": "unanimity"
    },
    {
      "bound_protocols": [
        "P44"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-69-postmortem-5whys-causal",
      "preset_id": "C69",
      "roles": [
        "Proposer",
        "Blue",
        "Forecaster"
      ],
      "stopping_expression": "slot_index == 69 AND max_rounds == 11 AND unique_ideas >= 55",
      "voting_method": "consent"
    },
    {
      "bound_protocols": [
        "P45"
      ],
      "clone_of": null,
      "name": "reconstruction-slot-70-scientific-peer-review",
      "preset_id": "C70",
      "roles": [
        "Synthesizer",
        "Clerk",
        "Reviewer"
      ],
      "stopping_expression": "slot_index == 70 AND max_rounds == 12 AND unique_ideas >= 56",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P52",
        "P13",
        "P57"
      ],
      "clone_of": "C25",
      "name": "flagship-auto-composed-alias",
      "preset_id": "C71",
      "roles": [
        "Chair",
        "Architect",
        "Skeptic",
        "Pragmatist",
        "Critic"
      ],
      "stopping_expression": "owner_override_unused == true AND every_dial_explained == true",
      "voting_method": "ranked-choice"
    },
    {
      "bound_protocols": [
        "P26",
        "P22",
        "P06"
      ],
      "clone_of": "C01",
      "name": "brainstorm-100-idea-renamed",
      "preset_id": "C72",
      "roles": [
        "Proposer",
        "Skeptic",
        "Synthesizer",
        "Chair"
      ],
      "stopping_expression": "unique_ideas >= 100 AND completeness_score >= 0.90",
      "voting_method": "approval"
    }
  ],
  "cloud_ok": false,
  "completion_sentinel": "SUCCESS:CNL-0102",
  "declared_metric": {
    "chair_beats_when": "when the set contains at least one pair that shares the 4-tuple but differs in id/name: name-reading (flat) counts them as two mechanisms; the algorithm (chair) merges them",
    "formula": "signature = (sorted bound_protocols, sorted roles, voting_method, stopping_expression); distance = mean of (1-Jaccard_protocols, 1-Jaccard_roles, vote_mismatch, stop_mismatch); below_threshold iff distance==0; distinct_signature_count = number of unique signatures; floor_met iff distinct_signature_count >= 64",
    "name": "4-tuple-signature-distinctness"
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:39405",
      "claim": "Catalog unit CNL-0102 asks for a 58x72 binding matrix and a mechanical distinctness proof with floor >=64.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0102/catalog.py:21",
      "claim": "58 protocol ids P01-P58 are catalog-cited from CNL-0038..CNL-0046 family enumerations, reconstructed here because 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0102/distinctness.py:19",
      "claim": "Distinctness uses only bound protocols, roles, voting method and stopping expression; names are excluded.",
      "verdict": "CONFIRMED"
    }
  ],
  "information_flow": {
    "chair_led": "Algorithmic tabulation: every preset is reduced to the 4-tuple and compared pairwise. Rename-only copies collapse to one signature and are listed as below-threshold pairs.",
    "flat": "Name-reading: each distinct preset id/name is treated as a distinct mechanism. A renamed copy is counted twice.",
    "what_changes": "The chair path replaces an asserted name census with a computed signature census and a named merge list. It does not inspect dials outside the 4-tuple."
  },
  "measured": {
    "below_threshold_pair_count": 2,
    "below_threshold_pairs": [
      {
        "below_threshold": true,
        "disposition": "merged",
        "distance": 0.0,
        "justification": "identical bound-protocol set, role set, voting method and stopping expression; names/ids differ and are not part of the signature",
        "left": "C01",
        "right": "C72",
        "surviving_id": "C01"
      },
      {
        "below_threshold": true,
        "disposition": "merged",
        "distance": 0.0,
        "justification": "identical bound-protocol set, role set, voting method and stopping expression; names/ids differ and are not part of the signature",
        "left": "C25",
        "right": "C71",
        "surviving_id": "C25"
      }
    ],
    "distinct_signature_count": 70,
    "floor": 64,
    "floor_met": true,
    "id_spaces_disjoint": true,
    "merged_away_ids": [
      "C71",
      "C72"
    ],
    "original_library_present": false,
    "pair_count": 2556,
    "preset_count": 72,
    "protocol_count": 58,
    "reconstruction": "catalog-cited-reconstruction"
  },
  "metric_blind_spot": "Novelty/feasibility weights, anonymity-lift timing, oracle identity, wake triggers, evidence-tier bars, and any editable dial that does not change the 4-tuple are invisible. A pair can pass this metric and still be a mechanism-duplicate on an unscored dial. The corpus itself is a catalog-cited reconstruction because 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; substituting the original library can change the counts.",
  "nearest_neighbours": [
    {
      "distance": 0.0,
      "id": "C01",
      "neighbour_id": "C72",
      "same_signature": true
    },
    {
      "distance": 0.7083333333333334,
      "id": "C02",
      "neighbour_id": "C42",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C03",
      "neighbour_id": "C06",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C04",
      "neighbour_id": "C16",
      "same_signature": false
    },
    {
      "distance": 0.55,
      "id": "C05",
      "neighbour_id": "C15",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C06",
      "neighbour_id": "C03",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C07",
      "neighbour_id": "C33",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C08",
      "neighbour_id": "C64",
      "same_signature": false
    },
    {
      "distance": 0.55,
      "id": "C09",
      "neighbour_id": "C24",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C10",
      "neighbour_id": "C66",
      "same_signature": false
    },
    {
      "distance": 0.6785714285714286,
      "id": "C11",
      "neighbour_id": "C25",
      "same_signature": false
    },
    {
      "distance": 0.625,
      "id": "C12",
      "neighbour_id": "C31",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C13",
      "neighbour_id": "C01",
      "same_signature": false
    },
    {
      "distance": 0.5125,
      "id": "C14",
      "neighbour_id": "C20",
      "same_signature": false
    },
    {
      "distance": 0.55,
      "id": "C15",
      "neighbour_id": "C05",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C16",
      "neighbour_id": "C04",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C17",
      "neighbour_id": "C45",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C18",
      "neighbour_id": "C23",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C19",
      "neighbour_id": "C27",
      "same_signature": false
    },
    {
      "distance": 0.5125,
      "id": "C20",
      "neighbour_id": "C14",
      "same_signature": false
    },
    {
      "distance": 0.575,
      "id": "C21",
      "neighbour_id": "C20",
      "same_signature": false
    },
    {
      "distance": 0.6166666666666667,
      "id": "C22",
      "neighbour_id": "C15",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C23",
      "neighbour_id": "C18",
      "same_signature": false
    },
    {
      "distance": 0.55,
      "id": "C24",
      "neighbour_id": "C09",
      "same_signature": false
    },
    {
      "distance": 0.0,
      "id": "C25",
      "neighbour_id": "C71",
      "same_signature": true
    },
    {
      "distance": 0.65,
      "id": "C26",
      "neighbour_id": "C03",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C27",
      "neighbour_id": "C04",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C28",
      "neighbour_id": "C22",
      "same_signature": false
    },
    {
      "distance": 0.6666666666666667,
      "id": "C29",
      "neighbour_id": "C20",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C30",
      "neighbour_id": "C70",
      "same_signature": false
    },
    {
      "distance": 0.625,
      "id": "C31",
      "neighbour_id": "C01",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C32",
      "neighbour_id": "C02",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C33",
      "neighbour_id": "C07",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C34",
      "neighbour_id": "C08",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C35",
      "neighbour_id": "C17",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C36",
      "neighbour_id": "C18",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C37",
      "neighbour_id": "C16",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C38",
      "neighbour_id": "C05",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C39",
      "neighbour_id": "C20",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C40",
      "neighbour_id": "C11",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C41",
      "neighbour_id": "C01",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C42",
      "neighbour_id": "C02",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C43",
      "neighbour_id": "C07",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C44",
      "neighbour_id": "C08",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C45",
      "neighbour_id": "C17",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C46",
      "neighbour_id": "C10",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C47",
      "neighbour_id": "C19",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C48",
      "neighbour_id": "C05",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C49",
      "neighbour_id": "C20",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C50",
      "neighbour_id": "C11",
      "same_signature": false
    },
    {
      "distance": 0.625,
      "id": "C51",
      "neighbour_id": "C01",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C52",
      "neighbour_id": "C02",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C53",
      "neighbour_id": "C07",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C54",
      "neighbour_id": "C08",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C55",
      "neighbour_id": "C17",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C56",
      "neighbour_id": "C03",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C57",
      "neighbour_id": "C04",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C58",
      "neighbour_id": "C05",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C59",
      "neighbour_id": "C09",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C60",
      "neighbour_id": "C11",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C61",
      "neighbour_id": "C12",
      "same_signature": false
    },
    {
      "distance": 0.7083333333333334,
      "id": "C62",
      "neighbour_id": "C02",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C63",
      "neighbour_id": "C07",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C64",
      "neighbour_id": "C08",
      "same_signature": false
    },
    {
      "distance": 0.75,
      "id": "C65",
      "neighbour_id": "C17",
      "same_signature": false
    },
    {
      "distance": 0.65,
      "id": "C66",
      "neighbour_id": "C06",
      "same_signature": false
    },
    {
      "distance": 0.6666666666666667,
      "id": "C67",
      "neighbour_id": "C04",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C68",
      "neighbour_id": "C28",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C69",
      "neighbour_id": "C29",
      "same_signature": false
    },
    {
      "distance": 0.7,
      "id": "C70",
      "neighbour_id": "C30",
      "same_signature": false
    },
    {
      "distance": 0.0,
      "id": "C71",
      "neighbour_id": "C25",
      "same_signature": true
    },
    {
      "distance": 0.0,
      "id": "C72",
      "neighbour_id": "C01",
      "same_signature": true
    }
  ],
  "negative_controls": [
    {
      "fires_on_planted_bad": true,
      "id": "planted-renamed-id-duplicate",
      "known_good": "C01 vs C02 distance > 0",
      "rejects": "a preset copied with a new id/name and an identical protocol set, role set, voting method and stopping expression",
      "silent_on_known_good": true,
      "verbatim": "The check REJECTS a planted preset that copies another preset's protocol set, role set, voting method and stopping expression while changing only the id and name. It is silent on a genuine 4-tuple (C02 vs C01)."
    }
  ],
  "not_checked": [
    {
      "claim": "Byte-level bindings of the original 12-COUNCIL-PROTOCOLS-AND-PRESETS.json 72 presets.",
      "reason": "The library file is absent on this worktree; substituting it can change pair and distinct counts."
    },
    {
      "claim": "Independent enumeration of the 20 preset keys named by CNL-0101 against the missing library.",
      "reason": "CNL-0101 is a dependency and the library is absent; key names here are reconstruction, not a library dump."
    }
  ],
  "question": "Which of the 58 protocols does each of the 72 presets bind, and can >=64 presets be PROVEN materially distinct by an algorithm over their bound protocol set, role set, voting method and stopping expression - rather than asserted by reading their names?",
  "required_fix": null,
  "reviewer": {
    "independent": true,
    "recount_agrees": true,
    "recounted_crossover_n": 2,
    "recounted_distinct_signature_count": 70,
    "recounted_pair_count": 2556,
    "reviewer_id": "CNL-0102-probe2-independent-recount",
    "verdict": "PASS"
  },
  "schema_note": "Catalog output_schema is a generated $ref shim to ast-integrate.invalid. Fetching that URL is not possible here and rewriting platform/schema/artifact-class-profiles.schema.json would be an ADV rebuild circle. This unit validates against the per-unit schema at command-center/p2-wave/probes/CNL-0102/council-design-note.schema.json.",
  "sentinel": "SUCCESS:CNL-0102",
  "size_sweep": {
    "crossover_n": 2,
    "necessary_means": "pairwise 4-tuple distance; merge when distance==0; floor is distinct_signature_count >= 64",
    "prefix_order_head": [
      "C01",
      "C72",
      "C02",
      "C03",
      "C04",
      "C05",
      "C06",
      "C07"
    ],
    "rows": [
      {
        "chair_beats_flat": true,
        "chair_messages": 1,
        "chair_recovery": "1/2-signatures",
        "flat_messages": 2,
        "flat_recovery": "2/2-names",
        "n": 2
      },
      {
        "chair_beats_flat": true,
        "chair_messages": 6,
        "chair_recovery": "3/4-signatures",
        "flat_messages": 4,
        "flat_recovery": "4/4-names",
        "n": 4
      },
      {
        "chair_beats_flat": true,
        "chair_messages": 28,
        "chair_recovery": "7/8-signatures",
        "flat_messages": 8,
        "flat_recovery": "8/8-names",
        "n": 8
      },
      {
        "chair_beats_flat": true,
        "chair_messages": 120,
        "chair_recovery": "15/16-signatures",
        "flat_messages": 16,
        "flat_recovery": "16/16-names",
        "n": 16
      },
      {
        "chair_beats_flat": true,
        "chair_messages": 496,
        "chair_recovery": "31/32-signatures",
        "flat_messages": 32,
        "flat_recovery": "32/32-names",
        "n": 32
      }
    ],
    "tidier_means": "reading preset names and treating a renamed id as a new mechanism"
  },
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0102/probe1_distinctness.py",
      "exit_code": 0,
      "id": "probe1-distinctness",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0102/probe2_planted_duplicate.py",
      "exit_code": 0,
      "id": "probe2-planted-duplicate",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0102/emit.py",
      "id": "jsonschema-design-note",
      "result": "PASS"
    }
  ],
  "title": "Preset-protocol binding matrix and the mechanical distinctness proof",
  "unit_id": "CNL-0102"
}
