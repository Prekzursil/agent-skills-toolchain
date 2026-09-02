{
  "unit_id": "CNL-0113",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0113",
  "kind": "council-preset-family",
  "question": "Both juries decide on presented evidence - what does the benchmark jury need in addition, given that a benchmark result is a number an interested party produced and can game?",
  "answer": "Both juries decide on presented evidence. The evidence-adjudication jury (C-J01) treats admitted exhibits as the facts under a standard of proof, with a clerk who is not the presenter controlling admission and jurors who did not argue (CNL-0034 / CNL-0040: P14, P15, P17, P50). That is enough when exhibits are documents or testimony. A benchmark result is not that kind of exhibit: it is a number an interested party produced, movable by metric choice, split leakage, hardware, seeds, and undisclosed overlap. Admitting the number as a fact makes the presenter the real decision-maker (the CNL-0034 presenter-as-decider failure, specialised to scores). The benchmark-results jury (C-J02) therefore needs, in addition: (1) classify the number as CLAIM not FACT; (2) a protocol-registrar who seals metric, splits, hardware class, and seeds BEFORE any result is admitted, with P18 two-key control so the producer cannot reseal alone; (3) a replicator role whose independent remeasurement is an oracle; (4) a metric-adversary / canary whose cheaper policy that beats the metric without the claimed capability yields GAMEABLE; (5) producer recusal from the voting jury; (6) oracle veto in the voting rule so majority cannot vote CONFIRMED while replication is pending or the canary is gameable (CNL-0106 oracle-override pattern, specialised to remeasurement rather than a unit test); (7) outcome types CONFIRMED-UNDER-PROTOCOL | GAMEABLE | UNREPLICATED | PROTOCOL-VIOLATION so a good-looking number cannot be laundered as a verdict. Nearest sibling is C-J01 in the same family: the differential is the extra roles, extra protocol steps, oracle-veto voting, and stopping that forbids CONFIRMED without replication. A clone that only renames C-J01 is distance 0 and is rejected as a mechanism-duplicate. Catalog C-ids C-J01/C-J02 are family-local; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this tree (same finding as ARC-0003). SUCCESS:CNL-0113",
  "library_status": {
    "original_library_on_tree": false,
    "original_library_path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "reconstruction": "P14-P19 named in catalog CNL-0040; sibling presets reconstructed from CNL-0103-CNL-0116 family titles. Original 72-record library bytes are not on this tree.",
    "protocol_ids_from_catalog": [
      "P14",
      "P15",
      "P17",
      "P18",
      "P50"
    ]
  },
  "preset_type": {
    "kind": "typed-delta-over-councilspec",
    "keys": [
      "id",
      "name",
      "family",
      "catalog_c_ids",
      "base_spec_ref",
      "delta",
      "roles",
      "protocol_schedule",
      "voting",
      "stopping",
      "editable_dials",
      "default_binding",
      "anti_failure",
      "audit",
      "evidence_contract",
      "outcome_types",
      "oracles",
      "recusal",
      "version_policy",
      "metadata"
    ],
    "on_base_version_bump": "migrate-or-list-unmigratable; never silent-fork",
    "locked_dial_override": "REJECT"
  },
  "schema_binding": {
    "path": "command-center/schema/council-preset.schema.json",
    "exists": true,
    "has_defs_preset": false,
    "generated_by": "platform/lib/_gen_schema_substrate.py",
    "physical_definition": "platform/schema/artifact-class-profiles.schema.json#/$defs/council-preset",
    "executable_schema": "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json",
    "rewrote_shared_schema": false
  },
  "presets": [
    {
      "id": "C-J01",
      "name": "evidence-adjudication-jury",
      "family": "jury",
      "catalog_c_ids": [
        "C-J01"
      ],
      "base_spec_ref": "councilspec.v2.base@unversioned-on-this-tree",
      "delta": {
        "overlays": [
          "roles",
          "protocol_schedule",
          "voting",
          "stopping",
          "evidence_contract",
          "outcome_types"
        ],
        "must_not_override": [
          "presenter_cannot_vote",
          "clerk_cannot_vote"
        ]
      },
      "roles": [
        {
          "id": "clerk",
          "count": 1,
          "votes": false,
          "obligation": "Admit or exclude exhibits; never vote on the merits."
        },
        {
          "id": "presenter",
          "count": 1,
          "votes": false,
          "obligation": "Offer exhibits; does not decide."
        },
        {
          "id": "judge",
          "count": 1,
          "votes": false,
          "obligation": "Rule procedure and hung; does not vote on merits."
        },
        {
          "id": "juror",
          "count": 5,
          "votes": true,
          "obligation": "Decide admitted claims; must not have argued the case."
        }
      ],
      "protocol_schedule": [
        {
          "order": 1,
          "protocol_id": "P50",
          "purpose": "Clerk-led intake and admission of exhibits."
        },
        {
          "order": 2,
          "protocol_id": "P15",
          "purpose": "Claim-by-claim adjudication against the admitted packet."
        },
        {
          "order": 3,
          "protocol_id": "P17",
          "purpose": "Jury deliberation with hung permitted."
        }
      ],
      "voting": {
        "rule": "supermajority-jurors-hung-ok",
        "quorum": 4,
        "who_votes": "juror",
        "oracle_veto": false
      },
      "stopping": {
        "expression": "hung-or-verdict OR max_rounds",
        "max_rounds": 3,
        "on_timeout": "HUNG",
        "forbid": [
          "presenter-vote",
          "clerk-vote"
        ]
      },
      "editable_dials": [
        "juror.count",
        "voting.quorum",
        "stopping.max_rounds"
      ],
      "default_binding": {
        "juror.count": 5,
        "voting.quorum": 4,
        "stopping.max_rounds": 3,
        "standard_of_proof": "preponderance"
      },
      "anti_failure": {
        "on_split": "surface-hung-not-average",
        "no_silent_average": true
      },
      "audit": {
        "persist_transcript": true,
        "hash_inputs": true,
        "seal_protocol": false
      },
      "evidence_contract": "Admitted documents and testimony are the facts under the stated standard of proof. A self-reported number may be admitted as an exhibit; this jury has no replication oracle, so a number from an interested party can move the verdict.",
      "outcome_types": [
        "CLAIM-UPHELD",
        "CLAIM-REJECTED",
        "INSUFFICIENT",
        "HUNG"
      ],
      "oracles": [],
      "recusal": [
        "presenter-from-jury",
        "clerk-from-jury"
      ],
      "version_policy": {
        "on_base_bump": "migrate-or-list-unmigratable",
        "reject_locked_override": true
      },
      "metadata": {
        "unit_id": "CNL-0113",
        "extends_protocols": [
          "P14",
          "P15",
          "P17",
          "P50"
        ],
        "extends_units": [
          "CNL-0034",
          "CNL-0040",
          "CNL-0101"
        ]
      }
    },
    {
      "id": "C-J02",
      "name": "benchmark-results-jury",
      "family": "jury",
      "catalog_c_ids": [
        "C-J02"
      ],
      "base_spec_ref": "councilspec.v2.base@unversioned-on-this-tree",
      "delta": {
        "overlays": [
          "roles",
          "protocol_schedule",
          "voting",
          "stopping",
          "oracles",
          "recusal",
          "evidence_contract",
          "outcome_types",
          "audit.seal_protocol"
        ],
        "must_not_override": [
          "producer_recusal",
          "oracle_veto",
          "seal_before_admit",
          "replicator_role",
          "metric_adversary_role"
        ]
      },
      "roles": [
        {
          "id": "clerk",
          "count": 1,
          "votes": false,
          "obligation": "Classify the number as CLAIM not FACT; never vote."
        },
        {
          "id": "claim-presenter",
          "count": 1,
          "votes": false,
          "obligation": "Present the claimed score; recused from the jury tally."
        },
        {
          "id": "protocol-registrar",
          "count": 1,
          "votes": false,
          "obligation": "Seal metric, splits, hardware class, and seeds BEFORE any result is admitted."
        },
        {
          "id": "replicator",
          "count": 1,
          "votes": false,
          "obligation": "Independent remeasurement under the sealed protocol; oracle, not juror."
        },
        {
          "id": "metric-adversary",
          "count": 1,
          "votes": false,
          "obligation": "Exhibit a cheaper policy that beats the metric without the claimed capability."
        },
        {
          "id": "judge",
          "count": 1,
          "votes": false,
          "obligation": "Rule procedure; cannot override an oracle veto."
        },
        {
          "id": "juror",
          "count": 5,
          "votes": true,
          "obligation": "Decide among remaining outcomes after oracles; must not have produced the number."
        }
      ],
      "protocol_schedule": [
        {
          "order": 1,
          "protocol_id": "seal-protocol-before-result",
          "purpose": "Registrar seals metric/splits/hardware/seeds before any score is in evidence."
        },
        {
          "order": 2,
          "protocol_id": "P18",
          "purpose": "Two-key dual control on the seal so the producer cannot reseal alone."
        },
        {
          "order": 3,
          "protocol_id": "P50",
          "purpose": "Clerk-led intake: the vendor number is a claim, not a fact."
        },
        {
          "order": 4,
          "protocol_id": "independent-remeasure",
          "purpose": "Replicator re-runs the sealed protocol on a sealed fixture."
        },
        {
          "order": 5,
          "protocol_id": "gameability-canary",
          "purpose": "Metric-adversary runs a known-cheap policy / leakage canary."
        },
        {
          "order": 6,
          "protocol_id": "P15",
          "purpose": "Claim-by-claim on (sealed protocol, replication delta, canary)."
        },
        {
          "order": 7,
          "protocol_id": "P17",
          "purpose": "Deliberation with hung permitted; CONFIRMED forbidden under veto."
        }
      ],
      "voting": {
        "rule": "supermajority-jurors-with-oracle-veto",
        "quorum": 4,
        "who_votes": "juror",
        "oracle_veto": "replicator-or-canary"
      },
      "stopping": {
        "expression": "(oracles-resolved AND (hung-or-verdict)) OR max_rounds",
        "max_rounds": 4,
        "on_timeout": "INCONCLUSIVE",
        "forbid": [
          "CONFIRMED-while-replication-pending",
          "CONFIRMED-if-canary-gameable",
          "CONFIRMED-if-protocol-unsealed",
          "producer-as-juror"
        ]
      },
      "editable_dials": [
        "juror.count",
        "voting.quorum",
        "stopping.max_rounds",
        "replication.tolerance"
      ],
      "default_binding": {
        "juror.count": 5,
        "voting.quorum": 4,
        "stopping.max_rounds": 4,
        "replication.tolerance": 1.5
      },
      "anti_failure": {
        "on_split": "surface-hung-not-average",
        "no_silent_average": true
      },
      "audit": {
        "persist_transcript": true,
        "hash_inputs": true,
        "seal_protocol": true
      },
      "evidence_contract": "A benchmark result is a number an interested party produced. It is admitted only as a CLAIM, and only after the protocol is sealed. Independent remeasurement and a gameability canary are required before CONFIRMED-UNDER-PROTOCOL. Majority opinion cannot override a failed replication or a passing canary. Producer recusal is structural.",
      "outcome_types": [
        "CONFIRMED-UNDER-PROTOCOL",
        "GAMEABLE",
        "UNREPLICATED",
        "PROTOCOL-VIOLATION",
        "CLAIM-REJECTED",
        "INCONCLUSIVE",
        "HUNG"
      ],
      "oracles": [
        {
          "id": "replicator",
          "vetoes": "CONFIRMED-UNDER-PROTOCOL",
          "obligation": "Must re-run the sealed protocol; pending or mismatch blocks CONFIRMED."
        },
        {
          "id": "metric-adversary",
          "vetoes": "CONFIRMED-UNDER-PROTOCOL",
          "obligation": "A cheaper policy that beats the metric without the claimed capability yields GAMEABLE."
        }
      ],
      "recusal": [
        "producer-from-jury",
        "claim-presenter-from-jury",
        "clerk-from-jury",
        "replicator-from-jury",
        "registrar-from-jury",
        "metric-adversary-from-jury"
      ],
      "version_policy": {
        "on_base_bump": "migrate-or-list-unmigratable",
        "reject_locked_override": true
      },
      "metadata": {
        "unit_id": "CNL-0113",
        "extends_protocols": [
          "P15",
          "P17",
          "P18",
          "P50",
          "seal-protocol-before-result",
          "independent-remeasure",
          "gameability-canary"
        ],
        "extends_units": [
          "CNL-0034",
          "CNL-0040",
          "CNL-0101",
          "CNL-0106"
        ]
      }
    }
  ],
  "nearest_sibling": {
    "subject_id": "C-J02",
    "sibling_id": "C-J01",
    "sibling_name": "evidence-adjudication-jury",
    "distance": 11,
    "differing_axes": [
      "roles",
      "protocol_schedule",
      "voting",
      "stopping"
    ],
    "duplicate_if_name_only": true
  },
  "instantiation": {
    "fixture_task_id": "task.vendor-mmlu-claim",
    "profiles": [
      {
        "preset_id": "C-J01",
        "roster": [
          "clerk",
          "presenter",
          "judge",
          "juror-1",
          "juror-2",
          "juror-3",
          "juror-4",
          "juror-5"
        ],
        "protocol_schedule": [
          "P50",
          "P15",
          "P17"
        ],
        "voting_method": "supermajority-jurors-hung-ok|q=4|who=juror|veto=False",
        "stopping_expression": "hung-or-verdict OR max_rounds|max=3|timeout=HUNG|forbid=presenter-vote,clerk-vote"
      },
      {
        "preset_id": "C-J02",
        "roster": [
          "clerk",
          "claim-presenter",
          "protocol-registrar",
          "replicator",
          "metric-adversary",
          "judge",
          "juror-1",
          "juror-2",
          "juror-3",
          "juror-4",
          "juror-5"
        ],
        "protocol_schedule": [
          "seal-protocol-before-result",
          "P18",
          "P50",
          "independent-remeasure",
          "gameability-canary",
          "P15",
          "P17"
        ],
        "voting_method": "supermajority-jurors-with-oracle-veto|q=4|who=juror|veto=replicator-or-canary",
        "stopping_expression": "(oracles-resolved AND (hung-or-verdict)) OR max_rounds|max=4|timeout=INCONCLUSIVE|forbid=CONFIRMED-while-replication-pending,CONFIRMED-if-canary-gameable,CONFIRMED-if-protocol-unsealed,producer-as-juror"
      }
    ]
  },
  "schema_validation": {
    "validator": "jsonschema.Draft202012Validator",
    "working_schema": "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json",
    "catalog_schema": "command-center/schema/council-preset.schema.json",
    "validator_target": "$defs.preset",
    "valid_error_count": 0,
    "invalid_record_error_count": 18,
    "invalid_record_id": "C-J99"
  },
  "negative_control": {
    "check": "name-only-clone-distance-zero-and-locked-dial-reject",
    "reject_state": "preset copied from C-J01 with only id/name changed to look like C-J02",
    "on_reject_state": "FIRE distance=0 MECHANISM-DUPLICATE; do not register",
    "on_accept_state": "SILENT on live C-J02 (distance>=1 vs C-J01; oracles present)",
    "verbatim": "The check FIRES when a preset shares C-J01's roles, protocol_schedule, voting and stopping and differs only in id/name (distance 0). It is SILENT on C-J02, which adds registrar/replicator/metric-adversary, seal-before-admit, oracle veto, and producer recusal. Overlay of locked dial producer_recusal is REJECT. SUCCESS:CNL-0113"
  },
  "reviewer": {
    "reviewer_id": "CNL-0113-probe2-sibling-schema",
    "independent": true,
    "verdict": "PASS",
    "method": "Re-instantiate both presets against the fixture, recompute the 4-axis profile and nearest-sibling distance, re-run Draft202012Validator on live records plus a deliberately invalid record, and re-run the name-only clone control."
  },
  "tests": [
    {
      "id": "instantiate-fixture",
      "result": "PASS",
      "detail": "C-J01 roster=['clerk', 'presenter', 'judge', 'juror-1', 'juror-2', 'juror-3', 'juror-4', 'juror-5'] schedule=['P50', 'P15', 'P17'] vote=supermajority-jurors-hung-ok|q=4|who=juror|veto=False stop=hung-or-verdict OR max_rounds|max=3|timeout=HUNG|forbid=presenter-vote,clerk-vote; C-J02 roster=['clerk', 'claim-presenter', 'protocol-registrar', 'replicator', 'metric-adversary', 'judge', 'juror-1', 'juror-2', 'juror-3', 'juror-4', 'juror-5'] schedule=['seal-protocol-before-result', 'P18', 'P50', 'independent-remeasure', 'gameability-canary', 'P15', 'P17']"
    },
    {
      "id": "nearest-sibling-differential",
      "result": "PASS",
      "detail": "nearest sibling of C-J02 is C-J01 (evidence-adjudication-jury) distance=11 axes=['roles', 'protocol_schedule', 'voting', 'stopping']"
    },
    {
      "id": "draft202012-validator",
      "result": "PASS",
      "detail": "valid_error_count=0 invalid_record_error_count=18 invalid_record_id=C-J99"
    },
    {
      "id": "negative-control",
      "result": "PASS",
      "detail": "name-only clone distance=0; C-J01 presenter-moved=True; C-J02 presenter-moved=False; locked-dial-fired=True"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0113-jury-family-evidence-adjudication-and-benchmark-results-ju.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0113/council-preset.schema.json",
      "exists": true,
      "role": "working-schema"
    },
    {
      "path": "command-center/schema/council-preset.schema.json",
      "exists": true,
      "role": "catalog-declared-schema-shim"
    }
  ]
}
