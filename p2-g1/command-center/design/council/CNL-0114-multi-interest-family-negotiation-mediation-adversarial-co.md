{
  "answers": {
    "adversarial_collaboration_not_split_verdict": {
      "mechanism": "Advocates sign a joint test; a registrar locks the pre-registration hash. There is no outcome vote. Claimed outcome split-verdict is a procedure fault, not a result. The stop is a locked test plus recorded/scheduled run, or registrar rejection of a split.",
      "no_outcome_vote": true,
      "prereg_hash_required": true,
      "split_verdict_is_fault": true
    },
    "lay_panel_anti_steering": {
      "ballot_forbids_expert_default": true,
      "evidence_clerk_strips_recommendations": true,
      "mechanism": "The expert-presenter is on the roster but not in the franchise. An evidence-clerk owns the packet and may strip recommendations. Stopping requires the expert recommendation label to be absent from ballot options. A ballot that includes that label FIRES.",
      "presenter_has_no_vote": true
    },
    "negotiation_versus_mediation": {
      "mediation": "A non-voting mediator is seated with caucus/reframe/certify authority. Parties still own the bargain votes. third_party.kind=mediator and integrity.mediator_cannot_vote=true. A record named 'mediation' whose third_party.kind is not mediator is rejected as a rename of negotiation.",
      "negotiation": "Parties bargain on the record with no reframe seat. third_party.kind=none. Franchise is the parties. BATNA walk-away is a first-class stopping outcome. A recorder has no vote.",
      "not_a_name_split": true
    }
  },
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0114-multi-interest-family-negotiation-mediation-adversarial-co.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0114/council-preset.schema.json",
      "role": "working-schema"
    }
  ],
  "c_id_mapping": {
    "c_m01_body_on_disk": false,
    "extends_on_this_tree": [
      "CNL-0017 stakeholder-balanced selection (lay seats / given interests)",
      "CNL-0019 adversarial selection without manufactured disagreement",
      "CNL-0050 protocol-gap: negotiation has no card among the cited 58 (first pass)",
      "CNL-0034 jury topology is related; CNL-0113 owns evidence juries"
    ],
    "honesty": "This unit does not claim a C-id from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json because that file is absent. Sibling named for the differential is the on-disk reconstruction council.preset.catalog-class.editable.",
    "mapped_to_unread_library_c_ids": false,
    "only_catalog_named_preset_id": "C-M01"
  },
  "completion": "SUCCESS:CNL-0114",
  "family": {
    "id": "multi-interest",
    "members": [
      "council.preset.multi-interest.negotiation",
      "council.preset.multi-interest.mediation",
      "council.preset.multi-interest.adversarial-collaboration",
      "council.preset.multi-interest.lay-panel"
    ],
    "merge_rule": "a member whose profile distance to another member is 0 is a rename and must be merged",
    "parameter": "third_party.kind \u00d7 franchise_rule \u00d7 whether the product is a bargain, a certified memorandum, a locked test, or a lay ballot"
  },
  "fixture_task": {
    "disputed_number": {
      "label": "public p99 latency",
      "partner_claim_ms": 90,
      "platform_claim_ms": 240,
      "source": "each party cites its own dashboard"
    },
    "expert_recommendation": {
      "label": "Adopt expert recommendation: raise list price 12% and drop the public SLO",
      "presenter_id": "expert.sre-lead"
    },
    "id": "fixture.multi-interest.slo-pricing-dispute",
    "lay_stakeholders": [
      {
        "expertise": "none-on-sre",
        "id": "lay.app-dev-1"
      },
      {
        "expertise": "none-on-sre",
        "id": "lay.app-dev-2"
      },
      {
        "expertise": "none-on-sre",
        "id": "lay.app-dev-3"
      }
    ],
    "parties": [
      {
        "batna": "withdraw the partner discount tier",
        "id": "party.platform-ops",
        "interest": "cover cost; refuse an SLO that the on-call rotation cannot keep"
      },
      {
        "batna": "route traffic to a competing platform",
        "id": "party.partner-ecosystem",
        "interest": "keep list-price low enough that downstream apps stay; keep a public p99 number"
      }
    ],
    "required_profile_fields": [
      "roster",
      "protocol_schedule",
      "voting_method",
      "stopping_expression"
    ],
    "title": "Platform-Ops vs Partner-Ecosystem dispute over API price and a latency SLO the partner published"
  },
  "instantiations": [
    {
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.negotiation.offer"
      },
      "evidence": {
        "clerk_gate": false,
        "prereg_hash_required": false,
        "tier": "party-offers"
      },
      "franchise": [
        "party.A",
        "party.B"
      ],
      "integrity": {
        "ballot_forbids_expert_default": false,
        "batna_is_first_class_outcome": true,
        "mediator_cannot_vote": false,
        "presenter_disenfranchised": false,
        "split_verdict_is_fault": false
      },
      "outcomes": [
        "agreement",
        "walk-away-batna"
      ],
      "preset_id": "council.preset.multi-interest.negotiation",
      "protocol_schedule": [
        "protocol.negotiation.offer",
        "protocol.negotiation.counter",
        "protocol.negotiation.package-swap",
        "protocol.negotiation.batna-check"
      ],
      "roster": [
        {
          "authority": null,
          "filled_by": "party.platform-ops",
          "interest": "cover cost; refuse an SLO that the on-call rotation cannot keep",
          "role_id": "party.A",
          "template": "bargainer",
          "votes": true
        },
        {
          "authority": null,
          "filled_by": "party.partner-ecosystem",
          "interest": "keep list-price low enough that downstream apps stay; keep a public p99 number",
          "role_id": "party.B",
          "template": "bargainer",
          "votes": true
        },
        {
          "authority": "transcript-only",
          "role_id": "recorder",
          "template": "scribe",
          "votes": false
        }
      ],
      "stopping_expression": "all_franchise_signed OR batna_invoked OR max_rounds>=6",
      "task_id": "fixture.multi-interest.slo-pricing-dispute",
      "third_party_kind": "none",
      "voting_method": "unanimous-consent-of-franchise"
    },
    {
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.mediation.private-caucus"
      },
      "evidence": {
        "clerk_gate": false,
        "prereg_hash_required": false,
        "tier": "interest-statements"
      },
      "franchise": [
        "party.A",
        "party.B"
      ],
      "integrity": {
        "ballot_forbids_expert_default": false,
        "batna_is_first_class_outcome": false,
        "mediator_cannot_vote": true,
        "presenter_disenfranchised": false,
        "split_verdict_is_fault": false
      },
      "outcomes": [
        "certified-memorandum",
        "impasse"
      ],
      "preset_id": "council.preset.multi-interest.mediation",
      "protocol_schedule": [
        "protocol.mediation.private-caucus",
        "protocol.mediation.interest-reframe",
        "protocol.mediation.option-generation",
        "protocol.mediation.reality-test",
        "protocol.mediation.memorandum"
      ],
      "roster": [
        {
          "authority": null,
          "filled_by": "party.platform-ops",
          "interest": "cover cost; refuse an SLO that the on-call rotation cannot keep",
          "role_id": "party.A",
          "template": "bargainer",
          "votes": true
        },
        {
          "authority": null,
          "filled_by": "party.partner-ecosystem",
          "interest": "keep list-price low enough that downstream apps stay; keep a public p99 number",
          "role_id": "party.B",
          "template": "bargainer",
          "votes": true
        },
        {
          "authority": "caucus-reframe-certify",
          "role_id": "mediator",
          "template": "neutral-reframer",
          "votes": false
        },
        {
          "authority": "transcript-only",
          "role_id": "recorder",
          "template": "scribe",
          "votes": false
        }
      ],
      "stopping_expression": "memorandum_certified OR mediator_impasse OR max_rounds>=8",
      "task_id": "fixture.multi-interest.slo-pricing-dispute",
      "third_party_kind": "mediator",
      "voting_method": "mediated-consent-parties-sign-mediator-certifies"
    },
    {
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.advcol.competing-hypotheses"
      },
      "evidence": {
        "clerk_gate": false,
        "prereg_hash_required": true,
        "tier": "preregistered-test"
      },
      "franchise": [],
      "integrity": {
        "ballot_forbids_expert_default": false,
        "batna_is_first_class_outcome": false,
        "mediator_cannot_vote": false,
        "presenter_disenfranchised": false,
        "split_verdict_is_fault": true
      },
      "outcomes": [
        "shared-test-result",
        "procedure-fault"
      ],
      "preset_id": "council.preset.multi-interest.adversarial-collaboration",
      "protocol_schedule": [
        "protocol.advcol.competing-hypotheses",
        "protocol.advcol.joint-test-design",
        "protocol.advcol.preregister-lock",
        "protocol.advcol.execute-or-schedule",
        "protocol.advcol.shared-readout"
      ],
      "roster": [
        {
          "authority": "sign-test",
          "filled_by": "party.platform-ops",
          "interest": "cover cost; refuse an SLO that the on-call rotation cannot keep",
          "role_id": "advocate.A",
          "template": "hypothesis-holder",
          "votes": false
        },
        {
          "authority": "sign-test",
          "filled_by": "party.partner-ecosystem",
          "interest": "keep list-price low enough that downstream apps stay; keep a public p99 number",
          "role_id": "advocate.B",
          "template": "hypothesis-holder",
          "votes": false
        },
        {
          "authority": "lock-hash-reject-split-verdict",
          "role_id": "registrar",
          "template": "prereg-lock",
          "votes": false
        },
        {
          "authority": "procedure-not-outcome",
          "role_id": "protocol-adjudicator",
          "template": "procedure-judge",
          "votes": false
        }
      ],
      "stopping_expression": "(prereg_locked AND (result_recorded OR run_scheduled)) OR registrar_rejects_split_verdict",
      "task_id": "fixture.multi-interest.slo-pricing-dispute",
      "third_party_kind": "registrar",
      "voting_method": "joint-prereg-lock-no-outcome-vote"
    },
    {
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.lay.clerk-packet"
      },
      "evidence": {
        "clerk_gate": true,
        "prereg_hash_required": false,
        "tier": "clerk-gated-packet"
      },
      "franchise": [
        "lay.1",
        "lay.2",
        "lay.3"
      ],
      "integrity": {
        "ballot_forbids_expert_default": true,
        "batna_is_first_class_outcome": false,
        "mediator_cannot_vote": false,
        "presenter_disenfranchised": true,
        "split_verdict_is_fault": false
      },
      "outcomes": [
        "lay-ballot-result"
      ],
      "preset_id": "council.preset.multi-interest.lay-panel",
      "protocol_schedule": [
        "protocol.lay.clerk-packet",
        "protocol.lay.timeboxed-testimony",
        "protocol.lay.clerk-steering-rebuttal",
        "protocol.lay.silent-ballot"
      ],
      "roster": [
        {
          "authority": null,
          "filled_by": "lay.app-dev-1",
          "role_id": "lay.1",
          "template": "stakeholder-decider",
          "votes": true
        },
        {
          "authority": null,
          "filled_by": "lay.app-dev-2",
          "role_id": "lay.2",
          "template": "stakeholder-decider",
          "votes": true
        },
        {
          "authority": null,
          "filled_by": "lay.app-dev-3",
          "role_id": "lay.3",
          "template": "stakeholder-decider",
          "votes": true
        },
        {
          "authority": "timeboxed-testimony-no-vote",
          "filled_by": "expert.sre-lead",
          "must_not_vote": true,
          "role_id": "expert-presenter",
          "template": "briefing-witness",
          "votes": false
        },
        {
          "authority": "strip-recommendations",
          "role_id": "evidence-clerk",
          "template": "packet-gate",
          "votes": false
        },
        {
          "authority": "procedure",
          "role_id": "chair",
          "template": "procedure-only",
          "votes": false
        }
      ],
      "stopping_expression": "ballots_cast>=quorum AND expert_recommendation_absent_from_ballot_options",
      "task_id": "fixture.multi-interest.slo-pricing-dispute",
      "third_party_kind": "evidence-clerk",
      "voting_method": "lay-only-secret-ballot"
    }
  ],
  "library_status": {
    "c_m01_body_on_disk": false,
    "catalog_cited_preset_count": 72,
    "catalog_cited_protocol_count": 58,
    "honesty": "Nearest-sibling distances are computed against ON-DISK reconstructions, not against unread library bytes.",
    "on_this_tree": false,
    "only_catalog_named_preset_id": "C-M01",
    "path_catalog_input": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
  },
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0114/probe1_instantiate.py",
      "exit_code": 0,
      "id": "probe1"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0114/probe2_schema_sibling_control.py",
      "exit_code": 0,
      "id": "probe2"
    }
  ],
  "nearest_sibling_differential": [
    {
      "duplicates": [],
      "nearest_distinct": {
        "distance": 7,
        "duplicate": false,
        "id": "CNL-0104.gated-critique-board"
      },
      "preset_id": "council.preset.multi-interest.negotiation",
      "ranked": [
        {
          "distance": 7,
          "duplicate": false,
          "id": "CNL-0104.gated-critique-board"
        },
        {
          "distance": 7,
          "duplicate": false,
          "id": "council.preset.catalog-class.editable"
        }
      ]
    },
    {
      "duplicates": [],
      "nearest_distinct": {
        "distance": 8,
        "duplicate": false,
        "id": "CNL-0104.gated-critique-board"
      },
      "preset_id": "council.preset.multi-interest.mediation",
      "ranked": [
        {
          "distance": 8,
          "duplicate": false,
          "id": "CNL-0104.gated-critique-board"
        },
        {
          "distance": 8,
          "duplicate": false,
          "id": "council.preset.catalog-class.editable"
        }
      ]
    },
    {
      "duplicates": [],
      "nearest_distinct": {
        "distance": 9,
        "duplicate": false,
        "id": "CNL-0104.gated-critique-board"
      },
      "preset_id": "council.preset.multi-interest.adversarial-collaboration",
      "ranked": [
        {
          "distance": 9,
          "duplicate": false,
          "id": "CNL-0104.gated-critique-board"
        },
        {
          "distance": 9,
          "duplicate": false,
          "id": "council.preset.catalog-class.editable"
        }
      ]
    },
    {
      "duplicates": [],
      "nearest_distinct": {
        "distance": 9,
        "duplicate": false,
        "id": "CNL-0104.gated-critique-board"
      },
      "preset_id": "council.preset.multi-interest.lay-panel",
      "ranked": [
        {
          "distance": 9,
          "duplicate": false,
          "id": "CNL-0104.gated-critique-board"
        },
        {
          "distance": 9,
          "duplicate": false,
          "id": "council.preset.catalog-class.editable"
        }
      ]
    }
  ],
  "nearest_sibling_named": "CNL-0104.gated-critique-board",
  "negative_controls": [
    {
      "id": "name-only-clone",
      "rejects": "a preset that differs only in id/name from another record"
    },
    {
      "id": "locked-dial-overlay",
      "rejects": "operator overlay of voting.method (not in editable_dials)"
    },
    {
      "fires_on": "ballot options containing the expert recommendation label",
      "id": "lay-expert-steering",
      "silent_on": "clerk-authored options that omit that label"
    },
    {
      "fires_on": "claimed outcome split-verdict",
      "id": "split-verdict",
      "silent_on": "locked shared-test-result"
    },
    {
      "fires_on": "id/name contains mediation but third_party.kind != mediator",
      "id": "mediation-name-without-mediator"
    }
  ],
  "output_schema_declared": "command-center/schema/council-preset.schema.json",
  "output_schema_declared_present": true,
  "presets": [
    {
      "base_spec": "councilspec.v2.minimal",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.negotiation.offer"
      },
      "delta": {
        "anonymity": {
          "level": "named",
          "lift_phase": "never-hidden"
        },
        "budgets": {
          "caucus_turns": 0,
          "turns": 12
        },
        "evidence": {
          "clerk_gate": false,
          "prereg_hash_required": false,
          "tier": "party-offers"
        },
        "franchise_rule": "parties-only",
        "integrity": {
          "ballot_forbids_expert_default": false,
          "batna_is_first_class_outcome": true,
          "mediator_cannot_vote": false,
          "presenter_disenfranchised": false,
          "split_verdict_is_fault": false
        },
        "outcomes": [
          "agreement",
          "walk-away-batna"
        ],
        "protocol_bindings": [
          "protocol.negotiation.offer",
          "protocol.negotiation.counter",
          "protocol.negotiation.package-swap",
          "protocol.negotiation.batna-check"
        ],
        "recruitment": {
          "min_reviewers": 0,
          "mode": "parties-are-given"
        },
        "roles": [
          {
            "id": "party.A",
            "template": "bargainer",
            "votes": true
          },
          {
            "id": "party.B",
            "template": "bargainer",
            "votes": true
          },
          {
            "authority": "transcript-only",
            "id": "recorder",
            "template": "scribe",
            "votes": false
          }
        ],
        "stopping": {
          "expression": "all_franchise_signed OR batna_invoked OR max_rounds>=6",
          "max_rounds": 6
        },
        "third_party": {
          "kind": "none",
          "may_lock_prereg": false,
          "may_reframe_interests": false,
          "may_strip_recommendations": false,
          "votes": false
        },
        "voting": {
          "author_votes": false,
          "method": "unanimous-consent-of-franchise",
          "quorum": 2
        }
      },
      "editable_dials": [
        "stopping.max_rounds",
        "budgets.turns"
      ],
      "family": "multi-interest",
      "id": "council.preset.multi-interest.negotiation",
      "meta": {
        "library_c_id": "NOT-ON-DISK",
        "not_a_rename_of_sibling": true,
        "reconstruction_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; C-ids from that library are NOT-CHECKED.",
        "unit_id": "CNL-0114"
      },
      "name": "Direct-bargain negotiation (parties only, BATNA-capable)",
      "on_base_version_bump": "migrate-listed-dials-or-park",
      "supersedes_or_extends": [
        "CNL-0050-protocol-gap:negotiation-absent-from-58-cards",
        "CNL-0017-stakeholder-balance (parties as given interests, not a diversity sampler)"
      ]
    },
    {
      "base_spec": "councilspec.v2.minimal",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.mediation.private-caucus"
      },
      "delta": {
        "anonymity": {
          "level": "named-plus-private-caucus",
          "lift_phase": "memorandum"
        },
        "budgets": {
          "caucus_turns": 4,
          "turns": 16
        },
        "evidence": {
          "clerk_gate": false,
          "prereg_hash_required": false,
          "tier": "interest-statements"
        },
        "franchise_rule": "parties-only-mediator-certifies",
        "integrity": {
          "ballot_forbids_expert_default": false,
          "batna_is_first_class_outcome": false,
          "mediator_cannot_vote": true,
          "presenter_disenfranchised": false,
          "split_verdict_is_fault": false
        },
        "outcomes": [
          "certified-memorandum",
          "impasse"
        ],
        "protocol_bindings": [
          "protocol.mediation.private-caucus",
          "protocol.mediation.interest-reframe",
          "protocol.mediation.option-generation",
          "protocol.mediation.reality-test",
          "protocol.mediation.memorandum"
        ],
        "recruitment": {
          "min_reviewers": 0,
          "mode": "parties-plus-appointed-mediator"
        },
        "roles": [
          {
            "id": "party.A",
            "template": "bargainer",
            "votes": true
          },
          {
            "id": "party.B",
            "template": "bargainer",
            "votes": true
          },
          {
            "authority": "caucus-reframe-certify",
            "id": "mediator",
            "template": "neutral-reframer",
            "votes": false
          },
          {
            "authority": "transcript-only",
            "id": "recorder",
            "template": "scribe",
            "votes": false
          }
        ],
        "stopping": {
          "expression": "memorandum_certified OR mediator_impasse OR max_rounds>=8",
          "max_rounds": 8
        },
        "third_party": {
          "kind": "mediator",
          "may_lock_prereg": false,
          "may_reframe_interests": true,
          "may_strip_recommendations": false,
          "votes": false
        },
        "voting": {
          "author_votes": false,
          "certifier": "mediator",
          "method": "mediated-consent-parties-sign-mediator-certifies",
          "quorum": 2
        }
      },
      "editable_dials": [
        "stopping.max_rounds",
        "budgets.caucus_turns"
      ],
      "family": "multi-interest",
      "id": "council.preset.multi-interest.mediation",
      "meta": {
        "library_c_id": "NOT-ON-DISK",
        "not_a_rename_of_sibling": true,
        "reconstruction_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; C-ids from that library are NOT-CHECKED.",
        "unit_id": "CNL-0114"
      },
      "name": "Interest-reframe mediation (non-voting mediator)",
      "on_base_version_bump": "migrate-listed-dials-or-park",
      "supersedes_or_extends": [
        "CNL-0017-stakeholder-balance",
        "CNL-0050-protocol-gap:negotiation-is-not-mediation"
      ]
    },
    {
      "base_spec": "councilspec.v2.minimal",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.advcol.competing-hypotheses"
      },
      "delta": {
        "anonymity": {
          "level": "named",
          "lift_phase": "never-hidden"
        },
        "budgets": {
          "caucus_turns": 0,
          "turns": 14
        },
        "evidence": {
          "clerk_gate": false,
          "prereg_hash_required": true,
          "tier": "preregistered-test"
        },
        "franchise_rule": "no-outcome-vote-advocates-sign-test",
        "integrity": {
          "ballot_forbids_expert_default": false,
          "batna_is_first_class_outcome": false,
          "mediator_cannot_vote": false,
          "presenter_disenfranchised": false,
          "split_verdict_is_fault": true
        },
        "outcomes": [
          "shared-test-result",
          "procedure-fault"
        ],
        "protocol_bindings": [
          "protocol.advcol.competing-hypotheses",
          "protocol.advcol.joint-test-design",
          "protocol.advcol.preregister-lock",
          "protocol.advcol.execute-or-schedule",
          "protocol.advcol.shared-readout"
        ],
        "recruitment": {
          "min_reviewers": 0,
          "mode": "advocates-are-given"
        },
        "roles": [
          {
            "authority": "sign-test",
            "id": "advocate.A",
            "template": "hypothesis-holder",
            "votes": false
          },
          {
            "authority": "sign-test",
            "id": "advocate.B",
            "template": "hypothesis-holder",
            "votes": false
          },
          {
            "authority": "lock-hash-reject-split-verdict",
            "id": "registrar",
            "template": "prereg-lock",
            "votes": false
          },
          {
            "authority": "procedure-not-outcome",
            "id": "protocol-adjudicator",
            "template": "procedure-judge",
            "votes": false
          }
        ],
        "stopping": {
          "expression": "(prereg_locked AND (result_recorded OR run_scheduled)) OR registrar_rejects_split_verdict",
          "max_rounds": 5
        },
        "third_party": {
          "kind": "registrar",
          "may_lock_prereg": true,
          "may_reframe_interests": false,
          "may_strip_recommendations": false,
          "votes": false
        },
        "voting": {
          "author_votes": false,
          "method": "joint-prereg-lock-no-outcome-vote",
          "quorum": 0
        }
      },
      "editable_dials": [
        "stopping.max_rounds",
        "budgets.turns"
      ],
      "family": "multi-interest",
      "id": "council.preset.multi-interest.adversarial-collaboration",
      "meta": {
        "library_c_id": "NOT-ON-DISK",
        "not_a_rename_of_sibling": true,
        "reconstruction_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; C-ids from that library are NOT-CHECKED.",
        "unit_id": "CNL-0114"
      },
      "name": "Adversarial collaboration to a shared pre-registered test",
      "on_base_version_bump": "migrate-listed-dials-or-park",
      "supersedes_or_extends": [
        "CNL-0019-adversarial-selection-without-theatre",
        "CNL-0019-real-prior-conflict-must-bind-a-shared-test"
      ]
    },
    {
      "base_spec": "councilspec.v2.minimal",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "family": "MULTI-INTEREST",
        "protocol": "protocol.lay.clerk-packet"
      },
      "delta": {
        "anonymity": {
          "level": "secret-ballot",
          "lift_phase": "after-count"
        },
        "budgets": {
          "caucus_turns": 0,
          "turns": 8
        },
        "evidence": {
          "clerk_gate": true,
          "prereg_hash_required": false,
          "tier": "clerk-gated-packet"
        },
        "franchise_rule": "lay-only-secret-ballot",
        "integrity": {
          "ballot_forbids_expert_default": true,
          "batna_is_first_class_outcome": false,
          "mediator_cannot_vote": false,
          "presenter_disenfranchised": true,
          "split_verdict_is_fault": false
        },
        "outcomes": [
          "lay-ballot-result"
        ],
        "protocol_bindings": [
          "protocol.lay.clerk-packet",
          "protocol.lay.timeboxed-testimony",
          "protocol.lay.clerk-steering-rebuttal",
          "protocol.lay.silent-ballot"
        ],
        "recruitment": {
          "min_reviewers": 3,
          "mode": "lay-stakeholders-are-given"
        },
        "roles": [
          {
            "count": 3,
            "id": "lay",
            "template": "stakeholder-decider",
            "votes": true
          },
          {
            "authority": "timeboxed-testimony-no-vote",
            "id": "expert-presenter",
            "template": "briefing-witness",
            "votes": false
          },
          {
            "authority": "strip-recommendations",
            "id": "evidence-clerk",
            "template": "packet-gate",
            "votes": false
          },
          {
            "authority": "procedure",
            "id": "chair",
            "template": "procedure-only",
            "votes": false
          }
        ],
        "stopping": {
          "expression": "ballots_cast>=quorum AND expert_recommendation_absent_from_ballot_options",
          "max_rounds": 3
        },
        "third_party": {
          "kind": "evidence-clerk",
          "may_lock_prereg": false,
          "may_reframe_interests": false,
          "may_strip_recommendations": true,
          "votes": false
        },
        "voting": {
          "author_votes": false,
          "method": "lay-only-secret-ballot",
          "quorum": 3
        }
      },
      "editable_dials": [
        "stopping.max_rounds",
        "roles[id=lay].count"
      ],
      "family": "multi-interest",
      "id": "council.preset.multi-interest.lay-panel",
      "meta": {
        "library_c_id": "NOT-ON-DISK",
        "not_a_rename_of_sibling": true,
        "reconstruction_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; C-ids from that library are NOT-CHECKED.",
        "unit_id": "CNL-0114"
      },
      "name": "Lay stakeholder panel with clerk-gated expert testimony",
      "on_base_version_bump": "migrate-listed-dials-or-park",
      "supersedes_or_extends": [
        "CNL-0017-stakeholder-balance (lay seats, not expert diversity)",
        "CNL-0034-jury-topology (related; CNL-0113 owns evidence juries \u2014 this is a stakeholder panel)"
      ]
    }
  ],
  "probe_tails": {
    "probe1": [
      "  \"unit\": \"CNL-0114\"",
      "}",
      "instantiated=4 min_intra=8 neg_third=none med_third=mediator",
      "SUCCESS:CNL-0114-probe1 instantiate roster/schedule/vote/stop"
    ],
    "probe2": [
      "  \"unit\": \"CNL-0114\"",
      "}",
      "schema_errors=0 mutant_errors=2 nearest=CNL-0104.gated-critique-board d=7",
      "SUCCESS:CNL-0114-probe2 schema sibling negative-control"
    ]
  },
  "question": "These four seat participants with non-aligned interests or no expertise - what distinguishes negotiation (parties bargain directly) from mediation (a neutral third party reframes interests), what protects a lay stakeholder panel from being steered by the expert presenting to it, and what makes adversarial collaboration produce a shared pre-registered test rather than a split verdict?",
  "reviewer": {
    "independent": true,
    "method": "Mechanical instantiation and profile distance; does not accept the author's prose as the differential.",
    "reviewer_id": "CNL-0114-probe1-instantiate-replay",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0114",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0114/probe1_instantiate.py",
      "exit_code": 0,
      "id": "instantiate-fixture",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0114/probe2_schema_sibling_control.py",
      "exit_code": 0,
      "id": "schema-sibling-negative-control",
      "result": "PASS"
    }
  ],
  "title": "Multi-interest family: negotiation, mediation, adversarial collaboration and lay panel",
  "ts": "2026-08-25T00:52:59Z",
  "unit_id": "CNL-0114",
  "working_schema": "command-center/p2-wave/probes/CNL-0114/council-preset.schema.json",
  "working_schema_status": "unit-local working typed-delta schema; CNL-0101 owns the canonical 20-key type over the 72-record library, which is not on this tree"
}
