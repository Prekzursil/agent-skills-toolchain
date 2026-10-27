{
  "unit_id": "CNL-0061",
  "kind": "council-design-note",
  "state": "SUCCESS",
  "schema_version": 1,
  "title": "Ranked-choice tabulation and its known pathologies",
  "question": "What is the exact IRV tabulation procedure including elimination ties, and which pathologies (non-monotonicity, later-no-harm violation) can actually occur at council roster sizes of 3-15?",
  "claim_under_test": "IRV-COUNCIL-v1 (strict majority of continuing weight; eliminate exactly one last-place option via lookback-then-lex-min) is non-monotonic at roster 7 with 3 options, and later-no-harm does not fire under this IRV.",
  "sentinel": "SUCCESS:CNL-0061",
  "completion_sentinel": "SUCCESS:CNL-0061",
  "answer": "IRV-COUNCIL-v1 tabulates ranked ballots by repeating, until a unique strict majority of continuing weight exists: tally the first standing preference of each ballot (weight default 1.0; weight != 1.0 is an input whose provenance is CNL-0023, not this tabulator), drop exhausted ballots from the denominator, and if nobody has tally > continuing/2, eliminate exactly one last-place option. Last-place ties use lookback-then-lex-min-elim: walk earlier rounds from the first, keep only the unique-lowest among the tied set, and if still tied eliminate min(option_id). Never RNG; never batch-eliminate the whole last-place set. At roster sizes 3-15, non-monotonicity CAN occur: the worked 7-seat 3-option fixture elects C, then raising C on one A>C>B ballot to C>A>B elects B, because the raise turns a B/C last-place tie into an A/B last-place tie and lex-min eliminates A instead of B. The 3-candidate raise-to-first census at n=7 counts 6 flipping (profile, source-type) pairs; n=3..6 count 0 under the same search. Later-no-harm does NOT occur under this IRV (truncated first-choice A still wins after later ranks are filled; 0 violations in the reviewer random trials). A planted second-place-plurality method does violate later-no-harm, so the checker is not vacuous. SUCCESS:CNL-0061",
  "procedure": {
    "id": "IRV-COUNCIL-v1",
    "tie_policy": "lookback-then-lex-min-elim",
    "majority_rule": "strict-majority-of-continuing-weight",
    "steps": [
      "standing := option set; each ballot is a truncated ranking plus weight>0",
      "tally first remaining standing preference by weight; exhausted ballots leave the denominator",
      "quota := continuing_weight/2; unique tally > quota elects (strict; 50% is not a win)",
      "if continuing_weight==0, elect lex-min(standing) and flag exhausted_residual",
      "else last_place := argmin tally including zeros; if last_place==standing elect lex-min",
      "if |last_place|==1 eliminate it; if >1 lookback then lex-min \u2014 eliminate exactly one",
      "repeat; deterministic given options, ballots, and this policy"
    ],
    "weight": {
      "default": 1.0,
      "non_equal": "multiplied into the tally; unjustified non-1.0 is CNL-0023's spec-validation job. CNL-0023 artifact is absent on this tree; pathology fixtures are equal-weight. Weighted NM-7x3 with one C>B>A ballot at weight 2.0 elects the same winner as two unit ballots.",
      "weighted_fixture_winner": "C",
      "unit_ballot_winner": "C"
    },
    "rejected_alternatives": [
      {
        "id": "batch-eliminate-last-place-set",
        "why": "Eliminating every last-place option in one step can skip a candidate who would have won the next pairwise and is not replay-distinct from lookback."
      },
      {
        "id": "rng-coin-flip",
        "why": "Not replay-safe; councils must re-tabulate identically from the ballot file."
      },
      {
        "id": "majority-of-original-n",
        "why": "Exhausted ballots would inflate the quota and can block a majority of remaining opinion. Continuing-weight majority is the rule."
      }
    ]
  },
  "worked_examples": {
    "nm7x3": {
      "roster_size": 7,
      "options": 3,
      "raised_candidate": "C",
      "before_winner": "C",
      "after_winner": "B",
      "fired": true,
      "reviewer_before": "C",
      "reviewer_after": "B",
      "before_rounds": [
        {
          "standing": [
            "A",
            "B",
            "C"
          ],
          "tally": {
            "A": 3.0,
            "B": 2.0,
            "C": 2.0
          },
          "continuing_weight": 7.0,
          "exhausted_weight": 0.0,
          "quota": 3.5,
          "last_place": [
            "B",
            "C"
          ],
          "eliminated": "B",
          "elim_rule": "lex-min",
          "tie_break_used": true
        },
        {
          "standing": [
            "A",
            "C"
          ],
          "tally": {
            "A": 3.0,
            "C": 4.0
          },
          "continuing_weight": 7.0,
          "exhausted_weight": 0.0,
          "quota": 3.5,
          "winner": "C",
          "majority": true
        }
      ],
      "after_rounds": [
        {
          "standing": [
            "A",
            "B",
            "C"
          ],
          "tally": {
            "A": 2.0,
            "B": 2.0,
            "C": 3.0
          },
          "continuing_weight": 7.0,
          "exhausted_weight": 0.0,
          "quota": 3.5,
          "last_place": [
            "A",
            "B"
          ],
          "eliminated": "A",
          "elim_rule": "lex-min",
          "tie_break_used": true
        },
        {
          "standing": [
            "B",
            "C"
          ],
          "tally": {
            "B": 4.0,
            "C": 3.0
          },
          "continuing_weight": 7.0,
          "exhausted_weight": 0.0,
          "quota": 3.5,
          "winner": "B",
          "majority": true
        }
      ],
      "ballots_original": [
        {
          "ranks": [
            "A",
            "B",
            "C"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "A",
            "B",
            "C"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "A",
            "C",
            "B"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "B",
            "C",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "B",
            "C",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "C",
            "B",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "C",
            "B",
            "A"
          ],
          "weight": 1.0
        }
      ],
      "ballots_raised": [
        {
          "ranks": [
            "A",
            "B",
            "C"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "A",
            "B",
            "C"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "C",
            "A",
            "B"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "B",
            "C",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "B",
            "C",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "C",
            "B",
            "A"
          ],
          "weight": 1.0
        },
        {
          "ranks": [
            "C",
            "B",
            "A"
          ],
          "weight": 1.0
        }
      ],
      "narrative": "Original first-round tally A=3, B=2, C=2. last_place={B,C}, no history, lex-min eliminates B. A vs C runoff is 3-4, C wins. One seat raises C from second to first (A>C>B becomes C>A>B). New first-round tally A=2, B=2, C=3. last_place={A,B}, lex-min eliminates A. B vs C runoff is 4-3, B wins. Raising the winner unseated them. This is a worked example, not a citation."
    },
    "nm7x4": {
      "roster_size": 7,
      "options": 4,
      "raised_candidate": "D",
      "before_winner": "D",
      "after_winner": "B",
      "fired": true,
      "narrative": "Round-1 last place is unique (C has 0 first preferences). Raising D on A>B>D>C still flips D to B, so non-monotonicity at roster 7 is not only a round-1 last-place tie."
    }
  },
  "pathologies": {
    "non_monotonicity": {
      "occurs_at_roster_3_to_15": true,
      "smallest_3option_roster_with_raise_to_first_flip": 7,
      "census_n7_raise_to_first_hits": 6,
      "note": "3-option exhaustive raise-to-first search: n=3..6 have 0 hits; n=7 has 6 (profile, source-type) hits. Every 3-option hit in that search uses a last-place tie, which is why the elimination tie-break is load-bearing. Opposite lex-max elimination on the same NM-7x3 ballots elects a different original winner; the policy is part of the procedure, not an afterthought."
    },
    "later_no_harm": {
      "occurs_at_roster_3_to_15": false,
      "irv_truncated_then_completed_fired": false,
      "irv_silent": true,
      "why": "A later rank is never consulted while an earlier remaining preference on that ballot is still standing, so adding later ranks cannot reduce an earlier-ranked continuing candidate's tally. Truncation tests are required because complete rankings have no later rank left to add."
    }
  },
  "both_states": {
    "nonmonotonicity_fires_on_nm7x3": true,
    "nonmonotonicity_silent_on_majority7": true,
    "lnh_silent_on_irv": true,
    "lnh_fires_on_second_place_bait": true
  },
  "negative_controls": [
    {
      "id": "NC-MAJORITY-7-SILENT",
      "on_state": "majority-7: A already has 4/7 > 3.5; raising A on one B>A>C ballot to A>B>C must NOT look like non-monotonicity",
      "observed": "silent=true fired=false before_winner=A after_winner=A verbatim={\"after_winner\": \"A\", \"before_winner\": \"A\", \"fired\": false, \"fixture\": \"majority-7\", \"silent\": true}"
    },
    {
      "id": "NC-LNH-BAIT-FIRES",
      "on_state": "planted second-place-plurality on truncated [A]x3+[B]x2 versus one ballot completed to A>B \u2014 the state the LNH checker must reject",
      "observed": "fired=true before_winner=A after_winner=B verbatim={\"after_winner\": \"B\", \"before_winner\": \"A\", \"fired\": true, \"fixture\": \"lnh-bait-second-place-plurality\", \"silent\": false}"
    }
  ],
  "tests": [
    {
      "id": "non-monotonicity-worked-example",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0061/probe1_nonmonotonicity.py",
      "result": "PASS",
      "verbatim": "nm7x3_fired=True before=C after=B last_place=B,C elim=B\nMAJORITY-NEGATIVE-CONTROL {\"after_winner\": \"A\", \"before_winner\": \"A\", \"fired\": false, \"fixture\": \"majority-7\", \"raised_candidate\": \"A\", \"silent\": true}\nnm7x4_fired=True census_n7=6 weighted_winner=C majority_silent=True\nSUCCESS:CNL-0061-probe1 non-monotonicity worked example and majority negative control"
    },
    {
      "id": "independent-recount-and-later-no-harm",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0061/probe2_reviewer_recount.py",
      "result": "PASS",
      "verbatim": "RECOUNT-NM7X3 {\"agree\": true, \"author_after\": \"B\", \"author_before\": \"C\", \"author_fired\": true, \"reviewer_after\": \"B\", \"reviewer_before\": \"C\", \"reviewer_fired\": true}\nRECOUNT-MAJORITY {\"agree\": true, \"author_after\": \"A\", \"author_before\": \"A\", \"author_fired\": false, \"reviewer_after\": \"A\", \"reviewer_before\": \"A\", \"reviewer_fired\": false}\nLNH-IRV {\"after_winner\": \"A\", \"before_winner\": \"A\", \"fired\": false, \"first_choice\": \"A\", \"fixture\": \"lnh-irv-truncated-then-completed\", \"method\": \"IRV-COUNCIL-v1-reviewer-queues\", \"silent\": true}\nLNH-BAIT-NEGATIVE-CONTROL {\"after_winner\": \"B\", \"before_winner\": \"A\", \"fired\": true, \"first_choice\": \"A\", \"fixture\": \"lnh-bait-second-place-plurality\", \"method\": \"second-place-plurality\", \"silent\": false}\nrandom_irv_lnh_violations=0\nSUCCESS:CNL-0061-probe2 independent recount and later-no-harm both-states"
    }
  ],
  "evidence": [
    {
      "claim": "Elimination ties are resolved by lookback then lex-min, never RNG.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0061/irv_author.py:36",
      "mechanism": "author-source-constant",
      "snippet": "TIE_POLICY = \"lookback-then-lex-min-elim\"",
      "path": "command-center/p2-wave/probes/CNL-0061/irv_author.py",
      "line": 36
    },
    {
      "claim": "The 7-seat 3-option non-monotonicity fixture raises C on one ballot.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0061/fixtures.py:25",
      "mechanism": "on-disk-python-fixture-constant",
      "snippet": "NM7X3_RAISED_CANDIDATE = \"C\"",
      "path": "command-center/p2-wave/probes/CNL-0061/fixtures.py",
      "line": 25
    },
    {
      "claim": "Reviewer recount uses mutating rank queues, not the author's scan.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0061/irv_reviewer.py:4",
      "mechanism": "reviewer-source-docstring",
      "snippet": "Different mechanism from irv_author.py: each ballot is a mutable queue of",
      "path": "command-center/p2-wave/probes/CNL-0061/irv_reviewer.py",
      "line": 4
    },
    {
      "claim": "LNH checker vacuity bait is second-place plurality, not IRV.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0061/pathology.py:75",
      "mechanism": "pathology-detector-docstring",
      "snippet": "\"\"\"Planted non-council method that can violate later-no-harm.",
      "path": "command-center/p2-wave/probes/CNL-0061/pathology.py",
      "line": 75
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0061-probe2-reviewer-recount",
    "verdict": "PASS",
    "independent": true,
    "control_executed": true,
    "notes": "Named probe2 re-tabulates the JSON fixtures with irv_reviewer queues and re-runs majority / LNH both-states. Catalog asks for a mechanical recount, not agreement with the author's prose. Winner disagreement would have blocked emit."
  },
  "named_probes": [
    {
      "id": "probe1",
      "role": "non-monotonicity-worked-example",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0061/probe1_nonmonotonicity.py"
    },
    {
      "id": "probe2",
      "role": "independent-recount-and-later-no-harm",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0061/probe2_reviewer_recount.py"
    }
  ],
  "report": {
    "kind": "council-design-note",
    "observations": [
      {
        "name": "nm7x3-raise-C-flips-winner",
        "measured": "C->B",
        "method": "IRV-COUNCIL-v1 author tabulate on nm-7x3 JSON fixtures; raise C on one A>C>B ballot",
        "anchor": "command-center/p2-wave/probes/CNL-0061/fixtures.py:25"
      },
      {
        "name": "census-n7-raise-to-first-hits",
        "measured": 6,
        "method": "exhaustive 3-candidate raise-to-first search at roster 7",
        "anchor": "command-center/p2-wave/probes/CNL-0061/pathology.py:109"
      },
      {
        "name": "later-no-harm-under-irv",
        "measured": false,
        "method": "later_no_harm_check on truncated-then-completed IRV fixture",
        "anchor": "command-center/p2-wave/probes/CNL-0061/pathology.py:75"
      }
    ],
    "control_ids": [
      "NC-MAJORITY-7-SILENT",
      "NC-LNH-BAIT-FIRES"
    ]
  },
  "schema_note": "Catalog output_schema is a GENERATED SHIM whose $ref points at https://ast-integrate.invalid/...; jsonschema 4.10.3 RefResolver tries the network. G-1 does not require that hop. This unit validates against the per-unit schema. Overwriting the shared catalog schema would be a sibling rebuild circle.",
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0061-ranked-choice-tabulation-and-its-known-pathologies.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0061/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    }
  ],
  "regression_anchor": {
    "catalog_question": "What is the exact IRV tabulation procedure including elimination ties, and which pathologies (non-monotonicity, later-no-harm violation) can actually occur at council roster sizes of 3-15?",
    "harness_inputs_absent": {
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": true,
      "11-COUNCIL-SPECIFICATION.schema.json": true,
      "CNL-0023-artifact": true
    },
    "dependency_cnl_0023": "Listed dependency; artifact absent. Weight is an input with default 1.0. This unit does not invent provenance records."
  },
  "scope": {
    "executable_on": "in-probe fixtures and two independent IRV implementations; tools/council/vote/ballots.py is not on this tree",
    "does_not_claim": [
      "cloud ok=true is delivery",
      "global unit_manifest.py --write was run",
      "Windows harness-restore files were read on this host",
      "later-no-harm violations occur under IRV-COUNCIL-v1",
      "CNL-0023 provenance validator was executed",
      "ADV rebuild"
    ]
  },
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "cloud_ok": false,
  "min_bytes_threshold": 4096,
  "ts": "2026-08-25T00:55:57Z"
}
