{
  "answer": "Votes of a dead seat stay on the ledger under the dead seat_id. The replacement is a new seat_id and starts with zero ballots for every round it did not attend; in-flight turns are VOID, never inherited. Ideas stay attributed to originator_seat_id \u2014 the replacement may cite them after catch-up but does not become author. The council always reaches a named terminal state (REPLACED-AND-CONTINUED, DEGRADED-NO-REPLACEMENT, or ABORTED-QUORUM) inside MAX_STEPS; a hang is a detector failure, not an allowed outcome. Separately, CONFIG-side independence groups living and declared seats by canonical_model (date stamps and vendor prefixes stripped; gpt-4o != gpt-4.1). Role labels, seat ids, vendor strings, and declared_independent are not grouping keys. Same canonical model is DUPLICATE-INDEPENDENCE even across vendors; a genuinely different pair is silent; a missing model is UNATTESTED (fail-closed, not a fabricated pair). Response-side attestation (transport, endpoint, reported model, context digest) is ADV-0136, not this unit.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0021-participant-replacement-and-duplicate-independence-detecti.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0021/council-design-note.schema.json",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0021/runtime.py",
      "role": "supporting"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0021/reviewer.py",
      "role": "supporting"
    }
  ],
  "catalog_anchor": "command-center/WORK-UNIT-CATALOG.json:35348",
  "claims": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:262",
      "claim": "A mid-round death reaches REPLACED-AND-CONTINUED (or DEGRADED/ABORTED), never HUNG, inside MAX_STEPS.",
      "id": "C1",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:179",
      "claim": "Replacement ballots do not include rounds the dead seat attended (inherited=0 on the honest fixture; the inherit mutant is non-zero).",
      "id": "C2",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:125",
      "claim": "Same canonical model under two role labels is DUPLICATE-INDEPENDENCE; a genuinely different pair is not flagged; a role-label checker misses the collusion.",
      "id": "C3",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:48",
      "claim": "canonical_model does not collapse gpt-4o into gpt-4.1.",
      "id": "C4",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/reviewer.py:20",
      "claim": "An independent pairwise recount agrees with the grouping detector on pair counts.",
      "id": "C5",
      "verdict": "CONFIRMED"
    }
  ],
  "completion_sentinel": "SUCCESS:CNL-0021",
  "duplicate_independence": {
    "fail_closed": "empty or unknown model => UNATTESTED; that seat cannot count as independent evidence",
    "fires_on": "two or more seats sharing canonical_model after date-stamp and vendor-prefix strip",
    "grouping_key": "canonical_model(model)",
    "ignored_as_keys": [
      "role",
      "seat_id",
      "vendor",
      "declared_independent"
    ],
    "side": "CONFIG",
    "silent_on": "canonical_model values that differ, including gpt-4o versus gpt-4.1",
    "split_with_ADV_0136": "ADV-0136 attests response-side (vendor+model+context digest+transport). This unit never reads transport logs."
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:262",
      "claim": "Honest mid-round death is REPLACED-AND-CONTINUED with inherited=0; hang mutant is HUNG; inherit mutant inherited>=1.",
      "signal_1": {
        "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:262",
        "kind": "file:line",
        "mechanism": "bounded step machine in runtime.step / runtime.run"
      },
      "signal_2": {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py",
        "kind": "command",
        "mechanism": "probe1 live fixture run (event-log walk + inherited_ballots filter)",
        "verbatim_expect": "midround_defined_state=True hang_mutant_fires=True inheritance_mutant_fires=True"
      },
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:125",
      "claim": "Same-base-model pair fires; genuinely different pair is silent (both directions). Pairwise recount agrees with grouping.",
      "signal_1": {
        "anchor": "command-center/p2-wave/probes/CNL-0021/runtime.py:125",
        "kind": "file:line",
        "mechanism": "defaultdict grouping by canonical_model in duplicate_pairs",
        "verbatim": [
          {
            "code": "DUPLICATE-INDEPENDENCE",
            "detail": "canonical_model=claude-opus-4 shared by 2 seats",
            "seats": [
              "s-arch",
              "s-skep"
            ]
          }
        ]
      },
      "signal_2": {
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe2_reviewer_recount.py",
        "kind": "command",
        "mechanism": "nested pairwise comparison in reviewer.pairwise_duplicate_seat_ids (not groupby)",
        "verbatim_expect": "pairwise_same=[('s-arch', 's-skep')] pairwise_different=[]"
      },
      "verdict": "CONFIRMED"
    }
  ],
  "measured": {
    "aborted_status": "ABORTED-QUORUM",
    "cross_vendor_same_model_pairs": [
      [
        "s-az",
        "s-oa"
      ]
    ],
    "degraded_status": "DEGRADED-NO-REPLACEMENT",
    "different_pair_count": 0,
    "gpt4o_vs_gpt41_pairs": [],
    "hang_mutant_status": "HUNG",
    "honest_dead_ballots": 1,
    "honest_inherited": 0,
    "honest_replacement_ballots": 1,
    "honest_status": "REPLACED-AND-CONTINUED",
    "honest_steps": 10,
    "inherit_mutant_inherited": 1,
    "max_steps": 64,
    "role_checker_findings_on_collusion": 0,
    "same_base_pair_count": 1,
    "unattested_seats": [
      "s-ghost"
    ]
  },
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py",
      "id": "probe1",
      "role": "mid-round-death-and-both-direction-independence"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe2_reviewer_recount.py",
      "id": "probe2",
      "role": "independent-pairwise-recount"
    }
  ],
  "negative_controls": [
    {
      "check_does": "fires DUPLICATE-INDEPENDENCE; a role-label checker is silent on the same fixture",
      "id": "NC-duplicate-independence",
      "reject_state": "two seats, same canonical_model (claude-opus-4 and claude-opus-4-20250514), different roles, both declared_independent",
      "verbatim": "{\"code\": \"DUPLICATE-INDEPENDENCE\", \"detail\": \"canonical_model=claude-opus-4 shared by 2 seats\", \"seats\": [\"s-arch\", \"s-skep\"]}"
    },
    {
      "check_does": "inherited_ballots count is >0 (honest fixture is 0)",
      "id": "NC-vote-inheritance",
      "reject_state": "replacement copies the dead seat's historical ballots onto the new seat_id",
      "verbatim": "{\"honest_inherited\": 0, \"mutant_inherited\": 1}"
    },
    {
      "check_does": "status becomes HUNG at MAX_STEPS; honest run is REPLACED-AND-CONTINUED",
      "id": "NC-hang",
      "reject_state": "step machine waits on a dead seat without seating or degrading",
      "verbatim": "{\"hang_mutant\": \"HUNG\", \"honest\": \"REPLACED-AND-CONTINUED\", \"max_steps\": 64}"
    }
  ],
  "not_checked": [
    {
      "claim": "Field-by-field citation of $defs.seat in 11-COUNCIL-SPECIFICATION.schema.json",
      "reason": "The four catalog input paths from harness-restore-20260806 are not on this worktree (missing=['C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md', 'C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json', 'C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json', '/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md']). Citing unread schema fields would be overclaim."
    },
    {
      "claim": "Behaviour of a live multi-vendor LLM council under this protocol",
      "reason": "This unit ships a deterministic step machine and fixtures, not a live model dispatch."
    },
    {
      "claim": "Response-side SAME-TUPLE / DECLARED-ONLY / DRIVER-CONFOUND",
      "reason": "Those are ADV-0136 runtime attestation checks; this unit is the CONFIG-side half."
    },
    {
      "claim": "CNL-0005 nine-dial descriptor and CNL-0020 catch-up briefing artifacts",
      "reason": "Those dependency artifacts are not on this worktree; replacement reuses the catalog questions (new seat_id, role mandate, no majority-anchored first vote) without claiming their units delivered."
    },
    {
      "claim": "Instance validation against the catalog-declared shared command-center/schema/council-design-note.schema.json",
      "reason": "That shared file is contested: a sibling CNL-0030 worker required chair/flat size_sweep fields that are not this unit's question. This artifact validates against the per-unit copy at command-center/p2-wave/probes/CNL-0021/council-design-note.schema.json (same pattern as CNL-0012). Overwriting the shared schema would be a rebuild circle."
    }
  ],
  "output_schema": "command-center/schema/council-design-note.schema.json",
  "question": "When a seat dies or is replaced mid-council, what happens to its votes and its ideas - and separately, how does the runtime detect that two nominally different seats are the same base model and therefore not independent evidence?",
  "replacement_protocol": {
    "hang_is": "status=HUNG after MAX_STEPS with no honest terminal; the honest machine must not emit it",
    "ideas": "remain attributed to originator_seat_id; replacement may cite, never rewrite authorship",
    "max_steps": 64,
    "role_mandate": "replacement receives the departed seat's role, not its votes or its seat_id",
    "seat_id_reuse": "forbidden",
    "terminal_states": [
      "ABORTED-QUORUM",
      "COMPLETE",
      "DEGRADED-NO-REPLACEMENT",
      "REPLACED-AND-CONTINUED"
    ],
    "votes": "remain attributed to origin_seat_id; replacement ballot count starts at zero for rounds it did not attend; in-flight vote of the dying seat is VOID"
  },
  "reviewer": {
    "anchor": "command-center/p2-wave/probes/CNL-0021/reviewer.py:20",
    "independent": true,
    "mechanism": "reviewer.py nested pairwise canonical_model comparison plus ballot table keyed by (round_id, seat_id, option); does not read the author's claims[]",
    "recount_agrees": true,
    "reviewer_id": "CNL-0021-probe2-pairwise-recount",
    "role_mutant_control": "command-center/p2-wave/probes/CNL-0021/runtime.py:160",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0021",
  "source_unavailable": [
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md"
  ],
  "state": "SUCCESS",
  "strongest_surviving_counterargument": "Azure OpenAI gpt-4o and OpenAI gpt-4o may differ in routing and safety filters, so a vendor-aware auditor might want them as weak-independent. CONFIG-side this unit still flags them: they share a canonical_model, so they are not independent evidence of that model's distribution. ADV-0136 can still distinguish the vendor endpoints on the response side.",
  "tests": [
    {
      "catalog": "a mid-round death fixture: the council must reach a defined state, not hang",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py",
      "id": "T1-midround-death-defined-state",
      "observed": {
        "aborted": "ABORTED-QUORUM",
        "degraded": "DEGRADED-NO-REPLACEMENT",
        "hang_mutant": "HUNG",
        "honest": "REPLACED-AND-CONTINUED"
      },
      "result": "PASS"
    },
    {
      "catalog": "a same-base-model pair must be detected; a genuinely different pair must NOT be flagged (both directions)",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py",
      "id": "T2-same-and-different-base-model",
      "observed": {
        "cross_vendor_same_model": [
          [
            "s-az",
            "s-oa"
          ]
        ],
        "different_pairs": [],
        "gpt4o_vs_gpt41": [],
        "role_checker_on_collusion": 0,
        "same_pairs": [
          [
            "s-arch",
            "s-skep"
          ]
        ]
      },
      "result": "PASS"
    },
    {
      "catalog": "negative control recorded verbatim: state what the check does on the state it is meant to reject",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0021/probe1_midround_death_and_duplicate.py",
      "id": "T3-negative-control-recorded-verbatim",
      "observed": {
        "check_does": "emits DUPLICATE-INDEPENDENCE over those seat ids",
        "reject_state": "same-base-model pair with distinct role labels and declared_independent=true",
        "silent_on_genuinely_different_verbatim": "[]",
        "verbatim": "{\"code\": \"DUPLICATE-INDEPENDENCE\", \"detail\": \"canonical_model=claude-opus-4 shared by 2 seats\", \"seats\": [\"s-arch\", \"s-skep\"]}"
      },
      "result": "PASS"
    }
  ],
  "title": "Participant replacement and duplicate-independence detection",
  "unit_id": "CNL-0021",
  "validated_schema": "command-center/p2-wave/probes/CNL-0021/council-design-note.schema.json"
}
