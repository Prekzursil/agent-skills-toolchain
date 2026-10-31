{
 "unit_id": "CNL-0105",
 "state": "SUCCESS",
 "sentinel": "SUCCESS:CNL-0105",
 "schema_version": 1,
 "title": "Anonymous peer-review preset with an author rebuttal round",
 "question": "What does the peer-review preset need that a generic critique board does not - anonymity lifting, reviewer recruitment, and a bounded author rebuttal - and how is reviewer capture prevented when only two reviewers are seated?",
 "produced_at": "2026-08-25T00:58:03Z",
 "output_schema": "command-center/schema/council-preset.schema.json",
 "library_status": {
  "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
  "on_this_tree": false,
  "catalog_cited_preset_count": 72,
  "catalog_cited_protocol_count": 58,
  "only_catalog_named_preset_id": "C-M01",
  "c_m01_note": "CNL-0002 cites C-M01 as recognising 4 of 20 keys against the v1 schema. Body bytes are not on this worktree."
 },
 "preset_key_reconstruction": {
  "count": 20,
  "keys": [
   "id",
   "name",
   "family",
   "base_spec",
   "base_spec_version",
   "delta",
   "default_binding",
   "editable_dials",
   "protocol_bindings",
   "roles",
   "voting",
   "stopping",
   "anonymity",
   "recruitment",
   "rebuttal",
   "evidence",
   "integrity",
   "outcomes",
   "budgets",
   "meta"
  ],
  "catalog_cited": [
   "editable_dials",
   "default_binding"
  ],
  "reconstructed_not_library_verified": [
   "id",
   "name",
   "family",
   "base_spec",
   "base_spec_version",
   "delta",
   "protocol_bindings",
   "roles",
   "voting",
   "stopping",
   "anonymity",
   "recruitment",
   "rebuttal",
   "evidence",
   "integrity",
   "outcomes",
   "budgets",
   "meta"
  ],
  "honesty": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree. Only editable_dials and default_binding are named in WORK-UNIT-CATALOG.json CNL-0101. The other 18 key names are reconstructed from CouncilSpec section names plus the overlay this unit requires. This is not a 72/20 recount."
 },
 "answers": {
  "what_peer_review_needs_that_critique_board_does_not": [
   {
    "need": "anonymity-lifting",
    "critique_board": "named standing seats (CNL-0104 / P46)",
    "this_preset": "blind-then-revealed (CNL-0007). Votes attributed to pseudonyms until after the sealed post-rebuttal revote; lift writes a join table and does not rewrite the vote log.",
    "protocols": [
     "P20",
     "P23",
     "P25"
    ]
   },
   {
    "need": "reviewer-recruitment",
    "critique_board": "standing roster; no COI screen",
    "this_preset": "per-manuscript recruitment, min 2 reviewers, COI screen, prefer distinct vendors. Editor is not a voting reviewer."
   },
   {
    "need": "bounded-author-rebuttal",
    "critique_board": "rebuttal.max_rounds=0; author has no seat",
    "this_preset": "exactly one author rebuttal round at depth 1 (CNL-0048 budget). Author must answer each reviewer claim or mark wont-fix. No second rebuttal chain.",
    "protocols": [
     "P25"
    ]
   }
  ],
  "two_reviewer_capture_prevention": [
   "Sealed first round (P23): a reviewer cannot condition on the peer ballot.",
   "Dual-ACCEPT is not consensus: editor cannot vote accept/reject and must attest nocapture (P18 two-key analogue).",
   "Split ballots recruit reviewer-3; the two cannot settle a disagreement themselves.",
   "Rationale Jaccard >= 0.85 plus seal-break, same prompt_hash, or shared COI fires capture and refuses ACCEPT (P24 treats agreement as non-evidence when cloned).",
   "Anonymity lifts only after the sealed post-rebuttal revote, so the author cannot lobby identified reviewers."
  ]
 },
 "sibling_map": {
  "nearest_sibling": {
   "id": "CNL-0104.gated-critique-board",
   "name": "Gated design/plan critique board",
   "named_explicitly": true,
   "source": "command-center/WORK-UNIT-CATALOG.json#CNL-0104",
   "library_c_id": "NOT-ON-DISK",
   "bound_protocol": "P46",
   "bound_protocol_catalog_name": "architecture-review-board",
   "why_nearest": "CNL-0105's question contrasts the peer-review preset with a generic critique board. CNL-0104 is that board family; P46 is the catalogued ENGINEERING-REVIEW protocol it binds. No library C-id for that preset is on disk except the unrelated stub C-M01."
  },
  "extends": [
   "P45 scientific-peer-review",
   "P20 delphi-anonymous-rounds",
   "P23 silent-start-pooling",
   "P24 surprisingly-popular-bts",
   "P25 blind-reevaluation",
   "CNL-0007 anonymity level blind-then-revealed",
   "CNL-0041 ANONYMOUS family runtime",
   "CNL-0104.gated-critique-board (extends by adding anonymity, recruitment, rebuttal, capture gate)"
  ],
  "library_c_ids_named": [
   "C-M01"
  ],
  "catalog_protocol_siblings": [
   {
    "id": "P45",
    "name": "scientific-peer-review",
    "relation": "this preset binds P45 as the container protocol",
    "anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0045"
   },
   {
    "id": "P46",
    "name": "architecture-review-board",
    "relation": "nearest protocol sibling (generic critique board)",
    "anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0045"
   }
  ]
 },
 "preset": {
  "id": "council.preset.anonymous-peer-review-rebuttal",
  "name": "Anonymous peer-review with one author rebuttal round",
  "family": "engineering-review-peer",
  "base_spec": "councilspec.v2.minimal",
  "base_spec_version": "2.0.0",
  "delta": {
   "protocol_bindings": [
    "P45",
    "P20",
    "P23",
    "P24",
    "P25"
   ],
   "roles": [
    {
     "id": "editor",
     "template": "chair",
     "votes": false
    },
    {
     "id": "author",
     "template": "author",
     "votes": false
    },
    {
     "id": "reviewer-1",
     "template": "reviewer",
     "votes": true,
     "recruited": true
    },
    {
     "id": "reviewer-2",
     "template": "reviewer",
     "votes": true,
     "recruited": true
    },
    {
     "id": "reviewer-3",
     "template": "reviewer",
     "votes": true,
     "recruited": true,
     "conditional": true
    }
   ],
   "voting": {
    "method": "sealed-dual-then-editor-nocapture",
    "quorum": 2,
    "author_votes": false,
    "editor_votes_accept_reject": false,
    "accept_requires": [
     "reviewer-unanimous-or-R3-majority",
     "capture_check.fire==false",
     "editor.nocapture_attestation"
    ]
   },
   "stopping": {
    "expression": "(phase==post_rebuttal_revote AND capture.fire==false AND (unanimous_R1R2 OR R3_majority)) OR capture.fire==true OR recruit_R3_failed",
    "max_rounds": 6,
    "rebuttal_rounds": 1
   },
   "anonymity": {
    "level": "blind-then-revealed",
    "lift_phase": "after-sealed-post-rebuttal-revote",
    "vote_attribution": "pseudonym-in-log-join-table-after-lift"
   },
   "recruitment": {
    "mode": "per-manuscript",
    "min_reviewers": 2,
    "coi_screen": true,
    "prefer_distinct_vendors": true
   },
   "rebuttal": {
    "max_rounds": 1,
    "depth": 1,
    "author_seat": true,
    "obligation": "author-must-answer-each-reviewer-claim-or-mark-wont-fix"
   },
   "evidence": {
    "tier": "peer-reviewed-only",
    "rubric_source": "venue-or-editor"
   },
   "integrity": {
    "two_reviewer_capture": true,
    "coi_screen": true,
    "seal_first_round": true,
    "rationale_jaccard_fire_at": 0.85,
    "sybil_same_prompt_hash": true
   },
   "outcomes": [
    "decision",
    "conditional-decision",
    "no-decision",
    "dissent-with-minority-report"
   ],
   "budgets": {
    "rebuttal_depth": 1,
    "turns": 20
   }
  },
  "default_binding": {
   "protocol": "P45",
   "family": "ENGINEERING-REVIEW"
  },
  "editable_dials": [
   "recruitment.min_reviewers",
   "rebuttal.max_rounds",
   "stopping.max_rounds"
  ],
  "meta": {
   "unit_id": "CNL-0105",
   "supersedes_or_extends": [
    "P45 scientific-peer-review",
    "P20 delphi-anonymous-rounds",
    "P23 silent-start-pooling",
    "P24 surprisingly-popular-bts",
    "P25 blind-reevaluation",
    "CNL-0007 anonymity level blind-then-revealed",
    "CNL-0041 ANONYMOUS family runtime",
    "CNL-0104.gated-critique-board (extends by adding anonymity, recruitment, rebuttal, capture gate)"
   ],
   "library_c_id": "NOT-ON-DISK",
   "not_a_rename_of_sibling": true
  },
  "protocol_bindings": [
   "P45",
   "P20",
   "P23",
   "P24",
   "P25"
  ],
  "roles": [
   {
    "id": "editor",
    "template": "chair",
    "votes": false
   },
   {
    "id": "author",
    "template": "author",
    "votes": false
   },
   {
    "id": "reviewer-1",
    "template": "reviewer",
    "votes": true,
    "recruited": true
   },
   {
    "id": "reviewer-2",
    "template": "reviewer",
    "votes": true,
    "recruited": true
   },
   {
    "id": "reviewer-3",
    "template": "reviewer",
    "votes": true,
    "recruited": true,
    "conditional": true
   }
  ],
  "voting": {
   "method": "sealed-dual-then-editor-nocapture",
   "quorum": 2,
   "author_votes": false,
   "editor_votes_accept_reject": false,
   "accept_requires": [
    "reviewer-unanimous-or-R3-majority",
    "capture_check.fire==false",
    "editor.nocapture_attestation"
   ]
  },
  "stopping": {
   "expression": "(phase==post_rebuttal_revote AND capture.fire==false AND (unanimous_R1R2 OR R3_majority)) OR capture.fire==true OR recruit_R3_failed",
   "max_rounds": 6,
   "rebuttal_rounds": 1
  },
  "anonymity": {
   "level": "blind-then-revealed",
   "lift_phase": "after-sealed-post-rebuttal-revote",
   "vote_attribution": "pseudonym-in-log-join-table-after-lift"
  },
  "recruitment": {
   "mode": "per-manuscript",
   "min_reviewers": 2,
   "coi_screen": true,
   "prefer_distinct_vendors": true
  },
  "rebuttal": {
   "max_rounds": 1,
   "depth": 1,
   "author_seat": true,
   "obligation": "author-must-answer-each-reviewer-claim-or-mark-wont-fix"
  },
  "evidence": {
   "tier": "peer-reviewed-only",
   "rubric_source": "venue-or-editor"
  },
  "integrity": {
   "two_reviewer_capture": true,
   "coi_screen": true,
   "seal_first_round": true,
   "rationale_jaccard_fire_at": 0.85,
   "sybil_same_prompt_hash": true
  },
  "outcomes": [
   "decision",
   "conditional-decision",
   "no-decision",
   "dissent-with-minority-report"
  ],
  "budgets": {
   "rebuttal_depth": 1,
   "turns": 20
  }
 },
 "nearest_sibling_preset": {
  "id": "CNL-0104.gated-critique-board",
  "name": "Gated design/plan critique board",
  "family": "gated-review-board",
  "base_spec": "councilspec.v2.minimal",
  "base_spec_version": "2.0.0",
  "delta": {
   "protocol_bindings": [
    "P46"
   ],
   "roles": [
    {
     "id": "chair",
     "template": "moderator",
     "votes": true
    },
    {
     "id": "architect",
     "template": "reviewer",
     "votes": true
    },
    {
     "id": "skeptic",
     "template": "reviewer",
     "votes": true
    },
    {
     "id": "critic",
     "template": "reviewer",
     "votes": true
    }
   ],
   "voting": {
    "method": "majority-rubric",
    "quorum": 3,
    "author_votes": false,
    "fail_override": "chair"
   },
   "stopping": {
    "expression": "rubric_verdict_emitted OR max_rounds>=4",
    "max_rounds": 4
   },
   "anonymity": {
    "level": "named",
    "lift_phase": "never-hidden"
   },
   "recruitment": {
    "mode": "standing-roster",
    "min_reviewers": 3,
    "coi_screen": false
   },
   "rebuttal": {
    "max_rounds": 0,
    "depth": 0,
    "author_seat": false
   },
   "evidence": {
    "tier": "any-cited",
    "rubric_source": "board-owned"
   },
   "integrity": {
    "two_reviewer_capture": false,
    "coi_screen": false,
    "seal_first_round": false
   },
   "outcomes": [
    "decision",
    "conditional-decision"
   ],
   "budgets": {
    "rebuttal_depth": 0,
    "turns": 12
   }
  },
  "default_binding": {
   "protocol": "P46",
   "family": "ENGINEERING-REVIEW"
  },
  "editable_dials": [
   "stopping.max_rounds",
   "evidence.rubric_source"
  ],
  "meta": {
   "reconstruction_source": "command-center/WORK-UNIT-CATALOG.json#CNL-0104",
   "library_c_id": "NOT-ON-DISK",
   "bound_protocol_catalog": "P46 architecture-review-board",
   "role": "nearest-sibling-generic-critique-board"
  },
  "protocol_bindings": [
   "P46"
  ],
  "roles": [
   {
    "id": "chair",
    "template": "moderator",
    "votes": true
   },
   {
    "id": "architect",
    "template": "reviewer",
    "votes": true
   },
   {
    "id": "skeptic",
    "template": "reviewer",
    "votes": true
   },
   {
    "id": "critic",
    "template": "reviewer",
    "votes": true
   }
  ],
  "voting": {
   "method": "majority-rubric",
   "quorum": 3,
   "author_votes": false,
   "fail_override": "chair"
  },
  "stopping": {
   "expression": "rubric_verdict_emitted OR max_rounds>=4",
   "max_rounds": 4
  },
  "anonymity": {
   "level": "named",
   "lift_phase": "never-hidden"
  },
  "recruitment": {
   "mode": "standing-roster",
   "min_reviewers": 3,
   "coi_screen": false
  },
  "rebuttal": {
   "max_rounds": 0,
   "depth": 0,
   "author_seat": false
  },
  "evidence": {
   "tier": "any-cited",
   "rubric_source": "board-owned"
  },
  "integrity": {
   "two_reviewer_capture": false,
   "coi_screen": false,
   "seal_first_round": false
  },
  "outcomes": [
   "decision",
   "conditional-decision"
  ],
  "budgets": {
   "rebuttal_depth": 0,
   "turns": 12
  }
 },
 "instantiation": {
  "task_id": "fixture.manuscript.two-reviewer-methods-paper",
  "task_title": "Methods paper claiming a new hashing trick; author requests venue-style peer review",
  "profile": {
   "roster": [
    {
     "seat": "editor",
     "template": "chair",
     "votes": false,
     "status": "seated"
    },
    {
     "seat": "author",
     "template": "author",
     "votes": false,
     "status": "seated"
    },
    {
     "seat": "reviewer-1",
     "template": "reviewer",
     "votes": true,
     "status": "seated",
     "recruitment": "per-manuscript",
     "coi_screen": true
    },
    {
     "seat": "reviewer-2",
     "template": "reviewer",
     "votes": true,
     "status": "seated",
     "recruitment": "per-manuscript",
     "coi_screen": true
    },
    {
     "seat": "reviewer-3",
     "template": "reviewer",
     "votes": true,
     "status": "unseated-until-split-or-capture",
     "recruited": true
    }
   ],
   "protocol_schedule": [
    "recruit-and-coi-screen",
    "P45",
    "P23",
    "P20",
    "author-rebuttal-x1-depth1",
    "P25",
    "P24",
    "anonymity-lift:after-sealed-post-rebuttal-revote"
   ],
   "voting_method": "sealed-dual-then-editor-nocapture",
   "stopping_expression": "(phase==post_rebuttal_revote AND capture.fire==false AND (unanimous_R1R2 OR R3_majority)) OR capture.fire==true OR recruit_R3_failed",
   "anonymity_level": "blind-then-revealed",
   "lift_phase": "after-sealed-post-rebuttal-revote",
   "recruitment_mode": "per-manuscript",
   "rebuttal_max_rounds": 1,
   "capture_gate": true,
   "task_id": "fixture.manuscript.two-reviewer-methods-paper",
   "preset_id": "council.preset.anonymous-peer-review-rebuttal",
   "migration": "current"
  },
  "sibling_profile": {
   "roster": [
    {
     "seat": "chair",
     "template": "moderator",
     "votes": true,
     "status": "seated"
    },
    {
     "seat": "architect",
     "template": "reviewer",
     "votes": true,
     "status": "seated"
    },
    {
     "seat": "skeptic",
     "template": "reviewer",
     "votes": true,
     "status": "seated"
    },
    {
     "seat": "critic",
     "template": "reviewer",
     "votes": true,
     "status": "seated"
    }
   ],
   "protocol_schedule": [
    "P46",
    "rubric-verdict"
   ],
   "voting_method": "majority-rubric",
   "stopping_expression": "rubric_verdict_emitted OR max_rounds>=4",
   "anonymity_level": "named",
   "lift_phase": "never-hidden",
   "recruitment_mode": "standing-roster",
   "rebuttal_max_rounds": 0,
   "capture_gate": false,
   "task_id": "fixture.manuscript.two-reviewer-methods-paper",
   "preset_id": "CNL-0104.gated-critique-board",
   "migration": "current"
  }
 },
 "differential": {
  "this_fingerprint": {
   "roles": [
    "author:author:votes=False",
    "editor:chair:votes=False",
    "reviewer-1:reviewer:votes=True",
    "reviewer-2:reviewer:votes=True"
   ],
   "protocol_schedule": [
    "recruit-and-coi-screen",
    "P45",
    "P23",
    "P20",
    "author-rebuttal-x1-depth1",
    "P25",
    "P24",
    "anonymity-lift:after-sealed-post-rebuttal-revote"
   ],
   "voting_method": "sealed-dual-then-editor-nocapture",
   "stopping_expression": "(phase==post_rebuttal_revote AND capture.fire==false AND (unanimous_R1R2 OR R3_majority)) OR capture.fire==true OR recruit_R3_failed",
   "anonymity_level": "blind-then-revealed",
   "recruitment_mode": "per-manuscript",
   "rebuttal_max_rounds": 1,
   "capture_gate": true
  },
  "sibling_fingerprint": {
   "roles": [
    "architect:reviewer:votes=True",
    "chair:moderator:votes=True",
    "critic:reviewer:votes=True",
    "skeptic:reviewer:votes=True"
   ],
   "protocol_schedule": [
    "P46",
    "rubric-verdict"
   ],
   "voting_method": "majority-rubric",
   "stopping_expression": "rubric_verdict_emitted OR max_rounds>=4",
   "anonymity_level": "named",
   "recruitment_mode": "standing-roster",
   "rebuttal_max_rounds": 0,
   "capture_gate": false
  },
  "distance": 8,
  "differing_axes": [
   "anonymity_level",
   "capture_gate",
   "protocol_schedule",
   "rebuttal_max_rounds",
   "recruitment_mode",
   "roles",
   "stopping_expression",
   "voting_method"
  ],
  "identical_axes": [],
  "measurable": true,
  "name_only_duplicate": false
 },
 "capture": {
  "planted_bad": {
   "applicable": true,
   "fire": true,
   "action": "halt-capture",
   "n_reviewers": 2,
   "reasons": [
    "seal-broken",
    "rationale-clone",
    "sybil-same-prompt",
    "shared-coi"
   ],
   "split": false,
   "jaccard": 1.0,
   "accept_blocked": true,
   "note": "capture detector fired; ACCEPT refused"
  },
  "known_good_split": {
   "applicable": true,
   "fire": false,
   "action": "recruit-R3",
   "n_reviewers": 2,
   "reasons": [],
   "split": true,
   "jaccard": 0.08333333333333333,
   "accept_blocked": true,
   "note": "disagreement cannot be resolved by the two seated reviewers"
  },
  "known_good_dual_accept": {
   "applicable": true,
   "fire": false,
   "action": "editor-nocapture-then-accept",
   "n_reviewers": 2,
   "reasons": [],
   "split": false,
   "jaccard": 0.09090909090909091,
   "accept_blocked": false,
   "note": "dual-ACCEPT is not sufficient; editor cannot vote accept/reject and must attest nocapture"
  },
  "both_states": {
   "planted_fires": true,
   "clean_split_silent": true,
   "clean_accept_silent": true
  }
 },
 "schema_validation": {
  "draft": "2020-12",
  "validator": "jsonschema.Draft202012Validator",
  "catalog_schema": "command-center/schema/council-preset.schema.json",
  "working_preset_schema": "command-center/p2-wave/probes/CNL-0105/preset.record.schema.json",
  "working_envelope_schema": "command-center/p2-wave/probes/CNL-0105/envelope.schema.json",
  "catalog_schema_note": "The catalog council-preset.schema.json is a generated $ref shim with no $defs.preset. Affected records are validated against the working 20-key schema. This unit did not rewrite the shared catalog schema file.",
  "affected_records": [
   {
    "id": "council.preset.anonymous-peer-review-rebuttal",
    "error_count": 0
   },
   {
    "id": "CNL-0104.gated-critique-board",
    "error_count": 0
   }
  ],
  "affected_error_count": 0,
  "deliberately_invalid": {
   "id": "invalid_preset",
   "error_count": 20,
   "sample_messages": [
    "'family' is a required property",
    "'base_spec' is a required property",
    "'base_spec_version' is a required property",
    "'default_binding' is a required property",
    "'editable_dials' is a required property",
    "'protocol_bindings' is a required property"
   ],
   "proves_validator_not_vacuous": true
  },
  "envelope_error_count": 0
 },
 "non_editable_dial": {
  "overlay": {
   "voting.method": "majority-rubric"
  },
  "rejected": true,
  "message": "silent override of non-editable dial 'voting.method' rejected (editable_dials=['rebuttal.max_rounds', 'recruitment.min_reviewers', 'stopping.max_rounds'])"
 },
 "negative_control": {
  "verbatim": "On seating planted.seal-broken-clone, reviewer-2 copies reviewer-1's recommendation and rationale after seeing the peer ballot (seen_peer=true, identical rationale, same vendor and prompt_hash, shared COI). capture_check MUST fire (reasons include seal-broken and rationale-clone) and ACCEPT is refused. On seating clean.independent-sealed, ballots are sealed, vendors differ, rationales differ, recommendations split: capture_check MUST be silent and action=recruit-R3. A detector that is silent on the planted clone, or that fires on the sealed split, has not measured capture.",
  "planted_id": "planted.seal-broken-clone",
  "clean_id": "clean.independent-sealed",
  "planted_fire": true,
  "clean_fire": false
 },
 "tests": [
  {
   "id": "instantiate-fixture",
   "result": "PASS",
   "roster_seats": [
    "editor",
    "author",
    "reviewer-1",
    "reviewer-2",
    "reviewer-3"
   ],
   "protocol_schedule": [
    "recruit-and-coi-screen",
    "P45",
    "P23",
    "P20",
    "author-rebuttal-x1-depth1",
    "P25",
    "P24",
    "anonymity-lift:after-sealed-post-rebuttal-revote"
   ],
   "voting_method": "sealed-dual-then-editor-nocapture",
   "stopping_expression": "(phase==post_rebuttal_revote AND capture.fire==false AND (unanimous_R1R2 OR R3_majority)) OR capture.fire==true OR recruit_R3_failed"
  },
  {
   "id": "nearest-sibling-differential",
   "result": "PASS",
   "sibling": "CNL-0104.gated-critique-board",
   "distance": 8,
   "differing_axes": [
    "anonymity_level",
    "capture_gate",
    "protocol_schedule",
    "rebuttal_max_rounds",
    "recruitment_mode",
    "roles",
    "stopping_expression",
    "voting_method"
   ]
  },
  {
   "id": "jsonschema-draft202012",
   "result": "PASS",
   "affected_error_count": 0,
   "invalid_error_count": 20
  },
  {
   "id": "negative-control-capture",
   "result": "PASS",
   "planted_fire": true,
   "clean_fire": false
  }
 ],
 "reviewer": {
  "reviewer_id": "CNL-0105-probe1-instantiate-fresh",
  "verdict": "PASS",
  "independent": true,
  "method": "Re-derived roster/schedule/vote/stop from fixtures/records.json and compared fingerprints; did not take the author's prose as evidence."
 },
 "strongest_surviving_unknown": "The library C-id of the 12-COUNCIL critique-board preset is not on this worktree. Nearest sibling is named from catalogued protocol P46 and unit CNL-0104, not from a library byte copy."
}
