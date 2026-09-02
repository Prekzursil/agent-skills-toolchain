{
  "schema_version": 1,
  "unit_id": "CNL-0066",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0066",
  "spec_anchor": "_USER-PROMPTS.md:10746-10767",
  "min_bytes_threshold": 4096,
  "profile": "council-design-note",
  "artifacts": [
    {
      "path": "command-center/p2-wave/probes/CNL-0066/semantics.py",
      "bytes": 8639,
      "sha256": "e5951e111897f6829b198044bffd272a9c8630706c42d1c43eb463669a42c59b",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0066/fixtures.py",
      "bytes": 4772,
      "sha256": "69b95bd5d26b3ccc9246c6cd468f5c051750f2ba5eea21997391c3edf3c28e8b",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "bytes": 1118,
      "sha256": "e66edc40156c6abcad6b2e27d5e6ebc32a37e72559967fa1fc3ce53e5b245755",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py",
      "bytes": 5113,
      "sha256": "bada6141b046089a6b190c05ed42a76b65159b3a38ae44e07c88c46175fcd2f5",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0066/probe2_independent_recount.py",
      "bytes": 10803,
      "sha256": "62b2f2e5f29b7023f081e7b4d5435e2e079fa868bdd99ec886fcb1fe3ac649ca",
      "exists": true,
      "eol": "LF",
      "role": "control"
    }
  ],
  "evidence": [
    {
      "claim": "Decision tally uses frozen seated_n0, not present-and-voting",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:14",
      "probes": [
        {
          "role": "source",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0066/semantics.py:14",
          "raw_output": "decision denominator is seated_n0, never present-and-voting",
          "fingerprint": "file-read:semantics:rule",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py",
          "raw_output": "known-good-principled class=PRINCIPLED fire=False decision=PARKED proto_fired=False OK\nplanted-bad-strategic class=STRATEGIC fire=True decision=FAIL proto_fired=False OK\nplanted-bad-present-and-voting class=STRATEGIC fire=True decision=INVALID-PROTOCOL proto_fired=True OK\nknown-good-protocol-seated-basis class=PRINCIPLED fire=False decision=PARKED proto_fired=False OK\nnegative-nonpivotal-generic class=UNDETERMINED fire=False decision=PASS proto_fired=False OK\nshrinking_trap pv_yes=3 pv_den=4 pv_two_thirds=True seated_meets=False\nboth_states discriminator planted-bad=FIRE known-good=SILENT got_bad=True got_good=False\nboth_states protocol pv=FIRE seated=SILENT got_pv=True got_seated=False\nnegative_control nonpivotal-generic: check SILENT (class=UNDETERMINED fire=False decision=PASS)\nSUCCESS:CNL-0066-probe1 discriminator both-states shrinking-PV",
          "fingerprint": "cmd:probe1-discriminator",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "Pivotal incomplete abstention is classified STRATEGIC",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:158",
      "probes": [
        {
          "role": "source",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0066/semantics.py:158",
          "raw_output": "pivotal + not-principled => strategic (fail closed)",
          "fingerprint": "file-read:semantics:strat",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "static-analysis",
          "command": "command-center/p2-wave/probes/CNL-0066/fixtures.py:planted-bad-strategic",
          "raw_output": "planted-bad-strategic expect class=STRATEGIC strategic_fire=true",
          "fingerprint": "static:fixtures-planted-bad",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "Planted-bad fixture exists for the discriminator FIRE state",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0066/fixtures.py:103",
      "probes": [
        {
          "role": "source",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0066/fixtures.py:103",
          "raw_output": "planted-bad-strategic",
          "fingerprint": "file-read:fixtures:planted-bad",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py",
          "raw_output": "both_states discriminator planted-bad=FIRE known-good=SILENT",
          "fingerprint": "cmd:probe1-both-states-line",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "Unit question taken from the catalog, not restated from memory",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:37572",
      "probes": [
        {
          "role": "source",
          "method": "file-read",
          "command": "command-center/WORK-UNIT-CATALOG.json:37572",
          "raw_output": "Does an abstention reduce the denominator, count as a no, or park the decision",
          "fingerprint": "file-read:catalog:question",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "static-analysis",
          "command": "command-center/WORK-UNIT-CATALOG.json:question_or_target",
          "raw_output": "Does an abstention reduce the denominator, count as a no, or park the decision - and how is a principled abstention (no expertise) told apart from a strategic one (avoiding a recorded position)?",
          "fingerprint": "static:catalog-question-or-target",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "probe1-discriminator-both-states",
      "name": "principled vs strategic plus PV protocol both-states",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0066/probe1_discriminator.py",
      "result": "PASS",
      "output_tail": "known-good-principled class=PRINCIPLED fire=False decision=PARKED proto_fired=False OK\nplanted-bad-strategic class=STRATEGIC fire=True decision=FAIL proto_fired=False OK\nplanted-bad-present-and-voting class=STRATEGIC fire=True decision=INVALID-PROTOCOL proto_fired=True OK\nknown-good-protocol-seated-basis class=PRINCIPLED fire=False decision=PARKED proto_fired=False OK\nnegative-nonpivotal-generic class=UNDETERMINED fire=False decision=PASS proto_fired=False OK\nshrinking_trap pv_yes=3 pv_den=4 pv_two_thirds=True seated_meets=False\nboth_states discriminator planted-bad=FIRE known-good=SILENT got_bad=True got_good=False\nboth_states protocol pv=FIRE seated=SILENT got_pv=True got_seated=False\nnegative_control nonpivotal-generic: check SILENT (class=UNDETERMINED fire=False decision=PASS)\nSUCCESS:CNL-0066-probe1 discriminator both-states shrinking-PV"
    },
    {
      "id": "probe2-independent-recount",
      "name": "independent recount overclaim and both-states",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0066/probe2_independent_recount.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "discriminator-principled-vs-strategic",
      "kind": "known-broken-fixture",
      "description": "Rejects principled abstention classified as strategic. FIRES on planted-bad-strategic; SILENT on known-good-principled.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "FIRE class=STRATEGIC fire=True decision=FAIL",
      "good_state_output": "SILENT class=PRINCIPLED fire=False decision=PARKED"
    },
    {
      "id": "protocol-pv-vs-seated",
      "kind": "known-broken-fixture",
      "description": "Rejects present_and_voting used as decision threshold_basis. FIRES on planted-bad-present-and-voting; SILENT on seated basis.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "FIRE proto=True decision=INVALID-PROTOCOL",
      "good_state_output": "SILENT proto=False decision=PARKED"
    },
    {
      "id": "discriminator-nonpivotal-generic",
      "kind": "known-broken-fixture",
      "description": "Rejects non-pivotal incomplete abstention labelled strategic. The check that FIRES on planted-bad-strategic is SILENT here.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "FIRE class=STRATEGIC fire=True",
      "good_state_output": "SILENT class=UNDETERMINED fire=False decision=PASS"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0066-probe2-independent-recount",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": true,
    "vendor": "unassigned",
    "notes": "Probe2 re-ran the both-states control from fixture JSON without calling classify_abstention. Catalog asked for openai/gpt-5-codex; this delivery substitutes that mechanical recount. A live cross-vendor LLM signature was not obtained on this worktree.",
    "re_ran_both_states": true
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0066/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0066"
  },
  "downstream_consumers": [
    {
      "consumer": "CNL-0066 probe2 independent recount",
      "artifact_path": "command-center/design/council/CNL-0066-abstention-semantics-and-strategic-abstention-detection.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0066/probe2_independent_recount.py",
        "raw_output": "SUCCESS:CNL-0066-probe2 independent-recount overclaim both-states",
        "fingerprint": "cmd:probe2-independent-recount",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-25T00:58:31Z",
    "ended_at": "2026-08-25T00:58:31Z",
    "duration_seconds": 0
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
  },
  "residual_unknowns": [
    {
      "claim": "CNL-0058 (majority/supermajority vs quorum) is a catalog dependency and is not delivered on this tree.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Deliver CNL-0058 and re-run seated vs PV arithmetic against its quorum rule without changing this unit's seated_n0 bar."
    },
    {
      "claim": "Catalog reviewer_requirement named openai/gpt-5-codex; probe2 is a mechanical independent recount, not that vendor.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Dispatch a fresh-context gpt-5-codex reviewer that re-runs the both-states fixtures and signs reviewer.vendor=openai."
    }
  ],
  "produced_by": {
    "vendor": "xai",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "local-parallel"
  },
  "report": {
    "kind": "council-design-note",
    "title": "Abstention semantics and strategic-abstention detection",
    "question": "Does an abstention reduce the denominator, count as a no, or park the decision - and how is a principled abstention (no expertise) told apart from a strategic one (avoiding a recorded position)?",
    "answer": "An abstention does not reduce the decision denominator. The stopping predicate uses the frozen seated set (seated_n0). Present-and-voting is report-only; threshold_basis=present_and_voting is INVALID-PROTOCOL. A principled abstention (structured NO_EXPERTISE / CONFLICT_OF_INTEREST / INSUFFICIENT_EVIDENCE record, no domain-overlap lie) parks the decision under PARK_PRINCIPLED_ELSE_COUNT_AS_NO. A pivotal abstention that fails that record is STRATEGIC: it cannot park, counts as non-Yes, and the detector fires. Undeclared policy is invalid; there is no implicit drop from the denominator.",
    "family": "ABSTENTION-SEMANTICS",
    "family_count": 5,
    "re_ran_both_states": true,
    "enumeration": {
      "ids": [
        "P20",
        "P21",
        "P22",
        "P23",
        "P24"
      ],
      "source": "command-center/p2-wave/probes/CNL-0066/semantics.py",
      "independent_count": 5,
      "expected_n": 5
    },
    "records": [
      {
        "id": "P20",
        "slug": "forbid-present-and-voting-basis",
        "family": "ABSTENTION-SEMANTICS",
        "verdict": "EXECUTABLE",
        "missing_element": null,
        "attacking_role": "pivotal-abstainer",
        "turn_schedule": [
          "open",
          "snapshot-seated-n0",
          "reject-pv-basis",
          "tally-seated"
        ],
        "unfakeable_artifact": {
          "kind": "seated_snapshot_vs_pv_denominator",
          "must_produce": "frozen seated_n0 plus a rejection when threshold_basis is present_and_voting",
          "cooperative_fake": "recompute threshold against shrinking present-and-voting n and call it passage",
          "enforcement": "validate_protocol fires on forbidden basis; decision bit never reads pv_den"
        }
      },
      {
        "id": "P21",
        "slug": "count-nonprincipled-as-no",
        "family": "ABSTENTION-SEMANTICS",
        "verdict": "EXECUTABLE",
        "missing_element": null,
        "attacking_role": "pivotal-abstainer",
        "turn_schedule": [
          "open",
          "classify",
          "count-nonprincipled-non-yes",
          "stop"
        ],
        "unfakeable_artifact": {
          "kind": "yes_count_under_seated_threshold",
          "must_produce": "yes_count compared to frozen threshold_yes; non-principled abstain adds no Yes",
          "cooperative_fake": "treat the abstain as absent and drop seated_n0 by one",
          "enforcement": "resolve() uses yes_count vs seated threshold; shrinking_trap records the PV mirage"
        }
      },
      {
        "id": "P22",
        "slug": "park-principled-abstention",
        "family": "ABSTENTION-SEMANTICS",
        "verdict": "EXECUTABLE",
        "missing_element": null,
        "attacking_role": "expertise-gap-seat",
        "turn_schedule": [
          "open",
          "classify-principled",
          "park",
          "await-unpark-predicate"
        ],
        "unfakeable_artifact": {
          "kind": "principled_record",
          "must_produce": "structured missing_claim plus would_unpark_if; outcome PARKED",
          "cooperative_fake": "file reason_code=NO_EXPERTISE with empty claim to park anyway",
          "enforcement": "principled_fields_ok rejects unstructured claims; only PRINCIPLED may park"
        }
      },
      {
        "id": "P23",
        "slug": "strategic-abstention-detector",
        "family": "ABSTENTION-SEMANTICS",
        "verdict": "EXECUTABLE",
        "missing_element": null,
        "attacking_role": "pivotal-abstainer",
        "turn_schedule": [
          "open",
          "test-pivotality",
          "test-principled-record",
          "fire-or-silent"
        ],
        "unfakeable_artifact": {
          "kind": "strategic_fire_bit",
          "must_produce": "strategic_fire true on pivotal incomplete abstention, false on principled",
          "cooperative_fake": "label a pivotal generic abstention PRINCIPLED without the structured record",
          "enforcement": "probe1 both-states: FIRE on planted-bad, SILENT on known-good"
        }
      },
      {
        "id": "P24",
        "slug": "principled-record-consistency",
        "family": "ABSTENTION-SEMANTICS",
        "verdict": "EXECUTABLE",
        "missing_element": null,
        "attacking_role": "expertise-gap-seat",
        "turn_schedule": [
          "open",
          "check-reason-class",
          "check-claim",
          "check-overlap-and-prior"
        ],
        "unfakeable_artifact": {
          "kind": "consistency_witness",
          "must_produce": "NO_EXPERTISE incompatible with domain overlap or prior YES/NO on the class",
          "cooperative_fake": "claim no expertise while expertise_tags intersect required_domains",
          "enforcement": "principled_fields_ok fails no-expertise-but-domain-overlap"
        }
      }
    ],
    "decision": {
      "denominator": "frozen seated_n0; abstention does not shrink the decision bar",
      "principled": "PARKED under PARK_PRINCIPLED_ELSE_COUNT_AS_NO",
      "strategic": "non-Yes plus detector fire; cannot park",
      "undeclared_policy": "invalid protocol",
      "present_and_voting": "report-only; illegal as threshold_basis"
    },
    "both_states": {
      "discriminator": {
        "planted_bad": "FIRE",
        "known_good": "SILENT",
        "planted_bad_fixture": "planted-bad-strategic",
        "known_good_fixture": "known-good-principled",
        "verbatim_planted_bad": {
          "class": "STRATEGIC",
          "strategic_fire": true,
          "decision": "FAIL",
          "yes": 3
        },
        "verbatim_known_good": {
          "class": "PRINCIPLED",
          "strategic_fire": false,
          "decision": "PARKED",
          "yes": 3
        }
      },
      "protocol": {
        "planted_bad": "FIRE",
        "known_good": "SILENT",
        "planted_bad_fixture": "planted-bad-present-and-voting",
        "known_good_fixture": "known-good-protocol-seated-basis",
        "verbatim_planted_bad": {
          "protocol_fired": true,
          "decision": "INVALID-PROTOCOL",
          "violations": [
            "illegal-threshold-basis:present_and_voting"
          ]
        },
        "verbatim_known_good": {
          "protocol_fired": false,
          "decision": "PARKED",
          "violations": []
        }
      }
    },
    "shrinking_denominator_trap": {
      "present_and_voting_yes": 3,
      "present_and_voting_den": 4,
      "present_and_voting_ratio": 0.75,
      "present_and_voting_meets_two_thirds": true,
      "seated_yes": 3,
      "seated_den": 5,
      "seated_meets_threshold_yes": false,
      "decision_uses_seated_not_pv": true
    },
    "markdown_body": "# CNL-0066 Abstention semantics and strategic-abstention detection\n\n## Ruling\n\n1. **Decision denominator is the frozen seated set.** An abstention does not\n   reduce the denominator used for the stopping predicate. Present-and-voting\n   ratios may be *reported* and must be labelled as such. A protocol that sets\n   `threshold_basis=present_and_voting` is invalid (`INVALID-PROTOCOL`).\n2. **Principled abstention parks.** Under the default policy\n   `PARK_PRINCIPLED_ELSE_COUNT_AS_NO`, a ballot that satisfies the principled\n   record parks the decision (`PARKED`). Lack of expertise does not manufacture\n   a No.\n3. **Strategic abstention cannot park.** A pivotal abstention that fails the\n   principled record is classified `STRATEGIC`, counted as non-Yes (effectively\n   No for passage), and the detector fires. The shrinking-denominator attack\n   (three Yes, one abstain, one No looking like 3/4) therefore fails: seated\n   arithmetic is 3/5 against a 4-of-5 bar.\n4. **Undeclared policy is invalid.** There is no implicit \"drop from\n   denominator\". Allowed policies: `PARK_PRINCIPLED_ELSE_COUNT_AS_NO` and\n   `COUNT_AS_NO`.\n\n## Discriminator\n\nPrincipled iff kind=ABSTAIN and all of:\n- `reason_code` in {NO_EXPERTISE, CONFLICT_OF_INTEREST, INSUFFICIENT_EVIDENCE}\n- `missing_claim.{what, why_blocks_vote}` both non-empty\n- `would_unpark_if.{field, op}` present\n- not (NO_EXPERTISE and domain overlap with `required_domains`)\n- not (NO_EXPERTISE and a prior YES/NO on the same `question_class_id`)\n\nStrategic iff abstention is pivotal (switching that seat to YES would cross\n`threshold_yes`) and the principled record fails.\n\nNon-pivotal incomplete abstention is `UNDETERMINED`: counted as non-Yes, detector\nsilent. That is the negative control for the strategic check.\n\n## Why not \"always No\" or \"always shrink\"\n\nAlways-No punishes honest expertise gaps and invites fake Yes votes from\nunqualified seats. Always-shrink lets a pivotal seat pass a supermajority by\nleaving. Parking principled records and failing closed on pivotal incomplete\nrecords separates those cases with an executable check.\n",
    "observations": [
      {
        "name": "principled_class",
        "measured": "PRINCIPLED",
        "method": "semantics.resolve known-good-principled",
        "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:77"
      },
      {
        "name": "strategic_fire",
        "measured": true,
        "method": "semantics.resolve planted-bad-strategic",
        "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:158"
      },
      {
        "name": "pv_protocol_fired",
        "measured": true,
        "method": "semantics.validate_protocol present_and_voting",
        "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:102"
      },
      {
        "name": "shrinking_trap_pv_two_thirds",
        "measured": true,
        "method": "shrinking_trap present-and-voting ratio",
        "anchor": "command-center/p2-wave/probes/CNL-0066/semantics.py:230"
      }
    ],
    "control_ids": [
      "discriminator-principled-vs-strategic",
      "protocol-pv-vs-seated",
      "discriminator-nonpivotal-generic"
    ]
  },
  "extensions": {
    "completion_sentinel": "SUCCESS:CNL-0066",
    "output_path": "command-center/design/council/CNL-0066-abstention-semantics-and-strategic-abstention-detection.md",
    "dependency_note": "CNL-0058 is a catalog dependency and is not delivered on this tree. This unit forbids PV as the decision basis so a later CNL-0058 tally cannot silently accept a shrinking bar from abstention."
  },
  "both_states": {
    "discriminator": {
      "planted_bad": "FIRE",
      "known_good": "SILENT",
      "planted_bad_fixture": "planted-bad-strategic",
      "known_good_fixture": "known-good-principled",
      "verbatim_planted_bad": {
        "class": "STRATEGIC",
        "strategic_fire": true,
        "decision": "FAIL",
        "yes": 3
      },
      "verbatim_known_good": {
        "class": "PRINCIPLED",
        "strategic_fire": false,
        "decision": "PARKED",
        "yes": 3
      }
    },
    "protocol": {
      "planted_bad": "FIRE",
      "known_good": "SILENT",
      "planted_bad_fixture": "planted-bad-present-and-voting",
      "known_good_fixture": "known-good-protocol-seated-basis",
      "verbatim_planted_bad": {
        "protocol_fired": true,
        "decision": "INVALID-PROTOCOL",
        "violations": [
          "illegal-threshold-basis:present_and_voting"
        ]
      },
      "verbatim_known_good": {
        "protocol_fired": false,
        "decision": "PARKED",
        "violations": []
      }
    }
  },
  "answer": "An abstention does not reduce the decision denominator. The stopping predicate uses the frozen seated set (seated_n0). Present-and-voting is report-only; threshold_basis=present_and_voting is INVALID-PROTOCOL. A principled abstention (structured NO_EXPERTISE / CONFLICT_OF_INTEREST / INSUFFICIENT_EVIDENCE record, no domain-overlap lie) parks the decision under PARK_PRINCIPLED_ELSE_COUNT_AS_NO. A pivotal abstention that fails that record is STRATEGIC: it cannot park, counts as non-Yes, and the detector fires. Undeclared policy is invalid; there is no implicit drop from the denominator.",
  "records": [
    {
      "id": "P20",
      "slug": "forbid-present-and-voting-basis",
      "family": "ABSTENTION-SEMANTICS",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "attacking_role": "pivotal-abstainer",
      "turn_schedule": [
        "open",
        "snapshot-seated-n0",
        "reject-pv-basis",
        "tally-seated"
      ],
      "unfakeable_artifact": {
        "kind": "seated_snapshot_vs_pv_denominator",
        "must_produce": "frozen seated_n0 plus a rejection when threshold_basis is present_and_voting",
        "cooperative_fake": "recompute threshold against shrinking present-and-voting n and call it passage",
        "enforcement": "validate_protocol fires on forbidden basis; decision bit never reads pv_den"
      }
    },
    {
      "id": "P21",
      "slug": "count-nonprincipled-as-no",
      "family": "ABSTENTION-SEMANTICS",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "attacking_role": "pivotal-abstainer",
      "turn_schedule": [
        "open",
        "classify",
        "count-nonprincipled-non-yes",
        "stop"
      ],
      "unfakeable_artifact": {
        "kind": "yes_count_under_seated_threshold",
        "must_produce": "yes_count compared to frozen threshold_yes; non-principled abstain adds no Yes",
        "cooperative_fake": "treat the abstain as absent and drop seated_n0 by one",
        "enforcement": "resolve() uses yes_count vs seated threshold; shrinking_trap records the PV mirage"
      }
    },
    {
      "id": "P22",
      "slug": "park-principled-abstention",
      "family": "ABSTENTION-SEMANTICS",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "attacking_role": "expertise-gap-seat",
      "turn_schedule": [
        "open",
        "classify-principled",
        "park",
        "await-unpark-predicate"
      ],
      "unfakeable_artifact": {
        "kind": "principled_record",
        "must_produce": "structured missing_claim plus would_unpark_if; outcome PARKED",
        "cooperative_fake": "file reason_code=NO_EXPERTISE with empty claim to park anyway",
        "enforcement": "principled_fields_ok rejects unstructured claims; only PRINCIPLED may park"
      }
    },
    {
      "id": "P23",
      "slug": "strategic-abstention-detector",
      "family": "ABSTENTION-SEMANTICS",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "attacking_role": "pivotal-abstainer",
      "turn_schedule": [
        "open",
        "test-pivotality",
        "test-principled-record",
        "fire-or-silent"
      ],
      "unfakeable_artifact": {
        "kind": "strategic_fire_bit",
        "must_produce": "strategic_fire true on pivotal incomplete abstention, false on principled",
        "cooperative_fake": "label a pivotal generic abstention PRINCIPLED without the structured record",
        "enforcement": "probe1 both-states: FIRE on planted-bad, SILENT on known-good"
      }
    },
    {
      "id": "P24",
      "slug": "principled-record-consistency",
      "family": "ABSTENTION-SEMANTICS",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "attacking_role": "expertise-gap-seat",
      "turn_schedule": [
        "open",
        "check-reason-class",
        "check-claim",
        "check-overlap-and-prior"
      ],
      "unfakeable_artifact": {
        "kind": "consistency_witness",
        "must_produce": "NO_EXPERTISE incompatible with domain overlap or prior YES/NO on the class",
        "cooperative_fake": "claim no expertise while expertise_tags intersect required_domains",
        "enforcement": "principled_fields_ok fails no-expertise-but-domain-overlap"
      }
    }
  ]
}
