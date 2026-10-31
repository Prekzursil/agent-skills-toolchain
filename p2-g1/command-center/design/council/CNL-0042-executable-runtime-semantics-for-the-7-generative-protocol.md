{
 "answer": "Across P26-P32 a generation round is a GENERATE-mode turn whose legal speech acts are the protocol's counting/generate set (emit_idea, sketch, fill_cell/emit_combination, apply_principle, green_hat_emit, relax_and_emit, emit_counterfactual). A critique round is a CRITIQUE-mode turn after the GENERATE_CLOSED gate, legal acts being score/cluster, pinup_critique, screen_combination, score_against_both_parameters, black_hat, restore_and_filter, actual_world_score. The separator is the mode token plus the speech-act whitelist, not a prompt that says 'do not criticise'. Critique cannot leak into generation because a CRITIQUE act in GENERATE fires leak_check (CRITIQUE_ACT_IN_GENERATE), GENERATE turns do not see the annotation store, and the idea bag is append-only: GENERATE_CLOSED snapshots the count and drop_idea fires IDEA_COUNT_SUPPRESSION. Idea count used for stopping is the snapshot, never the post-critique survivor set. P33 prediction-tournament (FORECASTING) is excluded so a family mis-assignment cannot inflate n. 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this tree; the ranging set is the catalog-named closed list the unit itself gives so no member falls through a family mis-assignment.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0042-executable-runtime-semantics-for-the-7-generative-protocol.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0042/runtime.py",
   "role": "supporting"
  }
 ],
 "both_states": {
  "fired_on_planted_bad": true,
  "known_good_verbatim": "{\"codes\": [], \"findings\": [], \"fired\": false, \"idea_count\": 5, \"record_id\": \"P26\", \"silent\": true}",
  "planted_bad_verbatim": "{\"codes\": [\"CRITIQUE_ACT_IN_GENERATE\", \"CRITIQUE_CONTEXT_IN_GENERATE\"], \"findings\": [{\"at\": \"P26:g1:1:score\", \"code\": \"CRITIQUE_CONTEXT_IN_GENERATE\", \"detail\": \"annotation store was visible to a GENERATE turn\"}, {\"at\": \"P26:g1:1:score\", \"code\": \"CRITIQUE_ACT_IN_GENERATE\", \"detail\": \"score is a CRITIQUE act inside GENERATE\"}], \"fired\": true, \"idea_count\": 2, \"record_id\": \"P26\", \"silent\": false}",
  "silent_on_known_good": true
 },
 "census": {
  "catalog_named": [
   {
    "id": "P26",
    "slug": "brainstorming-swarm"
   },
   {
    "id": "P27",
    "slug": "design-charrette"
   },
   {
    "id": "P28",
    "slug": "morphological-analysis"
   },
   {
    "id": "P29",
    "slug": "triz-contradiction"
   },
   {
    "id": "P30",
    "slug": "six-hats-rotation"
   },
   {
    "id": "P31",
    "slug": "constraint-relaxation"
   },
   {
    "id": "P32",
    "slug": "counterfactual-council"
   }
  ],
  "census_basis": "catalog-named-closed-set (PPJ absent)",
  "counts_agree": true,
  "decoy_excluded": [
   "P33"
  ],
  "expected_n": 7,
  "family": "GENERATIVE",
  "family_n": 7,
  "library": {
   "present": [],
   "tried": [
    {
     "path": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    },
    {
     "path": "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    },
    {
     "path": "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    }
   ]
  },
  "library_used_as_census": false,
  "record_ids": [
   "P26",
   "P27",
   "P28",
   "P29",
   "P30",
   "P31",
   "P32"
  ],
  "roster_ids": [
   "P26",
   "P27",
   "P28",
   "P29",
   "P30",
   "P31",
   "P32"
  ]
 },
 "claim_under_test": "GENERATE vs CRITIQUE is a mode token plus speech-act whitelist; critique acts in GENERATE fire; the idea-count snapshot at GENERATE_CLOSED cannot be decremented by critique.",
 "cloud_ok": false,
 "detector": {
  "id": "CNL-0042-mode-whitelist-and-frozen-bag",
  "pair_and_gate_rejected": true,
  "signals": [
   {
    "id": "S1-mode-token-plus-act-whitelist",
    "mechanism": "Round.mode GENERATE|CRITIQUE plus per-protocol speech-act sets; CRITIQUE acts in GENERATE fire CRITIQUE_ACT_IN_GENERATE.",
    "role": "separate-generate-from-critique"
   },
   {
    "id": "S2-frozen-idea-bag",
    "mechanism": "GENERATE_CLOSED snapshots bag length; drop_idea fires IDEA_COUNT_SUPPRESSION; stopping uses the snapshot not post-critique survivors.",
    "role": "stop-count-suppression"
   }
  ],
  "stopping_bind": "Stopping and idea-count bind to the GENERATE_CLOSED snapshot only. A conjunction of 'some green hat AND no black hat' is rejected as a stopping rule (pair_and_gate_rejected)."
 },
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0042.question_or_target",
   "claim": "Catalog-named GENERATIVE closed set is P26-P32 (n=7)",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "library_absent_on_this_tree; census.library.present=[]",
   "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json was read and family=GENERATIVE counted n=7",
   "verdict": "REFUTED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0042/schedules.py:good_schedule",
   "claim": "Each of 7 records has an executable GENERATE/gate/CRITIQUE schedule",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0042/runtime.py:leak_check",
   "claim": "Leak check FIRES on planted-bad and is SILENT on known-good",
   "verdict": "CONFIRMED"
  }
 ],
 "negative_control": {
  "state_meant_to_reject": "CRITIQUE speech act (score) inside a GENERATE round of P26",
  "verbatim": "{\"codes\": [\"CRITIQUE_ACT_IN_GENERATE\", \"CRITIQUE_CONTEXT_IN_GENERATE\"], \"findings\": [{\"at\": \"P26:g1:1:score\", \"code\": \"CRITIQUE_CONTEXT_IN_GENERATE\", \"detail\": \"annotation store was visible to a GENERATE turn\"}, {\"at\": \"P26:g1:1:score\", \"code\": \"CRITIQUE_ACT_IN_GENERATE\", \"detail\": \"score is a CRITIQUE act inside GENERATE\"}], \"fired\": true, \"idea_count\": 2, \"record_id\": \"P26\", \"silent\": false}",
  "what_the_check_does": "FIRES. codes include CRITIQUE_ACT_IN_GENERATE."
 },
 "negative_controls": [
  {
   "id": "NC-critique-in-generate",
   "state_rejected": "CRITIQUE speech act inside a GENERATE round",
   "verbatim": {
    "codes": [
     "CRITIQUE_ACT_IN_GENERATE",
     "CRITIQUE_CONTEXT_IN_GENERATE"
    ],
    "findings": [
     {
      "at": "P26:g1:1:score",
      "code": "CRITIQUE_CONTEXT_IN_GENERATE",
      "detail": "annotation store was visible to a GENERATE turn"
     },
     {
      "at": "P26:g1:1:score",
      "code": "CRITIQUE_ACT_IN_GENERATE",
      "detail": "score is a CRITIQUE act inside GENERATE"
     }
    ],
    "fired": true,
    "idea_count": 2,
    "record_id": "P26",
    "silent": false
   },
   "what_the_check_does": "FIRES. codes include CRITIQUE_ACT_IN_GENERATE. Recorded verbatim from runtime.leak_check on P26 planted-bad."
  },
  {
   "id": "NC-family-misassignment",
   "state_rejected": "FORECASTING P33 counted as GENERATIVE",
   "what_the_check_does": "P33 is absent from catalog-named and roster generative sets"
  }
 ],
 "notes": "G-1 CNL-0042: live named probes, honest SUCCESS, per-unit manifest. Did not run unit_manifest.py --write. PPJ library absent; no overclaim that family=GENERATIVE was counted from that file.",
 "per_record": [
  {
   "counting_acts": [
    "emit_idea"
   ],
   "critique_acts": [
    "score",
    "cluster"
   ],
   "generate_acts": [
    "emit_idea",
    "pass"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = bag length at GENERATE_CLOSED. Critique writes annotations only; drop_idea is a leak.",
   "leak_stop": "Speech-act whitelist plus a frozen idea bag. Generators never receive the annotation store as context, so scores cannot suppress further emits.",
   "mechanical_separator": "Round.mode is GENERATE until GENERATE_CLOSED; only emit_idea/pass are legal. score/cluster are CRITIQUE acts and cannot occupy a GENERATE turn.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P26",
   "slug": "brainstorming-swarm",
   "turn_schedule": {
    "id": "P26-good",
    "kind": "known-good",
    "record_id": "P26",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_idea",
        "body": "P26-a-1"
       },
       {
        "act": "emit_idea",
        "body": "P26-a-2"
       },
       {
        "act": "emit_idea",
        "body": "P26-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_idea",
        "body": "P26-b-1"
       },
       {
        "act": "emit_idea",
        "body": "P26-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "score",
        "target": "P26-1"
       },
       {
        "act": "score",
        "target": "P26-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "sketch"
   ],
   "critique_acts": [
    "pinup_critique"
   ],
   "generate_acts": [
    "sketch",
    "pass"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = sketch emits at GENERATE_CLOSED.",
   "leak_stop": "pinup_critique is illegal while studio.mode=GENERATE. Idea count is sketches at the studio close, not survivors of pin-up.",
   "mechanical_separator": "Studio rounds are GENERATE (sketch). Pin-up is a distinct CRITIQUE round whose role is unbound until GENERATE_CLOSED.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P27",
   "slug": "design-charrette",
   "turn_schedule": {
    "id": "P27-good",
    "kind": "known-good",
    "record_id": "P27",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "sketch",
        "body": "P27-a-1"
       },
       {
        "act": "sketch",
        "body": "P27-a-2"
       },
       {
        "act": "sketch",
        "body": "P27-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "sketch",
        "body": "P27-b-1"
       },
       {
        "act": "sketch",
        "body": "P27-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "pinup_critique",
        "target": "P27-1"
       },
       {
        "act": "pinup_critique",
        "target": "P27-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "emit_combination"
   ],
   "critique_acts": [
    "screen_combination"
   ],
   "generate_acts": [
    "fill_cell",
    "emit_combination"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = combinations emitted before GENERATE_CLOSED, not post-screen survivors.",
   "leak_stop": "screen_combination is illegal before GENERATE_CLOSED. Screening cannot decrement the combination bag.",
   "mechanical_separator": "Box fill and combination emit are GENERATE. Consistency screening is CRITIQUE and cannot mark a cell invalid during fill.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P28",
   "slug": "morphological-analysis",
   "turn_schedule": {
    "id": "P28-good",
    "kind": "known-good",
    "record_id": "P28",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_combination",
        "body": "P28-a-1"
       },
       {
        "act": "emit_combination",
        "body": "P28-a-2"
       },
       {
        "act": "emit_combination",
        "body": "P28-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_combination",
        "body": "P28-b-1"
       },
       {
        "act": "emit_combination",
        "body": "P28-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "screen_combination",
        "target": "P28-1"
       },
       {
        "act": "screen_combination",
        "target": "P28-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "apply_principle"
   ],
   "critique_acts": [
    "score_against_both_parameters"
   ],
   "generate_acts": [
    "apply_principle"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = apply_principle emits at GENERATE_CLOSED.",
   "leak_stop": "score_against_both_parameters cannot share a GENERATE turn with apply_principle. Feasibility scoring is not an input to later GENERATE turns.",
   "mechanical_separator": "Inventive-principle application emits solutions (GENERATE). Dual-parameter scoring is CRITIQUE.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P29",
   "slug": "triz-contradiction",
   "turn_schedule": {
    "id": "P29-good",
    "kind": "known-good",
    "record_id": "P29",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "apply_principle",
        "body": "P29-a-1"
       },
       {
        "act": "apply_principle",
        "body": "P29-a-2"
       },
       {
        "act": "apply_principle",
        "body": "P29-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "apply_principle",
        "body": "P29-b-1"
       },
       {
        "act": "apply_principle",
        "body": "P29-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "score_against_both_parameters",
        "target": "P29-1"
       },
       {
        "act": "score_against_both_parameters",
        "target": "P29-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "green_hat_emit"
   ],
   "critique_acts": [
    "black_hat"
   ],
   "generate_acts": [
    "green_hat_emit"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = green_hat_emit at GENERATE_CLOSED.",
   "leak_stop": "black_hat speech acts are illegal under a green hat token. Idea count ignores black-hat kills.",
   "mechanical_separator": "Hat token IS the mode. Only green_hat_emit increments the idea bag. black_hat is CRITIQUE. white/red/yellow/blue are PROCESS and do not count.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P30",
   "slug": "six-hats-rotation",
   "turn_schedule": {
    "id": "P30-good",
    "kind": "known-good",
    "record_id": "P30",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "green_hat_emit",
        "body": "P30-a-1"
       },
       {
        "act": "green_hat_emit",
        "body": "P30-a-2"
       },
       {
        "act": "green_hat_emit",
        "body": "P30-a-3"
       }
      ]
     },
     {
      "id": "white",
      "mode": "PROCESS",
      "turns": [
       {
        "act": "white_hat",
        "body": "facts-only"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "green_hat_emit",
        "body": "P30-b-1"
       },
       {
        "act": "green_hat_emit",
        "body": "P30-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "black_hat",
        "target": "P30-1"
       },
       {
        "act": "black_hat",
        "target": "P30-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "relax_and_emit"
   ],
   "critique_acts": [
    "restore_and_filter"
   ],
   "generate_acts": [
    "relax_and_emit"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = relax_and_emit at GENERATE_CLOSED, before C_full is restored.",
   "leak_stop": "restore_and_filter is illegal while the relaxed store is live. Filter cannot pop the relaxed bag.",
   "mechanical_separator": "GENERATE evaluates against C_relaxed. CRITIQUE restores C_full and filters. The two constraint sets are different stores.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P31",
   "slug": "constraint-relaxation",
   "turn_schedule": {
    "id": "P31-good",
    "kind": "known-good",
    "record_id": "P31",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "relax_and_emit",
        "body": "P31-a-1"
       },
       {
        "act": "relax_and_emit",
        "body": "P31-a-2"
       },
       {
        "act": "relax_and_emit",
        "body": "P31-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "relax_and_emit",
        "body": "P31-b-1"
       },
       {
        "act": "relax_and_emit",
        "body": "P31-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "restore_and_filter",
        "target": "P31-1"
       },
       {
        "act": "restore_and_filter",
        "target": "P31-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  },
  {
   "counting_acts": [
    "emit_counterfactual"
   ],
   "critique_acts": [
    "actual_world_score"
   ],
   "generate_acts": [
    "emit_counterfactual"
   ],
   "good_run": {
    "annotation_n": 2,
    "idea_count": 5,
    "silent": true
   },
   "idea_count_rule": "Count = counterfactual emits at GENERATE_CLOSED.",
   "leak_stop": "actual_world_score cannot run in GENERATE. Actual-world feasibility is not GENERATE context.",
   "mechanical_separator": "Counterfactual emits live in an alternate-world namespace (GENERATE). actual_world_score is CRITIQUE against the real-world store.",
   "missing_element": null,
   "phase_gate": "GENERATE_CLOSED",
   "record_id": "P32",
   "slug": "counterfactual-council",
   "turn_schedule": {
    "id": "P32-good",
    "kind": "known-good",
    "record_id": "P32",
    "rounds": [
     {
      "id": "g1",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_counterfactual",
        "body": "P32-a-1"
       },
       {
        "act": "emit_counterfactual",
        "body": "P32-a-2"
       },
       {
        "act": "emit_counterfactual",
        "body": "P32-a-3"
       }
      ]
     },
     {
      "id": "g2",
      "mode": "GENERATE",
      "turns": [
       {
        "act": "emit_counterfactual",
        "body": "P32-b-1"
       },
       {
        "act": "emit_counterfactual",
        "body": "P32-b-2"
       }
      ]
     },
     {
      "id": "gate",
      "mode": "GENERATE_CLOSED",
      "turns": []
     },
     {
      "id": "c1",
      "mode": "CRITIQUE",
      "turns": [
       {
        "act": "actual_world_score",
        "target": "P32-1"
       },
       {
        "act": "actual_world_score",
        "target": "P32-2"
       }
      ]
     }
    ]
   },
   "verdict": "EXECUTABLE"
  }
 ],
 "planted_mutant_control": {
  "per_class_recall": [
   {
    "caught": 7,
    "class": "critique-act-in-generate",
    "planted": 7,
    "recall": 1.0,
    "scope": "planted"
   },
   {
    "caught": 7,
    "class": "critique-context-in-generate",
    "planted": 7,
    "recall": 1.0,
    "scope": "planted"
   },
   {
    "caught": 7,
    "class": "drop-idea-count-suppression",
    "planted": 7,
    "recall": 1.0,
    "scope": "planted"
   },
   {
    "caught": 7,
    "class": "critique-before-generate-closed",
    "planted": 7,
    "recall": 1.0,
    "scope": "planted"
   }
  ],
  "scope": "Four leak/suppression mutant classes planted on all 7 GENERATIVE records. Unplanted classes are NOT-CHECKED.",
  "unplanted_classes": [
   "stylometric-identity-leak",
   "lexical-near-duplicate-idea-gaming"
  ]
 },
 "question": "Ranging over exactly these 7 records, named so no member can fall through a family mis-assignment (P26 brainstorming-swarm, P27 design-charrette, P28 morphological-analysis, P29 triz-contradiction, P30 six-hats-rotation, P31 constraint-relaxation, P32 counterfactual-council): For each of the 7 GENERATIVE protocol records, what separates a generation round from a critique round mechanically, and what stops critique from leaking into generation and suppressing the idea count?",
 "reviewer": {
  "independent": true,
  "method": "Re-parses catalog question_or_target with PID regex; re-tabulates roster family=GENERATIVE; re-runs leak_check. Does not read answer prose.",
  "recount_agrees": true,
  "reviewer_id": "CNL-0042-probe2-independent-recount",
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0042",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0042/probe1_family_schedules.py",
   "id": "T1-seven-executable-schedules",
   "observation": "7/7 records EXECUTABLE; family_n=7; P33 excluded",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0042/probe2_both_states.py",
   "id": "T2-both-states-leak-check",
   "observation": "FIRES on planted critique-in-generate; SILENT on known-good",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0042/probe2_both_states.py",
   "id": "T3-negative-control-verbatim",
   "observation": "On P26 GENERATE turn with act=score the check FIRES with CRITIQUE_ACT_IN_GENERATE (and CRITIQUE_CONTEXT_IN_GENERATE).",
   "result": "PASS"
  }
 ],
 "title": "Executable runtime semantics for the 7 GENERATIVE protocols",
 "ts": "2026-08-25T00:52:47Z",
 "unit_id": "CNL-0042"
}
