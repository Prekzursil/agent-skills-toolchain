{
  "unit_id": "CNL-0041",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0041",
  "schema_version": 1,
  "report_kind": "council-design-note",
  "min_bytes_threshold": 4096,
  "title": "Executable runtime semantics for the 6 ANONYMOUS protocols",
  "question": "Ranging over exactly these 6 records, named so no member can fall through a family mis-assignment (P20 delphi-anonymous-rounds, P21 wideband-delphi-estimation, P22 brainwriting-635, P23 silent-start-pooling, P24 surprisingly-popular-bts, P25 blind-reevaluation): For each of the 6 ANONYMOUS protocol records, at what exact point is anonymity lifted, and what leaks identity before that point (writing style, tool traces, timing)?",
  "answer": "For catalog-named P20-P25, anonymity of protected objects lifts at the UNSEAL scheduler event after the result/score is frozen. P21 is the exception on conversational identity (allowed from DISCUSSION_OPEN) but estimate attribution still waits for UNSEAL. Before UNSEAL the live leak channels are writing_style (forwarded unique markers), tool_traces (public tool_run_id), and timing (unique public delays). All six schedules are EXECUTABLE on this worktree. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent, so the library family-count is NOT-CHECKED, not invented. SUCCESS:CNL-0041",
  "produced_at": "2026-08-25T00:56:43Z",
  "decision": {
    "summary": "For catalog-named P20-P25, anonymity of protected objects lifts at the UNSEAL scheduler event after the result/score is frozen. P21 is the exception on conversational identity (allowed from DISCUSSION_OPEN) but estimate attribution still waits for UNSEAL. Before UNSEAL the live leak channels are writing_style (forwarded unique markers), tool_traces (public tool_run_id), and timing (unique public delays). All six schedules are EXECUTABLE on this worktree. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent, so the library family-count is NOT-CHECKED, not invented; the independent recount is the catalog-named set (n=6) matching fixtures/protocols.json.",
    "anonymity_lift_event": "UNSEAL",
    "family_n": 6,
    "library_count_status": "NOT-CHECKED (file absent)"
  },
  "family": "ANONYMOUS",
  "family_count": 6,
  "library_status": {
    "file": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "present": false,
    "hits": [],
    "count_from_library": null,
    "count_status": "NOT-CHECKED (file absent on this worktree; not invented)",
    "roster_source": "WORK-UNIT-CATALOG.json CNL-0041.question_or_target named records",
    "independent_fixture_source": "command-center/p2-wave/probes/CNL-0041/fixtures/family_roster.json and protocols.json"
  },
  "dependency_artifacts_on_this_tree": {
    "CNL-0001": false,
    "CNL-0010": false,
    "CNL-0022": false
  },
  "dependency_note": "CNL-0001 / CNL-0010 / CNL-0022 output artifacts are absent. This unit uses local stopping evaluators and role-free sealed seats defined in fixtures/protocols.json. It does not claim those dependency contracts were executed.",
  "catalog_named_members": [
    {
      "id": "P20",
      "slug": "delphi-anonymous-rounds",
      "family": "ANONYMOUS"
    },
    {
      "id": "P21",
      "slug": "wideband-delphi-estimation",
      "family": "ANONYMOUS"
    },
    {
      "id": "P22",
      "slug": "brainwriting-635",
      "family": "ANONYMOUS"
    },
    {
      "id": "P23",
      "slug": "silent-start-pooling",
      "family": "ANONYMOUS"
    },
    {
      "id": "P24",
      "slug": "surprisingly-popular-bts",
      "family": "ANONYMOUS"
    },
    {
      "id": "P25",
      "slug": "blind-reevaluation",
      "family": "ANONYMOUS"
    }
  ],
  "protocols": [
    {
      "id": "P20",
      "slug": "delphi-anonymous-rounds",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "First authorized public binding of seat_token to seat_id, immediately after RESULT_FREEZE. There is no discussion phase; conversational and estimate anonymity share this clock.",
      "conversational_identity_allowed_from": null,
      "lift_index": 18,
      "event_types": [
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "FEEDBACK_ANON",
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "RESULT_FREEZE",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "max_rounds"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "rationale text copied into FEEDBACK_ANON",
          "why": "a unique stylistic marker in a forwarded comment binds the sealed estimate to one seat"
        },
        {
          "channel": "tool_traces",
          "carrier": "tool_run_id on the public SUBMIT view",
          "why": "a unique tool invocation id is a runtime identity even when seat_id is stripped"
        },
        {
          "channel": "timing",
          "carrier": "public submit_delay_ms unique to one seat",
          "why": "a delay no other seat shares identifies the remaining participant"
        }
      ],
      "protected_until_unseal": [
        "estimate",
        "rationale"
      ],
      "schedule": [
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "FEEDBACK_ANON",
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "RESULT_FREEZE",
        "UNSEAL"
      ]
    },
    {
      "id": "P21",
      "slug": "wideband-delphi-estimation",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "Estimate-attribution anonymity lifts at UNSEAL after RESULT_FREEZE. Conversational anonymity is not provided after DISCUSSION_OPEN: speech may carry seat_id, estimates may not.",
      "conversational_identity_allowed_from": "DISCUSSION_OPEN",
      "lift_index": 24,
      "event_types": [
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "DISCUSSION_OPEN",
        "DISCUSS",
        "DISCUSS",
        "DISCUSS",
        "DISCUSS",
        "DISCUSS",
        "DISCUSS",
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "RESULT_FREEZE",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "max_rounds"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "estimate rationale attributed during DISCUSS",
          "why": "naming whose number is whose during discussion unseals estimates before RESULT_FREEZE"
        },
        {
          "channel": "tool_traces",
          "carrier": "tool_run_id on public estimate objects",
          "why": "tool provenance on the card binds the number to a runtime identity"
        },
        {
          "channel": "timing",
          "carrier": "public card-submit delays",
          "why": "unique submit timing identifies the card author while discussion is still open"
        }
      ],
      "protected_until_unseal": [
        "estimate"
      ],
      "schedule": [
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "DISCUSSION_OPEN",
        "DISCUSS",
        "ROUND_OPEN",
        "SUBMIT_SEALED",
        "AGGREGATE",
        "RESULT_FREEZE",
        "UNSEAL"
      ]
    },
    {
      "id": "P22",
      "slug": "brainwriting-635",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "Sheet authorship is token-sealed through six pass cycles and POOL_REVEAL. Lift is UNSEAL (plenary unseal) after the pool is published without names.",
      "conversational_identity_allowed_from": null,
      "lift_index": 37,
      "event_types": [
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "POOL_REVEAL",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "pass_cycles"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "idea text on a circulating sheet",
          "why": "a unique phrase written in cycle 1 is still on the sheet when later seats read it"
        },
        {
          "channel": "tool_traces",
          "carrier": "editor session id stamped on a digital sheet cell",
          "why": "the cell's tool_run_id names the writer without a byline"
        },
        {
          "channel": "timing",
          "carrier": "which seat delayed the pass",
          "why": "a unique pass latency identifies who held the sheet"
        }
      ],
      "protected_until_unseal": [
        "sheet_author",
        "idea"
      ],
      "schedule": [
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "CYCLE",
        "POOL_REVEAL",
        "UNSEAL"
      ]
    },
    {
      "id": "P23",
      "slug": "silent-start-pooling",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "Silent generation has no public view. POOL_REVEAL publishes note bodies without authors. Attribution anonymity lifts at UNSEAL.",
      "conversational_identity_allowed_from": null,
      "lift_index": 9,
      "event_types": [
        "SILENT_WINDOW_OPEN",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SUBMIT_SEALED",
        "SILENT_WINDOW_CLOSE",
        "POOL_REVEAL",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "silent_window_closed"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "note body at POOL_REVEAL",
          "why": "the pooled text still carries a unique stylistic marker of its author"
        },
        {
          "channel": "tool_traces",
          "carrier": "tool_run_id on a pooled note",
          "why": "the capture tool names the writer"
        },
        {
          "channel": "timing",
          "carrier": "public note-arrival delays during the silent window",
          "why": "a unique arrival time identifies the remaining silent seat"
        }
      ],
      "protected_until_unseal": [
        "note_author"
      ],
      "schedule": [
        "SILENT_WINDOW_OPEN",
        "SUBMIT_SEALED",
        "SILENT_WINDOW_CLOSE",
        "POOL_REVEAL",
        "UNSEAL"
      ]
    },
    {
      "id": "P24",
      "slug": "surprisingly-popular-bts",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "Ballots (vote + predicted popularity) stay sealed through scoring. Lift is UNSEAL immediately after SCORE_FREEZE. Revealing ballots before freeze makes Bayesian Truth Serum gameable.",
      "conversational_identity_allowed_from": null,
      "lift_index": 8,
      "event_types": [
        "BALLOT_SEALED",
        "BALLOT_SEALED",
        "BALLOT_SEALED",
        "BALLOT_SEALED",
        "BALLOT_SEALED",
        "BALLOT_SEALED",
        "SCORE_SURPRISINGLY_POPULAR",
        "SCORE_FREEZE",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "score_frozen"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "free-text justification attached to a public ballot",
          "why": "justification stylometry identifies the voter before SCORE_FREEZE"
        },
        {
          "channel": "tool_traces",
          "carrier": "tool_run_id on the ballot channel",
          "why": "the voting tool's run id is a seat identity"
        },
        {
          "channel": "timing",
          "carrier": "public ballot arrival unique to one seat",
          "why": "the last unique delay names the remaining voter while scoring is still open"
        }
      ],
      "protected_until_unseal": [
        "ballot",
        "prediction"
      ],
      "schedule": [
        "BALLOT_SEALED",
        "SCORE_SURPRISINGLY_POPULAR",
        "SCORE_FREEZE",
        "UNSEAL"
      ]
    },
    {
      "id": "P25",
      "slug": "blind-reevaluation",
      "verdict": "EXECUTABLE",
      "missing_element": null,
      "anonymity_lift_event": "UNSEAL",
      "anonymity_lift_meaning": "Work-product authorship and reviewer identity stay sealed until SCORE_LOCK. UNSEAL is the first authorized author (and reviewer) reveal.",
      "conversational_identity_allowed_from": null,
      "lift_index": 7,
      "event_types": [
        "INGEST_SEALED",
        "SCORE_SEALED",
        "SCORE_SEALED",
        "SCORE_SEALED",
        "SCORE_SEALED",
        "SCORE_SEALED",
        "SCORE_LOCK",
        "UNSEAL"
      ],
      "stopping": {
        "satisfied": true,
        "reason": "score_locked"
      },
      "leaks_before_lift": [
        {
          "channel": "writing_style",
          "carrier": "work-product text visible to reviewers",
          "why": "stylometry of the artifact identifies the author before SCORE_LOCK"
        },
        {
          "channel": "tool_traces",
          "carrier": "paths or tool_run_id left in the artifact",
          "why": "a unique tool trace in the work product is an author byline"
        },
        {
          "channel": "timing",
          "carrier": "creation timestamp unique to one author seat",
          "why": "a unique ingest time identifies the author while scores are still open"
        }
      ],
      "protected_until_unseal": [
        "author",
        "reviewer"
      ],
      "schedule": [
        "INGEST_SEALED",
        "SCORE_SEALED",
        "SCORE_LOCK",
        "UNSEAL"
      ]
    }
  ],
  "anonymity_lift_summary": {
    "P20": "UNSEAL after RESULT_FREEZE (no discussion phase; one clock)",
    "P21": "estimate attribution UNSEAL after RESULT_FREEZE; conversational identity allowed from DISCUSSION_OPEN",
    "P22": "UNSEAL after six CYCLE passes and POOL_REVEAL",
    "P23": "UNSEAL after POOL_REVEAL; silent window has no public view",
    "P24": "UNSEAL after SCORE_FREEZE (ballots sealed through BTS scoring)",
    "P25": "UNSEAL after SCORE_LOCK (author and reviewer sealed through scoring)"
  },
  "tests": [
    {
      "id": "probe1-family-schedules",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0041/probe1_family_schedules.py",
      "result": "PASS",
      "exit_code": 0,
      "verbatim": "library_present=False catalog_n=6 roster_silent=True bad_fired=True executable=6/6 mutant=NOT-EXECUTABLE\nSUCCESS:CNL-0041-probe1 family recount and executable schedules"
    },
    {
      "id": "probe2-both-states",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0041/probe2_both_states.py",
      "result": "PASS",
      "exit_code": 0,
      "verbatim": "recount_n=6 good_silent=True bad_fired=True schema_ok=None\nNEGATIVE_CONTROL FIRES fired=True silent=False channels=['writing_style'] leak_count=1 first={'channel': 'writing_style', 'event': 'FEEDBACK_ANON', 'index': 8, 'seat_id': 'A', 'object_class': 'rationale', 'marker': 'styA-qx7'}\nSUCCESS:CNL-0041-probe2 both-states leak check and independent recount"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-P20-style-forward-before-unseal",
      "rejects": "P20 FEEDBACK_ANON forwarding a unique writing-style marker before UNSEAL",
      "observed": "FIRES fired=True silent=False channels=['writing_style'] leak_count=1 first={'channel': 'writing_style', 'event': 'FEEDBACK_ANON', 'index': 8, 'seat_id': 'A', 'object_class': 'rationale', 'marker': 'styA-qx7'}",
      "what_the_check_does_on_the_state_it_rejects": "FIRES fired=True silent=False channels=['writing_style'] leak_count=1 first={'channel': 'writing_style', 'event': 'FEEDBACK_ANON', 'index': 8, 'seat_id': 'A', 'object_class': 'rationale', 'marker': 'styA-qx7'}"
    },
    {
      "id": "NC-family-misassignment-P07",
      "rejects": "family_roster_bad.json inserting P07 oxford-debate labeled ANONYMOUS",
      "observed": "FIRES fired=True reasons=['count=7 expected=6', \"id-set ['P07', 'P20', 'P21', 'P22', 'P23', 'P24', 'P25'] != ['P20', 'P21', 'P22', 'P23', 'P24', 'P25']\", 'family-field mis-assignment']"
    },
    {
      "id": "NC-unseal-stripped-schedule",
      "rejects": "P20 schedule with UNSEAL removed",
      "observed": "NOT-EXECUTABLE missing_element=UNSEAL event (anonymity lift never occurs; schedule cannot finish)"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0041-probe2-independent-recount",
    "verdict": "PASS",
    "independent": true,
    "method": "Re-tabulated family membership from fixtures/protocols.json (family=ANONYMOUS) without reading this note's prose; re-ran the leak detector on known-good and planted-bad knobs.",
    "recount_ids": [
      "P20",
      "P21",
      "P22",
      "P23",
      "P24",
      "P25"
    ],
    "recount_n": 6
  },
  "evidence": [
    {
      "claim": "Catalog names exactly six ANONYMOUS records P20-P25.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36320"
    },
    {
      "claim": "Evidence requirement asks for a count from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36312"
    },
    {
      "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read from disk on this worktree.",
      "verdict": "REFUTED",
      "anchor": "command-center/p2-wave/probes/CNL-0041/family.py:library_hits present=false"
    },
    {
      "claim": "Fixture roster P20-P25 is independently countable and matches the catalog named set.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0041/fixtures/family_roster.json:7"
    },
    {
      "claim": "Each of the six named records has an executable turn schedule with a named UNSEAL lift.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0041/fixtures/protocols.json:6"
    },
    {
      "claim": "Identity-leak detector is silent on known-good runs and fires on planted-bad P20 rationale forwarding.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0041/probe2-both-states.raw.json"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0041-executable-runtime-semantics-for-the-6-anonymous-protocols.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "contract"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0041/fixtures/protocols.json",
      "exists": true,
      "role": "executable-schedules"
    }
  ],
  "strongest_surviving_counterargument": "The catalog evidence requirement says to count family members in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json. That file is absent, so a reader could demand BLOCKED until the library is placed on disk. That demand is recorded: library count is NOT-CHECKED, not invented. The six P-ids are named in the unit's own question_or_target, the independent fixture recount agrees, and the runtime question (when is anonymity lifted; what leaks before that) is answered with executable schedules. Placing the library later is a settling experiment, not a reason to fabricate records or to park this unit as BLOCKED while the named six can run.",
  "settling_experiment": "Place 12-COUNCIL-PROTOCOLS-AND-PRESETS.json on disk, count records with family=ANONYMOUS, and diff that id set against P20-P25. A disagreement blocks any later claim that this roster is the library."
}
