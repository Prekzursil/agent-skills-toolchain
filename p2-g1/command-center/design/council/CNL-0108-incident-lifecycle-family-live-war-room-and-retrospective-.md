{
  "unit_id": "CNL-0108",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0108",
  "title": "Incident lifecycle family: live war room and retrospective postmortem",
  "question": "The same root-cause reasoning runs under two very different clocks - what changes between the live war-room preset (act now, evidence later) and the retrospective root cause / postmortem one (evidence first, no action pressure), and which of the two may skip the minimum deliberation floor?",
  "answer": {
    "what_changes": "The two presets share a causal spine (root-cause reasoning) and diverge on clock, evidence order, roster, bound protocols, voting, stopping, and floor policy. Live binds P47 then P51, seats a commander who may act with dissent recorded, stops on containment, and treats unevidenced causes as deferred. Retrospective binds P44+P38+P40+P42, seats an evidence clerk who can veto an unevidenced close, and stops only when the floor and the causal record are both met.",
    "who_may_skip_minimum_deliberation_floor": "Only the live war-room preset may skip the minimum deliberation floor, and only for containment actions. The retrospective preset must hold the floor; a satisfied stop under an unmet floor is blocked and audited.",
    "may_skip": [
      "C-IL-LIVE"
    ],
    "must_hold_floor": [
      "C-IL-RETRO"
    ],
    "skip_scope": "containment-action-only",
    "cnl_0077_relation": "CNL-0077 floors outrank any stopping expression. Live is the typed exception: a FLOOR-SKIP audit line is allowed only when action=containment. A causal verdict cannot ride the skip. Retrospective has no exception. Ceiling max_rounds prevents a hang."
  },
  "preset_type": {
    "key_count": 20,
    "keys": [
      "id",
      "name",
      "family",
      "artifact_type",
      "base_spec_ref",
      "base_spec_version",
      "default_binding",
      "protocol_schedule",
      "roster",
      "voting",
      "consensus",
      "stopping",
      "anti_failure",
      "audit",
      "editable_dials",
      "outcome_type",
      "evidence_contract",
      "floor_policy",
      "clock",
      "supersedes"
    ],
    "classification": {
      "metadata": [
        "id",
        "name",
        "family",
        "artifact_type",
        "audit",
        "supersedes"
      ],
      "base": [
        "base_spec_ref",
        "base_spec_version"
      ],
      "delta": [
        "default_binding",
        "protocol_schedule",
        "roster",
        "voting",
        "consensus",
        "stopping",
        "anti_failure",
        "editable_dials",
        "outcome_type",
        "evidence_contract",
        "floor_policy",
        "clock"
      ]
    },
    "on_base_version_bump": "Each preset is a delta over base_spec_ref@base_spec_version. A base bump must migrate every preset or list the ones it cannot; this unit does not migrate the absent 72-record library. The two family deltas here rebind against 2.0.0."
  },
  "library": {
    "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "on_this_worktree": false,
    "paths_checked": {
      "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
      "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false
    },
    "sibling_source": "command-center/p2-wave/probes/CNL-0108/fixtures/reconstructed_catalog.json",
    "reconstruction": "Original library absent. Siblings reconstructed from WORK-UNIT-CATALOG.json named P-ids (CNL-0044 P44, CNL-0045 P47) and C-M01 (CNL-0002). Not a 72-preset disk count. C-IL-LIVE nearest sibling is C-ER47 (shared P47). C-IL-RETRO nearest sibling is C-ER-CRT (shared evidence-first + floor-hold); it still supersedes C-TC44/P44."
  },
  "presets": [
    {
      "id": "C-IL-LIVE",
      "name": "Live war-room (act now, evidence later)",
      "family": "incident-lifecycle",
      "artifact_type": "council-preset",
      "base_spec_ref": "CouncilSpec/v2",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "protocol_ids": [
          "P47",
          "P51"
        ]
      },
      "protocol_schedule": [
        {
          "order": 1,
          "protocol_id": "P47",
          "purpose": "Contain harm under a live operational clock"
        },
        {
          "order": 2,
          "protocol_id": "P51",
          "purpose": "Timeboxed spike only if containment needs a probe"
        }
      ],
      "roster": [
        {
          "id": "Incident-Commander",
          "obligation": "Issue a containment action within the live clock",
          "permission": "Override majority on containment only",
          "right": "Skip the deliberation floor for containment, never for cause"
        },
        {
          "id": "Mitigator",
          "obligation": "Apply the commanded mitigation and report blast radius",
          "permission": "Propose a narrower containment",
          "right": "Refuse a mitigation with no rollback"
        },
        {
          "id": "Scribe",
          "obligation": "Log every action and every deferred hypothesis",
          "permission": "Pause speech for a log line",
          "right": "Refuse an unlogged containment"
        },
        {
          "id": "Skeptic",
          "obligation": "Name the harm of acting on a wrong hypothesis",
          "permission": "Force a dissent line onto the transcript",
          "right": "Block a causal verdict while the floor is skipped"
        }
      ],
      "voting": {
        "method": "commander-decides-with-dissent-record",
        "quorum": 1
      },
      "consensus": {
        "reducer": "commander-action-plus-dissent",
        "local_completion_forbidden": true
      },
      "stopping": {
        "expr": {
          "op": "OR",
          "args": [
            {
              "var": "containment_declared",
              "eq": true
            },
            {
              "op": "AND",
              "args": [
                {
                  "var": "elapsed_minutes",
                  "gte": 30
                },
                {
                  "var": "mitigation_in_place",
                  "eq": true
                }
              ]
            }
          ]
        },
        "on_timeout": "contain-then-handoff-to-retrospective",
        "max_rounds": 3
      },
      "anti_failure": {
        "on_split": "commander-acts-dissent-recorded",
        "no_silent_average": true
      },
      "audit": {
        "persist_transcript": true,
        "hash_inputs": true
      },
      "editable_dials": [
        "stopping.max_rounds",
        "clock.containment_minutes"
      ],
      "outcome_type": "containment-action",
      "evidence_contract": {
        "order": "act-now-evidence-later",
        "unevidenced_cause": "deferred-to-retrospective"
      },
      "floor_policy": {
        "min_rounds": 2,
        "min_independent_briefs": 2,
        "min_evidence": 1,
        "may_skip_minimum_deliberation": true,
        "skip_scope": "containment-action-only",
        "ceiling_max_rounds": 3
      },
      "clock": {
        "kind": "live-operational",
        "action_pressure": true
      },
      "supersedes": [
        "C-ER47",
        "P47"
      ]
    },
    {
      "id": "C-IL-RETRO",
      "name": "Retrospective root-cause / postmortem (evidence first)",
      "family": "incident-lifecycle",
      "artifact_type": "council-preset",
      "base_spec_ref": "CouncilSpec/v2",
      "base_spec_version": "2.0.0",
      "default_binding": {
        "protocol_ids": [
          "P44",
          "P38",
          "P40",
          "P42"
        ]
      },
      "protocol_schedule": [
        {
          "order": 1,
          "protocol_id": "P44",
          "purpose": "Walk the 5-whys chain as the causal spine"
        },
        {
          "order": 2,
          "protocol_id": "P38",
          "purpose": "Score competing hypotheses instead of a single story"
        },
        {
          "order": 3,
          "protocol_id": "P40",
          "purpose": "Quality-of-information check on every cited source"
        },
        {
          "order": 4,
          "protocol_id": "P42",
          "purpose": "Map the surviving argument so a skipped premise is visible"
        }
      ],
      "roster": [
        {
          "id": "Facilitator",
          "obligation": "Hold the floor until min rounds, briefs and evidence exist",
          "permission": "Reorder protocols inside the schedule",
          "right": "Refuse any floor skip"
        },
        {
          "id": "Evidence-Clerk",
          "obligation": "Reject a cause that has no cited evidence",
          "permission": "Return a why-link for more sources",
          "right": "Veto an unevidenced close even under majority"
        },
        {
          "id": "Causal-Analyst",
          "obligation": "Draft each why-link with a cited source",
          "permission": "Add a competing hypothesis",
          "right": "Demand ACH scoring before close"
        },
        {
          "id": "Skeptic",
          "obligation": "Name the strongest alternative cause",
          "permission": "Challenge source quality",
          "right": "Attach a minority report"
        },
        {
          "id": "Domain-Owner",
          "obligation": "Confirm operational facts without deciding cause",
          "permission": "Correct a factual error",
          "right": "Refuse blame-as-cause language"
        }
      ],
      "voting": {
        "method": "evidence-adjudicated-majority",
        "quorum": 3
      },
      "consensus": {
        "reducer": "clerk-veto-then-majority",
        "local_completion_forbidden": true
      },
      "stopping": {
        "expr": {
          "op": "AND",
          "args": [
            {
              "var": "each_why_has_evidence",
              "eq": true
            },
            {
              "var": "competing_hypotheses_scored",
              "eq": true
            }
          ]
        },
        "on_timeout": "BLOCKED-incomplete-causal-record",
        "max_rounds": 16
      },
      "anti_failure": {
        "on_split": "minority-report-mandatory",
        "no_silent_average": true
      },
      "audit": {
        "persist_transcript": true,
        "hash_inputs": true
      },
      "editable_dials": [
        "floor_policy.min_rounds",
        "floor_policy.min_evidence",
        "stopping.max_rounds"
      ],
      "outcome_type": "evidenced-causal-record",
      "evidence_contract": {
        "order": "evidence-first",
        "unevidenced_cause": "rejected"
      },
      "floor_policy": {
        "min_rounds": 3,
        "min_independent_briefs": 3,
        "min_evidence": 3,
        "may_skip_minimum_deliberation": false,
        "skip_scope": "none",
        "ceiling_max_rounds": 16
      },
      "clock": {
        "kind": "retrospective-no-action-pressure",
        "action_pressure": false
      },
      "supersedes": [
        "C-TC44",
        "P44"
      ]
    }
  ],
  "instantiation": {
    "task": {
      "id": "fix.inc-api-p95",
      "title": "Production API p95 latency 12s, error rate 18%, started 14 minutes ago, root cause unknown",
      "harm_continuing": true,
      "elapsed_minutes": 14,
      "error_rate": 0.18,
      "p95_seconds": 12,
      "cause_known": false,
      "reproduction_exists": false,
      "citation": "CNL-0108 fixture; not a live incident"
    },
    "profiles": {
      "C-IL-LIVE": {
        "task_id": "fix.inc-api-p95",
        "preset_id": "C-IL-LIVE",
        "roster": [
          "Incident-Commander",
          "Mitigator",
          "Scribe",
          "Skeptic"
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P47",
            "purpose": "Contain harm under a live operational clock"
          },
          {
            "order": 2,
            "protocol_id": "P51",
            "purpose": "Timeboxed spike only if containment needs a probe"
          }
        ],
        "voting_method": "commander-decides-with-dissent-record",
        "stopping_expression": {
          "op": "OR",
          "args": [
            {
              "var": "containment_declared",
              "eq": true
            },
            {
              "op": "AND",
              "args": [
                {
                  "var": "elapsed_minutes",
                  "gte": 30
                },
                {
                  "var": "mitigation_in_place",
                  "eq": true
                }
              ]
            }
          ]
        },
        "stopping_on_timeout": "contain-then-handoff-to-retrospective",
        "floor_may_skip": true,
        "skip_scope": "containment-action-only",
        "clock": "live-operational",
        "evidence_order": "act-now-evidence-later",
        "outcome_type": "containment-action",
        "harm_continuing_at_bind": true
      },
      "C-IL-RETRO": {
        "task_id": "fix.inc-api-p95",
        "preset_id": "C-IL-RETRO",
        "roster": [
          "Facilitator",
          "Evidence-Clerk",
          "Causal-Analyst",
          "Skeptic",
          "Domain-Owner"
        ],
        "protocol_schedule": [
          {
            "order": 1,
            "protocol_id": "P44",
            "purpose": "Walk the 5-whys chain as the causal spine"
          },
          {
            "order": 2,
            "protocol_id": "P38",
            "purpose": "Score competing hypotheses instead of a single story"
          },
          {
            "order": 3,
            "protocol_id": "P40",
            "purpose": "Quality-of-information check on every cited source"
          },
          {
            "order": 4,
            "protocol_id": "P42",
            "purpose": "Map the surviving argument so a skipped premise is visible"
          }
        ],
        "voting_method": "evidence-adjudicated-majority",
        "stopping_expression": {
          "op": "AND",
          "args": [
            {
              "var": "each_why_has_evidence",
              "eq": true
            },
            {
              "var": "competing_hypotheses_scored",
              "eq": true
            }
          ]
        },
        "stopping_on_timeout": "BLOCKED-incomplete-causal-record",
        "floor_may_skip": false,
        "skip_scope": "none",
        "clock": "retrospective-no-action-pressure",
        "evidence_order": "evidence-first",
        "outcome_type": "evidenced-causal-record",
        "harm_continuing_at_bind": true
      }
    }
  },
  "nearest_siblings": {
    "C-IL-LIVE": {
      "nearest_sibling_id": "C-ER47",
      "nearest_sibling_name": "Incident war-room protocol wrapper",
      "distance": 69,
      "diff_axes": [
        "roster",
        "protocols",
        "voting",
        "stopping",
        "floor_may_skip",
        "clock",
        "evidence_order"
      ],
      "supersedes": [
        "C-ER47",
        "P47"
      ]
    },
    "C-IL-RETRO": {
      "nearest_sibling_id": "C-ER-CRT",
      "nearest_sibling_name": "Code-review tribunal with executable oracle",
      "distance": 50,
      "diff_axes": [
        "roster",
        "protocols",
        "voting",
        "stopping",
        "clock"
      ],
      "supersedes": [
        "C-TC44",
        "P44"
      ]
    }
  },
  "floor_runs": {
    "live_containment_unmet_floor": {
      "stop": true,
      "floor_blocked": false,
      "floor_skip_used": true,
      "hung": false,
      "audit": "FLOOR-SKIP-CONTAINMENT-ONLY"
    },
    "live_causal_unmet_floor": {
      "stop": false,
      "floor_blocked": true,
      "floor_skip_used": false,
      "hung": false,
      "audit": "FLOOR-BLOCKS-SATISFIED-STOP"
    },
    "retro_unmet_floor": {
      "stop": false,
      "floor_blocked": true,
      "floor_skip_used": false,
      "hung": false,
      "audit": "FLOOR-BLOCKS-SATISFIED-STOP"
    }
  },
  "schema": {
    "path": "command-center/schema/council-preset.schema.json",
    "executable_schema": "command-center/p2-wave/probes/CNL-0108/fixtures/preset.record.schema.json",
    "validator": "jsonschema.Draft202012Validator",
    "validator_target": "$defs.preset",
    "catalog_schema_note": "Catalog output_schema is a generated generic_report shim without $defs.preset. Record validation uses the unit-local schema. This unit did not rewrite the shared catalog schema.",
    "affected_record_count": 8,
    "error_count": 0,
    "invalid_record_error_count": 1,
    "invalid_record": "C-IL-LIVE with required key id removed"
  },
  "negative_controls": [
    {
      "id": "name-only-clone",
      "state_rejected": "C-ER47 copied with id C-IL-LIVE-FAKE and a live-looking name",
      "what_the_check_does": "mechanism_duplicate fires when profile-axis Hamming is 0 and ids differ. A rename is not a new preset."
    },
    {
      "id": "silent-non-editable-override",
      "state_rejected": "C-IL-LIVE with floor_policy.may_skip_minimum_deliberation cleared though that dial is not editable",
      "what_the_check_does": "reject_non_editable_override REJECTS writes to dials absent from editable_dials."
    },
    {
      "id": "vacuous-schema",
      "state_rejected": "preset record with id removed",
      "what_the_check_does": "Draft202012Validator must report >=1 error; 0 errors would prove the validator is vacuous."
    }
  ],
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0108/probe1_instantiate.py",
      "result": "PASS"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0108/probe2_sibling_schema.py",
      "result": "PASS"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0108-probe2-sibling-schema",
    "verdict": "PASS",
    "independent": true,
    "nearest_sibling_named": true,
    "scope_not_agreement": true,
    "note": "Probe2 re-derives nearest siblings and schema error counts from fixtures; it does not read this answer block."
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0108-incident-lifecycle-family-live-war-room-and-retrospective-.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-preset.schema.json",
      "exists": true,
      "role": "catalog-schema-shim"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0108/fixtures/preset.record.schema.json",
      "exists": true,
      "role": "executable-schema"
    }
  ],
  "ts": "2026-08-25T00:55:09Z",
  "notes": "SUCCESS:CNL-0108 G-1 family design. Live may skip the CNL-0077 floor for containment only. Retrospective may not. Cloud ok=true is not delivery."
}
