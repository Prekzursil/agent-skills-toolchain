{
  "answer": {
    "mechanism": "Tabulate first, then run every legal load-bearing test bound to the decided claim. If the tally would accept (YES) and any such test FAILS, the recorded outcome is REFUTED \u2014 never YES, even when every seat voted YES. A failing test bound to a different claim is recorded as an irrelevant failure and does not veto.",
    "who_may_declare": "Only owner, charter, protocol-preset, or a non-voting registrar, and only with declared_at strictly before ballot_close. A voting seat, a majority vote, a chair acting after close, or a registrar who also holds a seat on this council cannot make a test load-bearing."
  },
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0068-evidence-outranks-popularity-the-executable-test-override-.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0068/override.py",
      "role": "supporting"
    }
  ],
  "audit_when_floor_blocks": {
    "does_not_rewrite_expression": true,
    "event": "executable-test-override",
    "must_name_unmet_floors": true,
    "preserves_tally": "The ballot tally remains on the record. The override changes outcome, not the votes."
  },
  "ceiling": {
    "missing_is": "not-load-bearing; cannot veto a sound YES",
    "required_field": "binder_role",
    "unmet_at_ceiling": "At ballot_close, undeclared tests cannot be attached. A hang where every FAIL vetoes every claim is forbidden by claim_id match."
  },
  "claim_under_test": "One failing executable test that is legally bound to the decided claim overturns a unanimous YES; a failing test bound to a different claim cannot veto; only owner/charter/protocol-preset/registrar may declare a test load-bearing, and only before ballot_close.",
  "completion_sentinel": "SUCCESS:CNL-0068",
  "dependency_note": "CNL-0023 (vote-weight provenance) is not delivered on this worktree. This unit does not wait on it: the override fires on any legal weight vector, including weighted unanimity (fixture weighted_unanimous_refuted).",
  "depends_on": [
    "CNL-0023"
  ],
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0068].evidence_requirement (cites _USER-PROMPTS.md:11198 and :11244; those restore files are not on this worktree)",
      "claim": "The program's catalog records the spec sentences this unit must implement: agreement is not proof; evidence gates outrank popularity; consensus that fails executable tests.",
      "id": "E1-catalog-spec-sentences",
      "signal": "catalog-text",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py plus fixtures/unanimous_refuted.json",
      "claim": "A unanimous YES is not a binding YES when a legal load-bearing test bound to the claim exits non-zero.",
      "id": "E2-live-unanimous-refuted",
      "observed": {
        "outcome": "REFUTED",
        "reason": "executable-test-override",
        "unanimous_yes": true
      },
      "signal": "live-subprocess",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py plus fixtures/irrelevant_fail.json",
      "claim": "An irrelevant failing test cannot veto a sound YES.",
      "id": "E3-live-converse",
      "observed": {
        "irrelevant_failures": 1,
        "outcome": "YES"
      },
      "signal": "live-subprocess",
      "verdict": "CONFIRMED"
    }
  ],
  "fire_rule": "If tentative_outcome is YES and any legal load-bearing binding whose claim_id equals the decided claim has an executable result of FAIL, recorded outcome is REFUTED (not YES). ERROR on a legal bound test yields NOT-CHECKED and does not fall back to the tally as a binding YES.",
  "fixture_runs": {
    "irrelevant_fail": {
      "irrelevant_failure_count": 1,
      "outcome": "YES",
      "reason": "tally-irrelevant-failures-ignored"
    },
    "known_good": {
      "outcome": "YES",
      "reason": "tally"
    },
    "seat_declares": {
      "outcome": "YES",
      "rejected": [
        [
          "binder-role-forbidden:seat"
        ]
      ]
    },
    "unanimous_refuted": {
      "outcome": "REFUTED",
      "reason": "executable-test-override",
      "unanimous_yes": true
    },
    "weighted_unanimous_refuted": {
      "outcome": "REFUTED",
      "yes_weight": 10.0
    }
  },
  "floors": [
    {
      "blocks_fire_when": "a seat, majority, post-close, or voting-registrar declaration tries to make a test load-bearing",
      "design_default": "owner binding frozen at charter time",
      "hard_lower_bound": "binder_role in {owner, charter, protocol-preset, registrar} and declared_at strictly before ballot_close",
      "id": "legal-binder"
    },
    {
      "blocks_fire_when": "the failing test is bound to a different claim, including a prefix-similar claim_id",
      "design_default": "one binding per decided claim",
      "hard_lower_bound": "binding.claim_id == decided claim_id",
      "id": "claim-id-exact-match"
    },
    {
      "blocks_fire_when": "the bound test errors: outcome is NOT-CHECKED, not a binding YES",
      "design_default": "subprocess invocation run live",
      "hard_lower_bound": "legal applicable test status in {PASS, FAIL}",
      "id": "executable-result"
    }
  ],
  "kind": "council-design-note",
  "mechanism": {
    "claim_match": "exact equality of claim_id; prefix matches are irrelevant",
    "does_not_legislate_acceptance": "A passing test does not mint YES from a NO tally. This unit specifies the FAIL-overturns-YES direction required by tests_required. Factual settlement in both directions is left to TST-0274.",
    "engine": "command-center/p2-wave/probes/CNL-0068/override.py",
    "error_policy": "A legal bound test that cannot run (ERROR) yields NOT-CHECKED. The tally is recorded but is not a binding YES.",
    "forbidden_binder_roles": [
      "chair-after-close",
      "majority",
      "seat",
      "tally"
    ],
    "id": "claim-bound-load-bearing-test-override",
    "override_rule": "If tentative_outcome is YES and any legal load-bearing binding whose claim_id equals the decided claim has an executable result of FAIL, recorded outcome is REFUTED (not YES). ERROR on a legal bound test yields NOT-CHECKED and does not fall back to the tally as a binding YES.",
    "permitted_binder_roles": [
      "charter",
      "owner",
      "protocol-preset",
      "registrar"
    ],
    "steps": [
      "Parse ballot_close and compute the weighted tally. tentative_outcome is YES when yes_weight > no_weight; unanimous_yes is yes_weight > 0 and no_weight == 0.",
      "Classify each binding: binder_role must be in {owner, charter, protocol-preset, registrar}; declared_at must be strictly before ballot_close; declared_by_majority must not be true; a registrar must not also be a voting seat.",
      "Execute each invocation (live subprocess for kind=subprocess). Compare claim_id with exact equality to the decided claim.",
      "If any legal applicable result is ERROR, outcome is NOT-CHECKED.",
      "If tentative_outcome is YES and any legal applicable result is FAIL, outcome is REFUTED with reason executable-test-override.",
      "FAIL results on illegal or non-applicable bindings are recorded and do not change a sound YES."
    ],
    "summary": "Acceptance is a two-stage record: (1) weighted tally of ballots, (2) executable override. Stage 2 is claim-indexed. One FAIL on a legal binding whose claim_id equals the decided claim overturns a unanimous YES. Popularity cannot author the binding that would protect or attack that override."
  },
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py",
      "id": "probe1"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py",
      "id": "probe2"
    }
  ],
  "negative_controls": [
    {
      "bad_state_output": "FIRES outcome=REFUTED reason=executable-test-override binding_yes=False",
      "check_action": "adjudicate() sets outcome=REFUTED, binding_yes=false, reason=executable-test-override",
      "description": "The check FIRES (outcome=REFUTED) on unanimous YES plus a legal bound FAIL, and is SILENT (outcome=YES) when the same bound test PASSes.",
      "fired_on_bad_state": true,
      "good_state_output": "SILENT outcome=YES reason=tally",
      "id": "NC-unanimous-yes-bound-fail",
      "kind": "known-broken-fixture",
      "observed": "outcome=REFUTED reason=executable-test-override binding_yes=False",
      "planted_run": {
        "binding_yes": false,
        "fixture": "command-center/p2-wave/probes/CNL-0068/fixtures/unanimous_refuted.json",
        "outcome": "REFUTED",
        "reason": "executable-test-override",
        "unanimous_yes": true
      },
      "rejects": "unanimous YES ballots for claim C plus a legal load-bearing test bound to C that exits non-zero",
      "silent_on": {
        "fixture": "command-center/p2-wave/probes/CNL-0068/fixtures/known_good.json",
        "outcome": "YES",
        "reason": "tally"
      },
      "silent_on_good_state": true,
      "state_rejected": "unanimous YES ballots for claim C plus a legal load-bearing test bound to C that exits non-zero",
      "verbatim": "On the state the check is meant to reject -- a council whose recorded ballots are unanimous YES for claim C, with a load-bearing test bound to C that exits non-zero -- adjudicate() must set outcome to REFUTED and must not emit a binding decision in {YES, ACCEPT, APPROVE, PASS}. The same check must stay silent (leave a sound YES standing) when the failing test is bound to a different claim."
    }
  ],
  "question": "The spec states agreement is not proof and evidence gates outrank popularity - what is the exact mechanism by which one failing executable test overturns a unanimous vote, and who is permitted to declare a test load-bearing?",
  "report": {
    "control_ids": [
      "NC-unanimous-yes-bound-fail"
    ],
    "kind": "council-design-note",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py",
        "measured": "REFUTED",
        "method": "override.adjudicate on fixtures/unanimous_refuted.json",
        "name": "unanimous-yes-bound-fail"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py",
        "measured": "YES",
        "method": "override.adjudicate on fixtures/irrelevant_fail.json",
        "name": "irrelevant-fail-cannot-veto"
      }
    ]
  },
  "residual_unknowns": [
    "Harness-restore files 11-COUNCIL-SPECIFICATION.schema.json and _USER-PROMPTS.md are not on this worktree; protocol-preset names beyond the catalog sentences are NOT-CHECKED.",
    "CNL-0023 weight-provenance schema is not delivered; this unit treats weights as numbers and does not validate provenance records.",
    "TST-0274 both-direction factual settlement (passing probe forcing YES against a unanimous NO) is out of scope for this design note."
  ],
  "reviewer": {
    "counterexample": {
      "id": "CE-IRRELEVANT-FAIL",
      "instance": "Three YES votes on claim.ship-ready plus a failing executable bound to claim.other. If outcome is not YES, the relevance claim is REFUTED.",
      "observed_outcome": "YES",
      "survived": true
    },
    "further_instances": [
      "CE-WEIGHTED-UNANIMITY",
      "CE-SEAT-BINDER",
      "CE-POST-CLOSE",
      "CE-MAJORITY-DECLARE",
      "CE-PREFIX-CLAIM"
    ],
    "independent": true,
    "method": "Named probe2 re-runs override.adjudicate on the fixtures and does not read this note's answer/mechanism.summary to compute the tally. It constructs counterexample instances rather than stating REFUTED-NOT-ATTEMPTED.",
    "reviewer_id": "CNL-0068-probe2-independent-recount",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0068",
  "source_availability": {
    "missing": [
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
    ],
    "requested_paths_present": false
  },
  "source_files_on_this_worktree": {
    "council_protocols_and_presets": false,
    "council_specification_schema": false,
    "disclosure": "The catalog inputs under C:/Users/Prekzursil/.claude/harness-restore-20260806/ are absent here. Spec sentences are taken from WORK-UNIT-CATALOG.json evidence_requirement for CNL-0068, not from a fabricated file:line of a missing restore tree.",
    "harness_restore_user_prompts": false
  },
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0068/probe1_unanimous_refuted.py",
      "id": "T1-unanimous-but-refuted",
      "required_by_catalog": "a unanimous-but-refuted fixture: the council votes YES, a test fails, and the recorded outcome must NOT be YES",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0068/probe2_converse_reviewer.py",
      "id": "T2-converse-irrelevant-fail",
      "required_by_catalog": "a converse control: an irrelevant failing test must not be able to veto a sound decision",
      "result": "PASS"
    }
  ],
  "title": "Evidence outranks popularity: the executable-test override of a majority",
  "ts": "2026-08-25T00:55:34Z",
  "unit_id": "CNL-0068",
  "who_may_declare_load_bearing": {
    "conflict_rule": "The participant who declares a test load-bearing for this council must not be a voting seat on the same run, except the owner/charter binding frozen before ballots open. A registrar listed in votes is rejected. A majority cannot vote a test into load-bearing status, because that would let popularity name the evidence gate.",
    "forbidden": [
      "chair-after-close",
      "majority",
      "seat",
      "tally",
      "post-close declaration",
      "voting registrar"
    ],
    "permitted": [
      "charter",
      "owner",
      "protocol-preset",
      "registrar"
    ]
  }
}
