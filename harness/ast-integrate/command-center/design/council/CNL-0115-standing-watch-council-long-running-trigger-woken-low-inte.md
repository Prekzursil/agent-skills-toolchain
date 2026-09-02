{
  "unit_id": "CNL-0115",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0115",
  "completion_sentinel": "SUCCESS:CNL-0115",
  "id": "council.preset.standing-watch.trigger-woken",
  "title": "Standing watch council: long-running, trigger-woken, low-intensity",
  "family": "STANDING-WATCH",
  "anonymity": false,
  "rebuttal": false,
  "extends": [
    {
      "id": "P51",
      "kind": "protocol",
      "relation": "extends",
      "note": "Catalog-cited timeboxed-spike-council (CNL-0045). Same low-intensity short panel (max_rounds=2, majority). This preset does not clock-start or forget: it sleeps, wakes on a named trigger, and blocks re-litigation via a settled ledger."
    },
    {
      "id": "C-cited:P51-timeboxed-spike-council",
      "kind": "preset",
      "relation": "extends"
    },
    {
      "id": "CNL-0011",
      "kind": "mechanism",
      "relation": "binds",
      "note": "Replay seeds are populated only for a wake session. Sleep state is not a paused-transcript freeze."
    },
    {
      "id": "CNL-0075",
      "kind": "mechanism",
      "relation": "realizes",
      "note": "Each new settled row carries a lineage_root from idea to decision so a later wake can exhibit the prior chain."
    },
    {
      "id": "council.preset.catalog-class.editable",
      "kind": "catalog-class",
      "relation": "extends",
      "note": "ARC-0003 transcribed catalog-class.editable four-voice base."
    }
  ],
  "roles": [
    {
      "id": "WatchClerk",
      "title": "Watch clerk",
      "voting": false,
      "seated_when": "always",
      "note": "Classifies incoming events. ACK-UNCHANGED is not a vote."
    },
    {
      "id": "Archivist",
      "title": "Archivist",
      "voting": false,
      "seated_when": "always",
      "note": "Serialises sleep_state (ledger + bindings). Does not carry transcripts."
    },
    {
      "id": "DutySentinel",
      "title": "Duty sentinel",
      "voting": false,
      "bind_triggers": true,
      "seated_when": "always",
      "note": "Owns trigger bindings declared before sleep. Mid-sleep bindings cannot be added to manufacture a wake."
    },
    {
      "id": "Chair",
      "title": "Chair",
      "voting": true,
      "seated_when": "wake"
    },
    {
      "id": "Skeptic",
      "title": "Skeptic",
      "voting": true,
      "seated_when": "wake"
    },
    {
      "id": "Pragmatist",
      "title": "Pragmatist",
      "voting": true,
      "seated_when": "wake"
    }
  ],
  "protocol_schedule": [
    {
      "id": "classify-trigger",
      "purpose": "WatchClerk classifies clock vs trigger vs reopen vs re-ask"
    },
    {
      "id": "fingerprint-question",
      "purpose": "hash question_id + material inputs; drop wall-clock and cosmetics"
    },
    {
      "id": "settled-lookup",
      "purpose": "ACK-UNCHANGED on fingerprint match; else wake with prior as exhibit"
    },
    {
      "id": "wake-deliberate",
      "purpose": "low-intensity panel seated only on wake; max_rounds=2",
      "optional": true
    },
    {
      "id": "lineage-bind",
      "purpose": "bind CNL-0075 lineage_root onto the new settled row",
      "optional": true
    },
    {
      "id": "record-ledger",
      "purpose": "one live decision per question_id; replace row, do not fork"
    },
    {
      "id": "return-to-sleep",
      "purpose": "unseat voting roles; persist sleep_state; clear replay_seeds"
    }
  ],
  "voting": {
    "rule": "majority",
    "quorum": 2,
    "on_tie": "BLOCKED-OPEN",
    "note": "Same majority rule as P51. Quorum applies only on wake. ACK-UNCHANGED is a clerk classification, not a ballot."
  },
  "stopping": {
    "max_rounds": 2,
    "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
    "on_timeout": "return-to-sleep",
    "on_stale": "ACK-UNCHANGED",
    "on_unresolved": "BLOCKED-OPEN"
  },
  "watch": {
    "kind": "standing-watch",
    "trigger_woken": true,
    "sleep_default": true,
    "settled_ledger_blocks_relitigation": true,
    "intensity": "low",
    "clock_tick_is_not_a_trigger": true,
    "fingerprint_excludes_wall_clock": true,
    "reopen_requires_token_and_new_evidence": true,
    "binder_role": "DutySentinel",
    "bindings_declared_before_sleep": true
  },
  "default_binding": {
    "base_spec_ref": "CouncilSpec.v2",
    "base_spec_version": "catalog-cited-absent-on-this-worktree",
    "protocol": "P51"
  },
  "editable_dials": [
    "stopping.max_rounds",
    "voting.quorum",
    "watch.bindings"
  ],
  "locked_dials": [
    "watch.trigger_woken",
    "watch.sleep_default",
    "watch.settled_ledger_blocks_relitigation",
    "watch.clock_tick_is_not_a_trigger",
    "watch.fingerprint_excludes_wall_clock",
    "watch.reopen_requires_token_and_new_evidence",
    "voting.rule"
  ],
  "anti_failure": {
    "on_split": "surface-disagreement",
    "no_silent_average": true,
    "name_only_duplicate_forbidden": true,
    "no_relitigation_on_stale_fingerprint": true
  },
  "audit": {
    "persist_sleep_state": true,
    "hash_material_inputs": true,
    "record_ack_separately_from_decision": true
  },
  "nearest_sibling": {
    "id": "C-cited:P51-timeboxed-spike-council",
    "source": "catalog-cited reconstruction on this worktree; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json Path.is_file() is false",
    "named_explicitly": true,
    "distance": 5.714285714285714,
    "ranked": [
      {
        "id": "C-cited:P51-timeboxed-spike-council",
        "distance": 5.714285714285714
      },
      {
        "id": "C-cited:P47-incident-war-room",
        "distance": 7.0
      },
      {
        "id": "C-cited:P53-escalation-ladder",
        "distance": 8.0
      },
      {
        "id": "C-cited:P55-shadow-council",
        "distance": 8.0
      },
      {
        "id": "council.preset.catalog-class.editable",
        "distance": 8.75
      },
      {
        "id": "C-cited:P04-consensus-conference",
        "distance": 9.714285714285715
      }
    ],
    "measurable_diffs": [
      {
        "field": "roles",
        "preset": [
          "Archivist",
          "Chair",
          "DutySentinel",
          "Pragmatist",
          "Skeptic",
          "WatchClerk"
        ],
        "sibling": [
          "Architect",
          "Pragmatist",
          "Skeptic"
        ]
      },
      {
        "field": "protocols",
        "preset": [
          "classify-trigger",
          "fingerprint-question",
          "lineage-bind",
          "record-ledger",
          "return-to-sleep",
          "settled-lookup",
          "wake-deliberate"
        ],
        "sibling": [
          "P51"
        ]
      },
      {
        "field": "stopping_expression",
        "preset": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "sibling": "wall_clock_spike_elapsed\u2192halt"
      },
      {
        "field": "trigger_woken",
        "preset": true,
        "sibling": false
      },
      {
        "field": "sleep_default",
        "preset": true,
        "sibling": false
      },
      {
        "field": "settled_ledger",
        "preset": true,
        "sibling": false
      }
    ],
    "library_file_on_this_worktree": false,
    "library_path_catalogued": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "reconstruction_basis": "WORK-UNIT-CATALOG.json CNL-0045 names P51 timeboxed-spike-council (low-intensity, max_rounds=2, majority). This unit does not claim a byte copy of the absent 72-preset library."
  },
  "question": "A standing council is mostly asleep - what wakes it, what state does it carry between wakings, and how does it avoid re-litigating a question it already settled six weeks ago?",
  "answers": {
    "what_wakes_it": "A named trigger predicate bound by DutySentinel before sleep: content-hash change on a watched source, a threshold breach, or an authorized reopen (reopen_token AND new_evidence_pointer). A clock tick is not a trigger. Cosmetic fields (etag, ad markup, wall-clock, asker_id) cannot wake. watch.trigger_woken and watch.clock_tick_is_not_a_trigger are locked dials.",
    "what_state_it_carries_between_wakings": "sleep_state = {watch_id, settled[], bindings[], replay_seeds={}}. settled[] is the CNL-0075 lineage-bearing decision ledger, one live row per question_id. bindings[] are the DutySentinel trigger predicates. replay_seeds stay empty while asleep: this is not a CNL-0011 paused-transcript freeze. Full transcripts, wall-clock, and participant mood are archived off the live state.",
    "how_it_avoids_relitigating_six_weeks_later": "question_fingerprint = sha256(question_id + canonical material_inputs). Wall-clock, elapsed_days, etag, and ad_markup are dropped before the hash. A trigger whose fingerprint matches a settled row returns ACK-UNCHANGED, seats no voting roles, and writes no new decision_id. The six-week re-ask is that case. A material-input digest change wakes with the prior decision as exhibit (not a blank slate). A bare re-ask without token+evidence does not reopen."
  },
  "instantiations": {
    "stale_six_weeks": {
      "task_id": "fixture.standing-watch.stale-six-weeks",
      "phase": "sleep",
      "classified": {
        "disposition": "ACK-UNCHANGED",
        "wake": false,
        "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
        "prior_decision_id": "D-2026-07-13-shipping-window",
        "reason": "question fingerprint matches settled ledger; wall-clock and cosmetic fields are excluded from the fingerprint; no new decision",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        }
      ],
      "voting_seats": [],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "match fingerprint; ACK-UNCHANGED or stay SLEEP; no vote"
        },
        {
          "id": "return-to-sleep",
          "purpose": "persist unchanged ledger; do not seat the panel"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "sleep has no ballot; ACK-UNCHANGED is a clerk classification, not a vote",
        "quorum_applies": false
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    },
    "clock_tick": {
      "task_id": "fixture.standing-watch.clock-tick",
      "phase": "sleep",
      "classified": {
        "disposition": "SLEEP",
        "wake": false,
        "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
        "prior_decision_id": "D-2026-07-13-shipping-window",
        "reason": "clock tick is not a trigger; a watcher that wakes on the clock is a poller",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        }
      ],
      "voting_seats": [],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "match fingerprint; ACK-UNCHANGED or stay SLEEP; no vote"
        },
        {
          "id": "return-to-sleep",
          "purpose": "persist unchanged ledger; do not seat the panel"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "sleep has no ballot; ACK-UNCHANGED is a clerk classification, not a vote",
        "quorum_applies": false
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    },
    "material_delta": {
      "task_id": "fixture.standing-watch.material-delta",
      "phase": "wake",
      "classified": {
        "disposition": "WAKE-MATERIAL-DELTA",
        "wake": true,
        "question_fingerprint": "2e8c7b43608d20d66639107c4d66731f17f6a0e5d7f0ce623cdf272a841677de",
        "prior_decision_id": "D-2026-07-13-shipping-window",
        "prior_as_exhibit": true,
        "reason": "same question_id, material inputs digest changed; prior decision is exhibit",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        },
        {
          "role_id": "Chair",
          "title": "Chair",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Skeptic",
          "title": "Skeptic",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Pragmatist",
          "title": "Pragmatist",
          "voting": true,
          "bind_triggers": false
        }
      ],
      "voting_seats": [
        "Chair",
        "Skeptic",
        "Pragmatist"
      ],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "find prior decision_id if any; attach as exhibit on delta/reopen"
        },
        {
          "id": "wake-deliberate",
          "purpose": "low-intensity panel; max_rounds=2; prior decision is exhibit"
        },
        {
          "id": "lineage-bind",
          "purpose": "CNL-0075: idea\u2192option\u2192claim\u2192vote\u2192decision recorded on the new row"
        },
        {
          "id": "record-ledger",
          "purpose": "replace the settled row for this question_id; do not fork a second live decision"
        },
        {
          "id": "return-to-sleep",
          "purpose": "clear replay_seeds; persist sleep_state; unseat voting roles"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "Same majority rule as P51. Quorum applies only on wake. ACK-UNCHANGED is a clerk classification, not a ballot."
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    },
    "new_question": {
      "task_id": "fixture.standing-watch.new-question",
      "phase": "wake",
      "classified": {
        "disposition": "WAKE-NEW",
        "wake": true,
        "question_fingerprint": "b17f1e6654d9d59ee78ad7609c68e52e13875e8e7bb521c7957761b23d7775ca",
        "prior_decision_id": null,
        "reason": "no settled row for this question_id",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        },
        {
          "role_id": "Chair",
          "title": "Chair",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Skeptic",
          "title": "Skeptic",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Pragmatist",
          "title": "Pragmatist",
          "voting": true,
          "bind_triggers": false
        }
      ],
      "voting_seats": [
        "Chair",
        "Skeptic",
        "Pragmatist"
      ],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "find prior decision_id if any; attach as exhibit on delta/reopen"
        },
        {
          "id": "wake-deliberate",
          "purpose": "low-intensity panel; max_rounds=2; prior decision is exhibit"
        },
        {
          "id": "lineage-bind",
          "purpose": "CNL-0075: idea\u2192option\u2192claim\u2192vote\u2192decision recorded on the new row"
        },
        {
          "id": "record-ledger",
          "purpose": "replace the settled row for this question_id; do not fork a second live decision"
        },
        {
          "id": "return-to-sleep",
          "purpose": "clear replay_seeds; persist sleep_state; unseat voting roles"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "Same majority rule as P51. Quorum applies only on wake. ACK-UNCHANGED is a clerk classification, not a ballot."
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    },
    "authorized_reopen": {
      "task_id": "fixture.standing-watch.authorized-reopen",
      "phase": "wake",
      "classified": {
        "disposition": "WAKE-REOPEN",
        "wake": true,
        "question_fingerprint": "54dddfd9b63e66726b5483958a20373e2d33eb66349b8a403c9b578f4e36ce1d",
        "prior_decision_id": "D-2026-07-13-shipping-window",
        "prior_as_exhibit": true,
        "reason": "authorized reopen with new evidence; prior decision is exhibit, not blank slate",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        },
        {
          "role_id": "Chair",
          "title": "Chair",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Skeptic",
          "title": "Skeptic",
          "voting": true,
          "bind_triggers": false
        },
        {
          "role_id": "Pragmatist",
          "title": "Pragmatist",
          "voting": true,
          "bind_triggers": false
        }
      ],
      "voting_seats": [
        "Chair",
        "Skeptic",
        "Pragmatist"
      ],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "find prior decision_id if any; attach as exhibit on delta/reopen"
        },
        {
          "id": "wake-deliberate",
          "purpose": "low-intensity panel; max_rounds=2; prior decision is exhibit"
        },
        {
          "id": "lineage-bind",
          "purpose": "CNL-0075: idea\u2192option\u2192claim\u2192vote\u2192decision recorded on the new row"
        },
        {
          "id": "record-ledger",
          "purpose": "replace the settled row for this question_id; do not fork a second live decision"
        },
        {
          "id": "return-to-sleep",
          "purpose": "clear replay_seeds; persist sleep_state; unseat voting roles"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "Same majority rule as P51. Quorum applies only on wake. ACK-UNCHANGED is a clerk classification, not a ballot."
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    },
    "bare_reask": {
      "task_id": "fixture.standing-watch.bare-reask",
      "phase": "sleep",
      "classified": {
        "disposition": "ACK-UNCHANGED",
        "wake": false,
        "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
        "prior_decision_id": "D-2026-07-13-shipping-window",
        "reason": "re-ask without reopen_token AND new_evidence_pointer; settled ledger stands",
        "new_decision_id": null
      },
      "roster": [
        {
          "role_id": "WatchClerk",
          "title": "Watch clerk",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "Archivist",
          "title": "Archivist",
          "voting": false,
          "bind_triggers": false
        },
        {
          "role_id": "DutySentinel",
          "title": "Duty sentinel",
          "voting": false,
          "bind_triggers": true
        }
      ],
      "voting_seats": [],
      "protocol_schedule": [
        {
          "id": "classify-trigger",
          "purpose": "WatchClerk classifies the event against the ledger"
        },
        {
          "id": "fingerprint-question",
          "purpose": "hash question_id + material inputs; drop cosmetic keys"
        },
        {
          "id": "settled-lookup",
          "purpose": "match fingerprint; ACK-UNCHANGED or stay SLEEP; no vote"
        },
        {
          "id": "return-to-sleep",
          "purpose": "persist unchanged ledger; do not seat the panel"
        }
      ],
      "voting": {
        "rule": "majority",
        "quorum": 2,
        "on_tie": "BLOCKED-OPEN",
        "note": "sleep has no ballot; ACK-UNCHANGED is a clerk classification, not a vote",
        "quorum_applies": false
      },
      "stopping": {
        "max_rounds": 2,
        "expression": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN",
        "on_timeout": "return-to-sleep",
        "on_stale": "ACK-UNCHANGED",
        "on_unresolved": "BLOCKED-OPEN"
      },
      "watch": {
        "kind": "standing-watch",
        "trigger_woken": true,
        "sleep_default": true,
        "settled_ledger_blocks_relitigation": true,
        "intensity": "low",
        "clock_tick_is_not_a_trigger": true,
        "fingerprint_excludes_wall_clock": true,
        "reopen_requires_token_and_new_evidence": true,
        "binder_role": "DutySentinel",
        "bindings_declared_before_sleep": true
      },
      "sleep_state": {
        "kind": "standing-watch-sleep-state",
        "watch_id": "watch.shipping-window",
        "settled": [
          {
            "question_id": "Q-shipping-window",
            "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
            "decision_id": "D-2026-07-13-shipping-window",
            "lineage_root": "idea:I-keep-current-window\u2192option:O-no-change\u2192claim:C-stable-sla\u2192vote:V-3-0\u2192decision:D-2026-07-13-shipping-window",
            "material_inputs_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c",
            "decided_logical": "wake-1"
          }
        ],
        "bindings": [
          {
            "source_id": "src-shipping-policy",
            "predicate": "content-hash-change",
            "last_digest": "73bd070d999c75aa26f599125d058cbcef7d8e43d111e63a715126fc720e142c"
          }
        ],
        "replay_seeds": {},
        "not_carried": [
          "wall_clock",
          "full_transcripts",
          "participant_mood",
          "paused_mid_round_cursor"
        ],
        "cnl_0011_distinction": "CNL-0011 serialises a paused mid-flight council so resume is byte-identical. Sleep is terminal-for-now: the next wake is a new session bound by the ledger, not a resume of the old transcript."
      }
    }
  },
  "classify_cases": {
    "stale_six_weeks": {
      "disposition": "ACK-UNCHANGED",
      "wake": false,
      "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
      "prior_decision_id": "D-2026-07-13-shipping-window",
      "reason": "question fingerprint matches settled ledger; wall-clock and cosmetic fields are excluded from the fingerprint; no new decision",
      "new_decision_id": null
    },
    "clock_tick": {
      "disposition": "SLEEP",
      "wake": false,
      "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
      "prior_decision_id": "D-2026-07-13-shipping-window",
      "reason": "clock tick is not a trigger; a watcher that wakes on the clock is a poller",
      "new_decision_id": null
    },
    "material_delta": {
      "disposition": "WAKE-MATERIAL-DELTA",
      "wake": true,
      "question_fingerprint": "2e8c7b43608d20d66639107c4d66731f17f6a0e5d7f0ce623cdf272a841677de",
      "prior_decision_id": "D-2026-07-13-shipping-window",
      "prior_as_exhibit": true,
      "reason": "same question_id, material inputs digest changed; prior decision is exhibit",
      "new_decision_id": null
    },
    "new_question": {
      "disposition": "WAKE-NEW",
      "wake": true,
      "question_fingerprint": "b17f1e6654d9d59ee78ad7609c68e52e13875e8e7bb521c7957761b23d7775ca",
      "prior_decision_id": null,
      "reason": "no settled row for this question_id",
      "new_decision_id": null
    },
    "authorized_reopen": {
      "disposition": "WAKE-REOPEN",
      "wake": true,
      "question_fingerprint": "54dddfd9b63e66726b5483958a20373e2d33eb66349b8a403c9b578f4e36ce1d",
      "prior_decision_id": "D-2026-07-13-shipping-window",
      "prior_as_exhibit": true,
      "reason": "authorized reopen with new evidence; prior decision is exhibit, not blank slate",
      "new_decision_id": null
    },
    "bare_reask": {
      "disposition": "ACK-UNCHANGED",
      "wake": false,
      "question_fingerprint": "36b6ee1fff25ec1c73a81af62c3f44aa6e6feb60a5bfde3e103487503b3ddba7",
      "prior_decision_id": "D-2026-07-13-shipping-window",
      "reason": "re-ask without reopen_token AND new_evidence_pointer; settled ledger stands",
      "new_decision_id": null
    }
  },
  "negative_control": {
    "rejected_state": "same question_id and material inputs, elapsed_days=42, council seats the panel and records a new competing decision",
    "check_does": "classify returns disposition=ACK-UNCHANGED, wake=false, new_decision_id=null; instantiate seats WatchClerk+Archivist+DutySentinel only; voting_seats is empty",
    "observed_disposition": "ACK-UNCHANGED",
    "observed_wake": false,
    "observed_new_decision_id": null,
    "observed_voting_seats": []
  },
  "library_disclosure": {
    "12_COUNCIL_PROTOCOLS_AND_PRESETS_json": false,
    "11_COUNCIL_SPECIFICATION_schema_json": false,
    "honest_limit": "Nearest sibling is named from catalog-cited P51, not from a live parse of the 72-record library. If that file lands, re-run nearest_sibling over its presets; a closer C-id replaces C-cited:P51-timeboxed-spike-council."
  },
  "schema_note": "Catalog output_schema is a GENERATED SHIM whose $ref points at https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver tries the network. This unit validates against the per-unit schema command-center/p2-wave/probes/CNL-0115/council-preset.schema.json. Overwriting the shared catalog schema would be a sibling rebuild circle.",
  "tests": [
    {
      "id": "instantiate-stale-sleep",
      "result": "PASS",
      "roster": [
        "WatchClerk",
        "Archivist",
        "DutySentinel"
      ],
      "schedule": [
        "classify-trigger",
        "fingerprint-question",
        "settled-lookup",
        "return-to-sleep"
      ],
      "voting": "majority",
      "stopping": "no_trigger\u2192SLEEP || stale_fp\u2192ACK-UNCHANGED || wake_rounds<=2 && unresolved\u2192BLOCKED-OPEN"
    },
    {
      "id": "instantiate-delta-wake-differs",
      "result": "PASS",
      "roster": [
        "Chair",
        "Skeptic",
        "Pragmatist"
      ],
      "schedule": [
        "classify-trigger",
        "fingerprint-question",
        "settled-lookup",
        "wake-deliberate",
        "lineage-bind",
        "record-ledger",
        "return-to-sleep"
      ]
    },
    {
      "id": "nearest-sibling-P51",
      "result": "PASS",
      "sibling": "C-cited:P51-timeboxed-spike-council",
      "distance": 5.714285714285714
    }
  ]
}
