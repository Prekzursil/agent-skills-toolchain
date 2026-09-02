{
  "unit_id": "CNL-0038",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0038",
  "title": "Executable runtime semantics for the 6 DELIBERATIVE protocols",
  "question": "Ranging over exactly these 6 records, named so no member can fall through a family mis-assignment (P01 free-form-moderated-panel, P02 round-robin, P03 fishbowl, P04 consensus-conference, P05 rotating-chair, P06 nominal-group-technique): For each of the 6 DELIBERATIVE protocol records, what is the executable turn-by-turn runtime semantics - and which of the 6 cannot be executed as written because its stopping condition is stated in prose that no evaluator can read?",
  "answer": "Of the 6 DELIBERATIVE records (P01\u2013P06), five have evaluator-readable stopping trees and emit a finite turn-by-turn schedule that is false before the last round and true at halt. P01 free-form-moderated-panel cannot be executed as written: its stopping condition is moderator-discretion prose that the AND/OR/NOT/ANY/ALL/weighted evaluator cannot parse. The ADVERSARIAL decoy P07 is excluded by family filter.",
  "family": {
    "name": "DELIBERATIVE",
    "expected_n": 6,
    "counted_n": 6,
    "catalog_named_n": 6,
    "library_present": false,
    "library_path": null,
    "slice_path": "command-center/p2-wave/probes/CNL-0038/fixtures/family-slice.json",
    "source_claimed": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "enumeration_basis": "Catalog item CNL-0038 names P01\u2013P06 so no member can fall through a family mis-assignment. Independent recount: evidence_requirement expected n=6, parenthetical P-id list n=6, family=DELIBERATIVE rows in the local family slice n=6. The Windows library file is absent on this worktree; the slice is not a byte copy of that file.",
    "members": [
      {
        "id": "P01",
        "slug": "free-form-moderated-panel"
      },
      {
        "id": "P02",
        "slug": "round-robin"
      },
      {
        "id": "P03",
        "slug": "fishbowl"
      },
      {
        "id": "P04",
        "slug": "consensus-conference"
      },
      {
        "id": "P05",
        "slug": "rotating-chair"
      },
      {
        "id": "P06",
        "slug": "nominal-group-technique"
      }
    ],
    "slice_family_ids": [
      "P01",
      "P02",
      "P03",
      "P04",
      "P05",
      "P06"
    ],
    "decoy_excluded": [
      "P07"
    ],
    "counts_agree": true
  },
  "verdicts": [
    {
      "record_id": "P01",
      "slug": "free-form-moderated-panel",
      "family": "DELIBERATIVE",
      "verdict": "NOT-EXECUTABLE",
      "stopping_readable": false,
      "classifier": "prose-unreadable:infix-expected-CMP-got-ID",
      "missing_element": "evaluator-readable stopping expression (AND/OR/NOT, ANY, ALL, weighted, or infix atom); classifier=prose-unreadable:infix-expected-CMP-got-ID",
      "turn_schedule": null,
      "stopping_as_written": "when the moderator judges the discussion has run its course and remaining comments are repetitive"
    },
    {
      "record_id": "P02",
      "slug": "round-robin",
      "family": "DELIBERATIVE",
      "verdict": "EXECUTABLE",
      "stopping_readable": true,
      "classifier": "ok",
      "missing_element": null,
      "turn_schedule": {
        "turn_count": 6,
        "stopped_after_round": 2,
        "stop_was_false_before_end": true,
        "stop_true_at_end": true,
        "turns": [
          {
            "round": 1,
            "seat": "A",
            "act": "speak"
          },
          {
            "round": 1,
            "seat": "B",
            "act": "speak"
          },
          {
            "round": 1,
            "seat": "C",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "A",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "B",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "C",
            "act": "speak"
          }
        ]
      },
      "stopping_as_written": {
        "op": "AND",
        "args": [
          {
            "var": "rounds",
            "cmp": ">=",
            "value": 2
          },
          {
            "op": "ALL",
            "over": "seats",
            "pred": {
              "var": "spoke_this_round",
              "cmp": "==",
              "value": true
            }
          }
        ]
      }
    },
    {
      "record_id": "P03",
      "slug": "fishbowl",
      "family": "DELIBERATIVE",
      "verdict": "EXECUTABLE",
      "stopping_readable": true,
      "classifier": "ok",
      "missing_element": null,
      "turn_schedule": {
        "turn_count": 10,
        "stopped_after_round": 2,
        "stop_was_false_before_end": true,
        "stop_true_at_end": true,
        "turns": [
          {
            "round": 1,
            "seat": "A",
            "ring": "inner",
            "act": "speak"
          },
          {
            "round": 1,
            "seat": "B",
            "ring": "inner",
            "act": "speak"
          },
          {
            "round": 1,
            "seat": "C",
            "ring": "outer",
            "act": "observe"
          },
          {
            "round": 1,
            "seat": "D",
            "ring": "outer",
            "act": "observe"
          },
          {
            "round": 1,
            "seat": "C",
            "act": "promote-to-inner"
          },
          {
            "round": 2,
            "seat": "B",
            "ring": "inner",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "C",
            "ring": "inner",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "D",
            "ring": "outer",
            "act": "observe"
          },
          {
            "round": 2,
            "seat": "A",
            "ring": "outer",
            "act": "observe"
          },
          {
            "round": 2,
            "seat": "D",
            "act": "promote-to-inner"
          }
        ]
      },
      "stopping_as_written": {
        "op": "AND",
        "args": [
          {
            "var": "rounds",
            "cmp": ">=",
            "value": 2
          },
          {
            "var": "promotions",
            "cmp": ">=",
            "value": 2
          }
        ]
      }
    },
    {
      "record_id": "P04",
      "slug": "consensus-conference",
      "family": "DELIBERATIVE",
      "verdict": "EXECUTABLE",
      "stopping_readable": true,
      "classifier": "ok",
      "missing_element": null,
      "turn_schedule": {
        "turn_count": 8,
        "stopped_after_round": 2,
        "stop_was_false_before_end": true,
        "stop_true_at_end": true,
        "turns": [
          {
            "round": 1,
            "seat": "A",
            "act": "propose"
          },
          {
            "round": 1,
            "seat": "B",
            "act": "propose"
          },
          {
            "round": 1,
            "seat": "C",
            "act": "propose"
          },
          {
            "round": 1,
            "seat": "B",
            "act": "object"
          },
          {
            "round": 2,
            "seat": "A",
            "act": "propose"
          },
          {
            "round": 2,
            "seat": "B",
            "act": "propose"
          },
          {
            "round": 2,
            "seat": "C",
            "act": "propose"
          },
          {
            "round": 2,
            "seat": "B",
            "act": "withdraw-objection"
          }
        ]
      },
      "stopping_as_written": {
        "op": "AND",
        "args": [
          {
            "var": "unresolved_objections",
            "cmp": "==",
            "value": 0
          },
          {
            "var": "rounds",
            "cmp": ">=",
            "value": 2
          }
        ]
      }
    },
    {
      "record_id": "P05",
      "slug": "rotating-chair",
      "family": "DELIBERATIVE",
      "verdict": "EXECUTABLE",
      "stopping_readable": true,
      "classifier": "ok",
      "missing_element": null,
      "turn_schedule": {
        "turn_count": 9,
        "stopped_after_round": 3,
        "stop_was_false_before_end": true,
        "stop_true_at_end": true,
        "turns": [
          {
            "round": 1,
            "seat": "A",
            "act": "open-as-chair"
          },
          {
            "round": 1,
            "seat": "B",
            "act": "speak"
          },
          {
            "round": 1,
            "seat": "C",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "B",
            "act": "open-as-chair"
          },
          {
            "round": 2,
            "seat": "A",
            "act": "speak"
          },
          {
            "round": 2,
            "seat": "C",
            "act": "speak"
          },
          {
            "round": 3,
            "seat": "C",
            "act": "open-as-chair"
          },
          {
            "round": 3,
            "seat": "A",
            "act": "speak"
          },
          {
            "round": 3,
            "seat": "B",
            "act": "speak"
          }
        ]
      },
      "stopping_as_written": {
        "op": "ALL",
        "over": "seats",
        "pred": {
          "var": "has_chaired",
          "cmp": "==",
          "value": true
        }
      }
    },
    {
      "record_id": "P06",
      "slug": "nominal-group-technique",
      "family": "DELIBERATIVE",
      "verdict": "EXECUTABLE",
      "stopping_readable": true,
      "classifier": "ok",
      "missing_element": null,
      "turn_schedule": {
        "turn_count": 12,
        "stopped_after_round": 4,
        "stop_was_false_before_end": true,
        "stop_true_at_end": true,
        "turns": [
          {
            "round": 1,
            "phase": "silent_generate",
            "seat": "A",
            "act": "write"
          },
          {
            "round": 1,
            "phase": "silent_generate",
            "seat": "B",
            "act": "write"
          },
          {
            "round": 1,
            "phase": "silent_generate",
            "seat": "C",
            "act": "write"
          },
          {
            "round": 2,
            "phase": "round_robin_share",
            "seat": "A",
            "act": "share"
          },
          {
            "round": 2,
            "phase": "round_robin_share",
            "seat": "B",
            "act": "share"
          },
          {
            "round": 2,
            "phase": "round_robin_share",
            "seat": "C",
            "act": "share"
          },
          {
            "round": 3,
            "phase": "clarify",
            "seat": "A",
            "act": "clarify"
          },
          {
            "round": 3,
            "phase": "clarify",
            "seat": "B",
            "act": "clarify"
          },
          {
            "round": 3,
            "phase": "clarify",
            "seat": "C",
            "act": "clarify"
          },
          {
            "round": 4,
            "phase": "rank",
            "seat": "A",
            "act": "ballot"
          },
          {
            "round": 4,
            "phase": "rank",
            "seat": "B",
            "act": "ballot"
          },
          {
            "round": 4,
            "phase": "rank",
            "seat": "C",
            "act": "ballot"
          }
        ]
      },
      "stopping_as_written": {
        "op": "AND",
        "args": [
          {
            "var": "phase",
            "cmp": "==",
            "value": "rank"
          },
          {
            "var": "ballots_cast",
            "cmp": "==",
            "value": 3
          }
        ]
      }
    }
  ],
  "not_executable_ids": [
    "P01"
  ],
  "executable_ids": [
    "P02",
    "P03",
    "P04",
    "P05",
    "P06"
  ],
  "executable_count": 5,
  "not_executable_count": 1,
  "which_cannot_execute_as_written": "P01",
  "tests": [
    {
      "id": "family-coverage",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0038/probe1_family_recount.py",
      "result": "PASS"
    },
    {
      "id": "both-states-prose-stop",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0038/probe2_both_states.py",
      "result": "PASS"
    }
  ],
  "both_states": {
    "check": "prose-stop recognizer (FIRE iff stopping is not evaluator-readable)",
    "known_good": {
      "fixture": "known-good P02 round-robin typed stop",
      "record_id": "P02",
      "stopping": {
        "op": "AND",
        "args": [
          {
            "var": "rounds",
            "cmp": ">=",
            "value": 2
          },
          {
            "op": "ALL",
            "over": "seats",
            "pred": {
              "var": "spoke_this_round",
              "cmp": "==",
              "value": true
            }
          }
        ]
      },
      "readable": true,
      "classifier": "ok",
      "fire": false,
      "verbatim": "P02 known-good readable=True fire=False classifier=ok"
    },
    "planted_bad": {
      "fixture": "planted-bad P02 stopping replaced with moderator-style prose",
      "record_id": "P02",
      "stopping": "when everyone seems done",
      "readable": false,
      "classifier": "prose-unreadable:infix-expected-CMP-got-ID",
      "fire": true,
      "schedule_executable": false,
      "missing_element": "evaluator-readable stopping expression (AND/OR/NOT, ANY, ALL, weighted, or infix atom); classifier=prose-unreadable:infix-expected-CMP-got-ID",
      "verbatim": "P02 planted-bad readable=False fire=True classifier=prose-unreadable:infix-expected-CMP-got-ID executable=False"
    },
    "silent_on_good": true,
    "fires_on_bad": true,
    "pass": true
  },
  "negative_control": {
    "reject_state": "when everyone seems done",
    "what_the_check_does": "On a typed round-robin record whose stopping field is replaced with prose ('when everyone seems done'), the recognizer FIRES (readable=false) and the runtime refuses to emit a turn schedule, naming the missing evaluator-readable stopping expression. It does not invent a max_rounds halt to make the protocol appear executable.",
    "verbatim": "P02 planted-bad readable=False fire=True classifier=prose-unreadable:infix-expected-CMP-got-ID executable=False",
    "fire": true,
    "executable": false
  },
  "reviewer": {
    "reviewer_id": "CNL-0038-probe1-independent-recount",
    "independent": true,
    "verdict": "PASS",
    "method": "Re-parse catalog named P-ids and expected n; re-filter family=DELIBERATIVE from the slice; do not read the author's answer paragraph. A disagreement in n blocks the unit.",
    "counted_n": 6,
    "author_n": 6
  },
  "evidence": [
    {
      "claim": "Catalog names exactly six DELIBERATIVE members P01\u2013P06.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0038.question_or_target"
    },
    {
      "claim": "Independent family=DELIBERATIVE filter yields the same six ids; P07 decoy is excluded.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0038/fixtures/family-slice.json"
    },
    {
      "claim": "P01 stopping is prose no evaluator can read; runtime emits NOT-EXECUTABLE naming the missing expression.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0038/stopping.py"
    },
    {
      "claim": "P02\u2013P06 emit finite schedules whose stop is false before the last round and true at halt.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0038/runtime.py"
    },
    {
      "claim": "Both-states: recognizer is silent on typed P02 and FIRES on planted prose P02.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0038/analyze.py:both_states"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0038-executable-runtime-semantics-for-the-6-deliberative-protoc.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0038/fixtures/family-slice.json",
      "exists": true,
      "role": "family-slice"
    }
  ],
  "completion_sentinel": "SUCCESS:CNL-0038"
}
