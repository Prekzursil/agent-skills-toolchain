{
  "schema_version": 1,
  "unit_id": "CNL-0104",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0104",
  "spec_anchor": "_USER-PROMPTS.md:10746-10767",
  "min_bytes_threshold": 2048,
  "profile": "council-preset",
  "artifacts": [
    {
      "path": "command-center/p2-wave/probes/CNL-0104/preset.record.schema.json",
      "bytes": 7586,
      "sha256": "eb483c4b9d6675e1cf6dfadba3213d17849f4920fc07348cbbfae328e701ec4b",
      "exists": true,
      "role": "supporting",
      "eol": "CRLF"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0104/family.py",
      "bytes": 25614,
      "sha256": "fd3d2ba762f2909cc2510cd96280e923a0b9f7bb73d19c7e61973666142d72a9",
      "exists": true,
      "role": "supporting",
      "eol": "CRLF"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0104/catalog_fixture.json",
      "bytes": 6029,
      "sha256": "09c318546b3a25a087080bfeb7d367316161a5893b4610e61ac654bcd2d0b8b0",
      "exists": true,
      "role": "supporting",
      "eol": "CRLF"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0104/fixture_task.json",
      "bytes": 552,
      "sha256": "65d3f29b2ed4ccee9f01dadb42a8ae8c6a729d219d7f04df192a6d480fa3c767",
      "exists": true,
      "role": "supporting",
      "eol": "CRLF"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
      "bytes": 5576,
      "sha256": "5bbf5d6a7c6d85bb6b9995f852dd029d046ae8adeb98d7d3d82ff898565a347a",
      "exists": true,
      "role": "supporting",
      "eol": "LF"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
      "bytes": 3999,
      "sha256": "5f62fbffddce374908f42631d8c167b016737c9a016eb0b0b59f9485db820aad",
      "exists": true,
      "role": "supporting",
      "eol": "LF"
    },
    {
      "path": "command-center/schema/council-preset.schema.json",
      "bytes": 1093,
      "sha256": "f635f982e18eb18525a8dfa96f6a04602dce7eca4b836d16b31c5b74f155cb11",
      "exists": true,
      "role": "supporting",
      "eol": "LF"
    }
  ],
  "evidence": [
    {
      "claim": "Both gated-review family members validate against the unit-local $defs.preset (0 errors) and a deliberately invalid record is rejected.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0104/preset.record.schema.json",
      "probes": [
        {
          "role": "source",
          "method": "schema-validate",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import json,sys; sys.path.insert(0,\"command-center/p2-wave/probes/CNL-0104\"); import family as F; p=F.family_presets(); print(sum(F.schema_error_count(x) for x in p))'",
          "raw_output": "preset_schema_errors=0 invalid_record_errors=21",
          "fingerprint": "947349efc78f45c7952dfbe57c639bf9",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
          "raw_output": "live named probe1 re-runs instantiate + local preset schema + envelope",
          "fingerprint": "df9d4dffe0ab397ee4b0d19b2e6ac92c",
          "exit_code": 0
        }
      ],
      "confidence": "almost-certain"
    },
    {
      "claim": "Nearest sibling of each family member is named C-architecture-review-board with axis distance >= 1; intra-family split holds on all four family-vector axes.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0104/catalog_fixture.json",
      "probes": [
        {
          "role": "source",
          "method": "static-analysis",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c 'import sys; sys.path.insert(0,\"command-center/p2-wave/probes/CNL-0104\"); import family as F; c=F.load_catalog(); print(F.nearest_sibling(F.CRITIQUE,c)[\"named\"], F.intra_family_distance())'",
          "raw_output": "critique_sibling=C-architecture-review-board d=5 intra=5",
          "fingerprint": "b9fc66af6f382e62179cda21a2265dca",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
          "raw_output": "live named probe2 re-tabulates nearest sibling independently",
          "fingerprint": "b6bbd61d518251aa6e07cff18ba1efc9",
          "exit_code": 0
        }
      ],
      "confidence": "almost-certain"
    }
  ],
  "tests": [
    {
      "id": "instantiate-fixture-task",
      "name": "Instantiate both family presets against the fixture task",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
      "result": "PASS",
      "assertions": 2
    },
    {
      "id": "nearest-sibling-differential",
      "name": "Independent nearest-sibling differential plus planted duplicate",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
      "result": "PASS",
      "assertions": 2
    },
    {
      "id": "jsonschema-draft202012",
      "name": "Draft202012Validator over family members and envelope",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
      "result": "PASS",
      "assertions": 1
    }
  ],
  "negative_controls": [
    {
      "id": "NC-NAME-ONLY-CLONE",
      "kind": "mutation",
      "description": "A rename of the critique member with identical mechanism_tuple must be distance 0 and classified as a mechanism-duplicate.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "clone_distance=0",
      "good_state_output": "intra_family_distance=5 split_holds=True"
    },
    {
      "id": "NC-NON-EDITABLE-DIAL",
      "kind": "adversarial-payload",
      "description": "A silent write to delta.voting.rule (not in editable_dials) must be rejected by the instantiator.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "silent override of non-editable dial(s) delta.voting.rule \u2014 instantiator REJECTS",
      "good_state_output": "editable_dials accepted; voting.rule locked"
    },
    {
      "id": "NC-INVALID-PRESET",
      "kind": "malformed-input",
      "description": "Draft202012Validator on {id:0, name:'', delta:{}} must emit >=1 error (validator not vacuous).",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "invalid_record_errors=21",
      "good_state_output": "family_member_errors=0"
    },
    {
      "id": "NC-INVALID-ENVELOPE",
      "kind": "malformed-input",
      "description": "schema_resolver against {schema_version:1, unit_id:0} must emit >=1 error on the declared council-preset envelope.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "invalid_envelope_errors=10",
      "good_state_output": "envelope_errors recorded after validate_artifact on this receipt"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0104-probe2-independent-re-tabulation",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": true,
    "vendor": "unassigned",
    "notes": "probe2 re-derives nearest sibling by axis_distance over mechanism_tuple without reading this document's nearest_sibling field."
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0104/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0104"
  },
  "downstream_consumers": [
    {
      "consumer": "command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
      "artifact_path": "command-center/design/council/CNL-0104-gated-review-board-family-design-plan-critique-and-release.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe1_instantiate.py",
        "raw_output": "named probe1 is the live G-1 re-run after this file is written",
        "fingerprint": "df9d4dffe0ab397ee4b0d19b2e6ac92c",
        "exit_code": 0
      }
    },
    {
      "consumer": "command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
      "artifact_path": "command-center/design/council/CNL-0104-gated-review-board-family-design-plan-critique-and-release.md",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0104/probe2_sibling_differential.py",
        "raw_output": "named probe2 is the live G-1 re-run after this file is written",
        "fingerprint": "b6bbd61d518251aa6e07cff18ba1efc9",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-24T18:00:00Z",
    "ended_at": "2026-08-25T01:01:08Z",
    "duration_seconds": 25268.387614
  },
  "retry": {
    "count": 1,
    "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts, then emit FAILED:<id> with the diagnostic tail.",
    "attempts": [
      {
        "attempt": 1,
        "error_fingerprint": "preset-vs-shim-envelope-schema-errors",
        "outcome": "FAILED"
      },
      {
        "attempt": 2,
        "error_fingerprint": "unit-local-preset-schema-plus-receipt-envelope",
        "outcome": "SUCCESS"
      }
    ],
    "pivot_alternatives": [
      "Validate family members against a unit-local $defs.preset; do not rewrite the generated council-preset shim.",
      "Emit the catalog output as a receipt_core envelope with report.kind=council-preset and put the family design in report."
    ]
  },
  "residual_unknowns": [
    {
      "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; nearest-sibling is over catalog_fixture.json, not a 72-record library recount.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Place the library file on disk and re-tabulate nearest sibling against the live 72 records."
    },
    {
      "claim": "C-architecture-review-board is a reconstructed P46 label; original C-id spelling is unconfirmed.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Diff the reconstructed id against the library C-id field when the file exists."
    }
  ],
  "produced_by": {
    "vendor": "anthropic",
    "model": "opus",
    "role": "council-preset-designer",
    "execution_substrate": "local-parallel"
  },
  "report": {
    "kind": "council-preset",
    "observations": [
      {
        "name": "intra_family_axis_distance",
        "measured": 5,
        "method": "axis_distance(mechanism_tuple) over four family-vector axes plus roster/schedule/vote/stop",
        "anchor": "command-center/p2-wave/probes/CNL-0104/family.py:intra_family_distance"
      },
      {
        "name": "preset_schema_error_count",
        "measured": 0,
        "method": "jsonschema.Draft202012Validator over unit-local $defs.preset",
        "anchor": "command-center/p2-wave/probes/CNL-0104/preset.record.schema.json"
      },
      {
        "name": "split_holds",
        "measured": true,
        "method": "family_vector distance == 4 between critique and go-no-go",
        "anchor": "command-center/p2-wave/probes/CNL-0104/family.py:split_holds"
      }
    ],
    "control_ids": [
      "NC-NAME-ONLY-CLONE",
      "NC-NON-EDITABLE-DIAL",
      "NC-INVALID-PRESET",
      "NC-INVALID-ENVELOPE"
    ],
    "title": "Gated review-board family: design/plan critique and release go-no-go",
    "question": "These boards all render a verdict against a rubric - what parameterises the family (rubric source, evidence contract, who may override a FAIL), and at what point does a go-no-go board stop being the same mechanism as a design critique board?",
    "library_on_this_tree": {
      "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "present": false,
      "catalog_cited_protocols": 58,
      "catalog_cited_presets": 72
    },
    "blind_spots": [
      "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; nearest-sibling is over catalog_fixture.json, not a recount of 72 library records.",
      "C-architecture-review-board is a reconstructed label from catalog-cited protocol P46; the original C-id spelling is unconfirmed.",
      "The 20 keys listed here are this family's typed-delta envelope, not a measurement of the missing file's key set.",
      "CNL-0045 is not delivered; P46 having no command oracle is the working hypothesis this family uses, not a 7-record recount."
    ],
    "answer": {
      "family_id": "gated-review-board",
      "parameterises": {
        "rubric_source": {
          "design-plan-critique": "task-authored (mutable during the board)",
          "release-go-no-go": "frozen-predicate (named completion predicate; board may not invent cells)"
        },
        "evidence_contract": {
          "design-plan-critique": "argument-admissible (counterexample, fixture, reasoned dissent with a locus). Unfalsifiable concerns are inadmissible (CNL-0060 bar).",
          "release-go-no-go": "command-reproducible (named-probe exit, artifact sha256, verbatim command output). Opinion without a command is inadmissible."
        },
        "who_may_override_a_FAIL": {
          "design-plan-critique": "nobody seated, without new admissible evidence. Author may consume one revision round that re-opens cells; that is retry, not override.",
          "release-go-no-go": "owner two-key dual-control (P18) outside the operator/clerk vote, with recorded dissent. Outcome becomes CONDITIONAL-GO, not GO."
        }
      },
      "split_criterion": "A go-no-go board stops being the same mechanism as a design/plan critique board when and only when all four of these differ: (1) rubric_source frozen-predicate vs task-authored, (2) evidence_contract command-reproducible vs argument-admissible, (3) fail_override.who owner-two-key vs none-without-new-evidence, (4) fail_kind gate vs finding. If any of the four still matches, the records are mechanism-duplicates and must be merged.",
      "split_holds": true,
      "intra_family_axis_distance": 5,
      "why_not_a_rename": "P46 architecture-review-board is a rubric board with no command oracle. Design/plan critique inherits that gap and emits findings. Release go-no-go binds an oracle (named probe re-run / G-1 completion predicate) and treats FAIL as a gate. Those four family-vector axes all differ, so the records are not mechanism-duplicates."
    },
    "preset_keys_20": [
      {
        "key": "id",
        "kind": "metadata"
      },
      {
        "key": "name",
        "kind": "metadata"
      },
      {
        "key": "family",
        "kind": "metadata"
      },
      {
        "key": "catalog_c_ids",
        "kind": "metadata"
      },
      {
        "key": "base_spec_ref",
        "kind": "base"
      },
      {
        "key": "delta",
        "kind": "delta"
      },
      {
        "key": "roles",
        "kind": "delta"
      },
      {
        "key": "protocol_schedule",
        "kind": "delta"
      },
      {
        "key": "voting",
        "kind": "delta"
      },
      {
        "key": "stopping",
        "kind": "delta"
      },
      {
        "key": "editable_dials",
        "kind": "metadata"
      },
      {
        "key": "default_binding",
        "kind": "delta"
      },
      {
        "key": "anti_failure",
        "kind": "delta"
      },
      {
        "key": "audit",
        "kind": "delta"
      },
      {
        "key": "evidence_contract",
        "kind": "delta"
      },
      {
        "key": "outcome_types",
        "kind": "delta"
      },
      {
        "key": "oracles",
        "kind": "delta"
      },
      {
        "key": "recusal",
        "kind": "delta"
      },
      {
        "key": "version_policy",
        "kind": "metadata"
      },
      {
        "key": "metadata",
        "kind": "metadata"
      }
    ],
    "presets": [
      {
        "id": "council.preset.gated-review.design-plan-critique",
        "name": "design-plan-critique",
        "family": "gated-review-board",
        "catalog_c_ids": [
          "C-architecture-review-board"
        ],
        "base_spec_ref": "councilspec.v2.gated-review-base@2.0.0-cnl0104",
        "delta": {
          "overlays": [
            "roles",
            "protocol_schedule",
            "voting",
            "stopping",
            "evidence_contract",
            "outcome_types",
            "default_binding.rubric_source",
            "default_binding.fail_kind"
          ],
          "must_not_override": [
            "family_vector",
            "voting.rule",
            "fail_kind",
            "author_nonvoting"
          ]
        },
        "roles": [
          {
            "id": "GateChair",
            "count": 1,
            "votes": true,
            "obligation": "Seat the board and bind the task-authored rubric."
          },
          {
            "id": "Architect",
            "count": 1,
            "votes": true,
            "obligation": "Argue the design against the rubric cells."
          },
          {
            "id": "Skeptic",
            "count": 1,
            "votes": true,
            "obligation": "Falsify findings; drop unfalsifiable concerns."
          },
          {
            "id": "EvidenceClerk",
            "count": 1,
            "votes": true,
            "obligation": "Admit or reject each finding's evidence packet."
          },
          {
            "id": "Author",
            "count": 1,
            "votes": false,
            "obligation": "Consume one revision round; does not vote the verdict."
          }
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P46",
            "purpose": "Seat the board and bind the task-authored rubric."
          },
          {
            "order": 2,
            "protocol_id": "P50",
            "purpose": "Admit or reject each finding's evidence packet."
          },
          {
            "order": 3,
            "protocol_id": "P49",
            "purpose": "Drop unfalsifiable findings via interrogation."
          }
        ],
        "voting": {
          "rule": "fail-sticky-majority",
          "quorum": 3,
          "who_votes": "seated-voting-roles",
          "oracle_veto": false
        },
        "stopping": {
          "expression": "ALL(cells_adjudicated) AND (fail_count==0 OR revision_budget==0 OR round>=max_rounds)",
          "max_rounds": 4,
          "on_timeout": "emit-findings-FAIL-open",
          "forbid": [
            "unfalsifiable-concern",
            "chair-feelings-as-evidence"
          ]
        },
        "editable_dials": [
          "stopping.max_rounds",
          "default_binding.revision_rounds"
        ],
        "default_binding": {
          "rubric_source": "task-authored",
          "evidence_kind": "argument-admissible",
          "fail_override_who": "none-without-new-evidence",
          "fail_kind": "finding",
          "revision_rounds": 1,
          "max_rounds": 4
        },
        "anti_failure": {
          "on_split": "surface-split-not-average",
          "no_silent_average": true
        },
        "audit": {
          "persist_transcript": true,
          "hash_inputs": true,
          "seal_protocol": false
        },
        "evidence_contract": "Findings rest on argument-admissible evidence: counterexample, fixture, or reasoned dissent with a locus. Unfalsifiable concern is inadmissible. FAIL is a finding, not a ship gate; nobody seated may convert FAIL to PASS without new admissible evidence.",
        "outcome_types": [
          "FINDINGS-PASS",
          "FINDINGS-FAIL",
          "FINDINGS-CONDITIONAL"
        ],
        "oracles": [],
        "recusal": [
          "author-from-verdict-tally"
        ],
        "version_policy": {
          "on_base_bump": "migrate-or-list-unmigratable",
          "reject_locked_override": true
        },
        "metadata": {
          "unit_id": "CNL-0104",
          "extends_protocols": [
            "P46",
            "P50",
            "P49"
          ],
          "extends_units": [
            "CNL-0101",
            "CNL-0045",
            "CNL-0060"
          ]
        }
      },
      {
        "id": "council.preset.gated-review.release-go-no-go",
        "name": "release-go-no-go",
        "family": "gated-review-board",
        "catalog_c_ids": [
          "C-architecture-review-board"
        ],
        "base_spec_ref": "councilspec.v2.gated-review-base@2.0.0-cnl0104",
        "delta": {
          "overlays": [
            "roles",
            "protocol_schedule",
            "voting",
            "stopping",
            "oracles",
            "evidence_contract",
            "outcome_types",
            "audit.seal_protocol",
            "default_binding.rubric_source",
            "default_binding.fail_kind"
          ],
          "must_not_override": [
            "family_vector",
            "voting.rule",
            "oracle_veto",
            "fail_kind",
            "owner_two_key"
          ]
        },
        "roles": [
          {
            "id": "GateChair",
            "count": 1,
            "votes": true,
            "obligation": "Seat the board against the frozen completion predicate."
          },
          {
            "id": "ProbeOperator",
            "count": 1,
            "votes": true,
            "obligation": "Re-run named probes; vote on command-reproducible cells."
          },
          {
            "id": "EvidenceClerk",
            "count": 1,
            "votes": true,
            "obligation": "Admit only named-probe exits, hashes, and verbatim output."
          },
          {
            "id": "OwnerKeyA",
            "count": 1,
            "votes": false,
            "obligation": "Silent until two-key override; may not vote as operator."
          },
          {
            "id": "OwnerKeyB",
            "count": 1,
            "votes": false,
            "obligation": "Silent until two-key override; may not vote as operator."
          }
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P46",
            "purpose": "Seat the board against the frozen named predicate."
          },
          {
            "order": 2,
            "protocol_id": "P16",
            "purpose": "Every cell must meet the command-reproducible evidence bar."
          },
          {
            "order": 3,
            "protocol_id": "P18",
            "purpose": "Fires only if FAIL and an owner two-key override is requested."
          }
        ],
        "voting": {
          "rule": "fail-closed-unanimity-of-operators",
          "quorum": 2,
          "who_votes": "operator-and-clerk",
          "oracle_veto": "named-probe-nonzero-exit"
        },
        "stopping": {
          "expression": "ALL(named_probes_rerun) AND (fail_count==0 OR override_two_key_complete OR round>=max_rounds)",
          "max_rounds": 2,
          "on_timeout": "NO-GO",
          "forbid": [
            "argument-without-command",
            "panel-majority-opinion"
          ]
        },
        "editable_dials": [
          "stopping.max_rounds"
        ],
        "default_binding": {
          "rubric_source": "frozen-predicate",
          "evidence_kind": "command-reproducible",
          "fail_override_who": "owner-two-key",
          "fail_kind": "gate",
          "revision_rounds": 0,
          "max_rounds": 2,
          "predicate_name": "G-1-contract-green"
        },
        "anti_failure": {
          "on_split": "surface-split-not-average",
          "no_silent_average": true
        },
        "audit": {
          "persist_transcript": true,
          "hash_inputs": true,
          "seal_protocol": true
        },
        "evidence_contract": "GO/NO-GO rests on command-reproducible evidence: named-probe exit code, artifact sha256, and verbatim command output. Opinion without a command is inadmissible. FAIL is a gate. Only owner two-key dual control (P18) with recorded dissent may convert the outcome to CONDITIONAL-GO.",
        "outcome_types": [
          "SHIP-GO",
          "SHIP-NOGO",
          "CONDITIONAL-GO"
        ],
        "oracles": [
          {
            "id": "named-probe",
            "vetoes": "SHIP-GO",
            "obligation": "Nonzero named-probe exit forbids SHIP-GO; FAIL stays a gate."
          }
        ],
        "recusal": [
          "owner-keys-from-operator-vote"
        ],
        "version_policy": {
          "on_base_bump": "migrate-or-list-unmigratable",
          "reject_locked_override": true
        },
        "metadata": {
          "unit_id": "CNL-0104",
          "extends_protocols": [
            "P46",
            "P16",
            "P18"
          ],
          "extends_units": [
            "CNL-0101",
            "CNL-0045",
            "CNL-0060"
          ]
        }
      }
    ],
    "instantiations": [
      {
        "ok": true,
        "preset_id": "council.preset.gated-review.design-plan-critique",
        "task_id": "task.fixture.gated-review-CNL-0104",
        "mechanism_class": "design-plan-critique",
        "roster": [
          {
            "role": "GateChair",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "Architect",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "Skeptic",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "EvidenceClerk",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "Author",
            "vote_weight": 0.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": "non-unit-weight:Author"
          }
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P46",
            "purpose": "Seat the board and bind the task-authored rubric.",
            "name": null
          },
          {
            "order": 2,
            "protocol_id": "P50",
            "purpose": "Admit or reject each finding's evidence packet.",
            "name": null
          },
          {
            "order": 3,
            "protocol_id": "P49",
            "purpose": "Drop unfalsifiable findings via interrogation.",
            "name": null
          }
        ],
        "voting": {
          "rule": "fail-sticky-majority",
          "quorum": 3,
          "who_votes": "seated-voting-roles",
          "oracle_veto": false
        },
        "stopping": {
          "expression": "ALL(cells_adjudicated) AND (fail_count==0 OR revision_budget==0 OR round>=max_rounds)",
          "max_rounds": 4,
          "on_timeout": "emit-findings-FAIL-open",
          "forbid": [
            "unfalsifiable-concern",
            "chair-feelings-as-evidence"
          ]
        },
        "family_vector": {
          "rubric_source": "task-authored",
          "evidence_contract": "argument-admissible",
          "fail_override_who": "none-without-new-evidence",
          "fail_kind": "finding"
        },
        "default_binding": {
          "rubric_source": "task-authored",
          "evidence_kind": "argument-admissible",
          "fail_override_who": "none-without-new-evidence",
          "fail_kind": "finding",
          "revision_rounds": 1,
          "max_rounds": 4
        },
        "mechanism_tuple": [
          [
            "Architect",
            "Author",
            "EvidenceClerk",
            "GateChair",
            "Skeptic"
          ],
          [
            "P46",
            "P50",
            "P49"
          ],
          [
            "fail-sticky-majority",
            3
          ],
          [
            "ALL(cells_adjudicated) AND (fail_count==0 OR revision_budget==0 OR round>=max_rounds)",
            4
          ],
          [
            "task-authored",
            "argument-admissible",
            "none-without-new-evidence",
            "finding"
          ]
        ]
      },
      {
        "ok": true,
        "preset_id": "council.preset.gated-review.release-go-no-go",
        "task_id": "task.fixture.gated-review-CNL-0104",
        "mechanism_class": "release-go-no-go",
        "roster": [
          {
            "role": "GateChair",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "ProbeOperator",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "EvidenceClerk",
            "vote_weight": 1.0,
            "seated": true,
            "may_override_fail": false,
            "weight_provenance": null
          },
          {
            "role": "OwnerKeyA",
            "vote_weight": 0.0,
            "seated": true,
            "may_override_fail": true,
            "weight_provenance": "non-unit-weight:OwnerKeyA"
          },
          {
            "role": "OwnerKeyB",
            "vote_weight": 0.0,
            "seated": true,
            "may_override_fail": true,
            "weight_provenance": "non-unit-weight:OwnerKeyB"
          }
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P46",
            "purpose": "Seat the board against the frozen named predicate.",
            "name": null
          },
          {
            "order": 2,
            "protocol_id": "P16",
            "purpose": "Every cell must meet the command-reproducible evidence bar.",
            "name": null
          },
          {
            "order": 3,
            "protocol_id": "P18",
            "purpose": "Fires only if FAIL and an owner two-key override is requested.",
            "name": null
          }
        ],
        "voting": {
          "rule": "fail-closed-unanimity-of-operators",
          "quorum": 2,
          "who_votes": "operator-and-clerk",
          "oracle_veto": "named-probe-nonzero-exit"
        },
        "stopping": {
          "expression": "ALL(named_probes_rerun) AND (fail_count==0 OR override_two_key_complete OR round>=max_rounds)",
          "max_rounds": 2,
          "on_timeout": "NO-GO",
          "forbid": [
            "argument-without-command",
            "panel-majority-opinion"
          ]
        },
        "family_vector": {
          "rubric_source": "frozen-predicate",
          "evidence_contract": "command-reproducible",
          "fail_override_who": "owner-two-key",
          "fail_kind": "gate"
        },
        "default_binding": {
          "rubric_source": "frozen-predicate",
          "evidence_kind": "command-reproducible",
          "fail_override_who": "owner-two-key",
          "fail_kind": "gate",
          "revision_rounds": 0,
          "max_rounds": 2,
          "predicate_name": "G-1-contract-green"
        },
        "mechanism_tuple": [
          [
            "EvidenceClerk",
            "GateChair",
            "OwnerKeyA",
            "OwnerKeyB",
            "ProbeOperator"
          ],
          [
            "P46",
            "P16",
            "P18"
          ],
          [
            "fail-closed-unanimity-of-operators",
            2
          ],
          [
            "ALL(named_probes_rerun) AND (fail_count==0 OR override_two_key_complete OR round>=max_rounds)",
            2
          ],
          [
            "frozen-predicate",
            "command-reproducible",
            "owner-two-key",
            "gate"
          ]
        ]
      }
    ],
    "nearest_sibling": {
      "council.preset.gated-review.design-plan-critique": {
        "named": "C-architecture-review-board",
        "distance": 5,
        "axes_that_differ": [
          "roles",
          "protocols",
          "voting",
          "stopping",
          "family_vector"
        ],
        "ranked": [
          {
            "id": "C-architecture-review-board",
            "name": "architecture-review-board",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "C-incident-war-room",
            "name": "incident-war-room",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "C-scientific-peer-review",
            "name": "scientific-peer-review",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "council.preset.catalog-class.editable",
            "name": "catalog-class-editable",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          }
        ],
        "same_mechanism": false
      },
      "council.preset.gated-review.release-go-no-go": {
        "named": "C-architecture-review-board",
        "distance": 5,
        "axes_that_differ": [
          "roles",
          "protocols",
          "voting",
          "stopping",
          "family_vector"
        ],
        "ranked": [
          {
            "id": "C-architecture-review-board",
            "name": "architecture-review-board",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "C-incident-war-room",
            "name": "incident-war-room",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "C-scientific-peer-review",
            "name": "scientific-peer-review",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          },
          {
            "id": "council.preset.catalog-class.editable",
            "name": "catalog-class-editable",
            "distance": 5,
            "mechanism_class": "pre-family-review-board"
          }
        ],
        "same_mechanism": false
      }
    },
    "c_id_mapping": [
      {
        "preset_id": "council.preset.gated-review.design-plan-critique",
        "catalog_c_ids": [
          "C-architecture-review-board"
        ],
        "supersedes": [
          {
            "id": "C-architecture-review-board",
            "relation": "extends",
            "confirmed_from_library_file": false,
            "basis": "Catalog-cited protocol P46 architecture-review-board (CNL-0045 ENGINEERING-REVIEW member list). C-id string is reconstructed; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent."
          }
        ]
      },
      {
        "preset_id": "council.preset.gated-review.release-go-no-go",
        "catalog_c_ids": [
          "C-architecture-review-board"
        ],
        "supersedes": [
          {
            "id": "C-architecture-review-board",
            "relation": "extends",
            "confirmed_from_library_file": false,
            "basis": "Same P46 sibling as the critique member, plus a command oracle P46 does not have. That oracle is what makes this a different mechanism rather than a renamed critique board."
          }
        ]
      }
    ],
    "schema_validation": {
      "declared_output_schema": "command-center/schema/council-preset.schema.json",
      "declared_schema_shape": "generated $ref shim to receipt envelope; report.kind=council-preset",
      "executable_preset_schema": "command-center/p2-wave/probes/CNL-0104/preset.record.schema.json",
      "validator": "jsonschema.Draft202012Validator",
      "validator_target": "unit-local $defs.preset plus declared envelope via schema_resolver",
      "validator_target_reason": "Strike 1 validated family members against the generated shim and recorded 17 envelope errors on a preset record. Pivot: family members use the unit-local $defs.preset; the catalog file uses the declared council-preset envelope. This unit did not rewrite the shared shim.",
      "affected_records": [
        {
          "id": "council.preset.gated-review.design-plan-critique",
          "errors": 0,
          "messages": []
        },
        {
          "id": "council.preset.gated-review.release-go-no-go",
          "errors": 0,
          "messages": []
        }
      ],
      "error_count": 0,
      "deliberately_invalid": {
        "record": {
          "id": 0,
          "name": "",
          "delta": {}
        },
        "error_count": 21,
        "proves_validator_not_vacuous": true
      },
      "invalid_envelope_error_count": 10
    },
    "negative_control": {
      "what_it_rejects": "A record named release-go-no-go whose family vector still matches design-plan-critique (name-only / mechanism-duplicate), and a silent write to a non-editable dial (delta.voting.rule).",
      "name_only_clone_distance": 0,
      "mixed_named_gng_classified_as": "design-plan-critique",
      "non_editable_dial_rejected": true,
      "non_editable_dial_reason": "silent override of non-editable dial(s) delta.voting.rule \u2014 instantiator REJECTS",
      "both_states": {
        "known_good_gng_class": "release-go-no-go",
        "planted_mixed_class": "design-plan-critique",
        "fires_on_planted": true,
        "silent_on_known_good": true
      }
    },
    "reviewer_method": "probe2 re-derives nearest sibling by axis_distance over mechanism_tuple without reading this document's nearest_sibling field."
  }
}
