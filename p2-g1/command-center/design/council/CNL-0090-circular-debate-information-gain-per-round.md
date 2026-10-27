{
 "answer": "G_t = |new claims| + |new evidence|. Newness requires unseen claim_id AND text that is not a token-Jaccard>=0.85 or char-4gram>=0.35 duplicate. Circling threshold: G_t < 1 for 2 consecutive rounds. Planted loop fires at round 3; productive and refinement stay silent; false_positive_rate=0.0. SUCCESS:CNL-0090",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0090-circular-debate-information-gain-per-round.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-detector-spec.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0090/detector.py",
   "role": "mechanism"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0090/probe1_both_states.py",
   "role": "named-probe"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0090/probe2_independent_gain.py",
   "role": "named-probe"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0090/artifact.schema.json",
   "role": "schema"
  }
 ],
 "both_states": {
  "detector_control_first": true,
  "known_good": {
   "fixture": "command-center/p2-wave/probes/CNL-0090/fixtures/clean_productive.json",
   "silent": true,
   "verbatim": "known-good-productive fixture=clean_productive.json fired=False silent=True fired_at=None curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-drop', 'C-backpressure'], 'new_evidence_ids': ['E-overflow-2', 'E-block-2'], 'consecutive_subfloor': 0}, {'round': 3, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-single-writer', 'C-shard'], 'new_evidence_ids': ['E-aba-3', 'E-shard-3'], 'consecutive_subfloor': 0}, {'round': 4, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-model-check', 'C-litmus'], 'new_evidence_ids': ['E-tla-4', 'E-litmus-4'], 'consecutive_subfloor': 0}]"
  },
  "planted_bad": {
   "fired": true,
   "fired_at_round": 3,
   "fixture": "command-center/p2-wave/probes/CNL-0090/fixtures/planted_loop.json",
   "verbatim": "detector-control-known-present fixture=planted_loop.json fired=True silent=False fired_at=3 curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 1}, {'round': 3, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 2}, {'round': 4, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 3}]"
  },
  "probe1_summary": "fired_on_bad=True silent_on_good=True detector_control_first=True false_positive_rate=0.0"
 },
 "claim_under_test": "G_t is the count of new claims plus new evidence nodes in round t. A claim is new only when its claim_id is unseen and its text is not a token-Jaccard or char-4gram duplicate of a prior claim. Circling is G_t < 1 for 2 consecutive rounds. Paraphrase with new ids still fires; refinement that adds evidence without new claims stays silent.",
 "completion_sentinel": "SUCCESS:CNL-0090",
 "dependency_cnl_0051": "CNL-0051 is not delivered on this tree. canonicalize.py is the local anti-gaming core this detector actually executes; it does not close the full-rewrite class.",
 "detector_id": "council.antifail.circular-debate.information-gain",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/detector.py:4",
   "claim": "Information units are new claims plus new evidence, not round count.",
   "line": 4,
   "path": "command-center/p2-wave/probes/CNL-0090/detector.py",
   "snippet": "G_t = |new claims| + |new evidence nodes|"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/detector.py:27",
   "claim": "The circling floor is one information unit: G_t < 1 is subfloor.",
   "line": 27,
   "path": "command-center/p2-wave/probes/CNL-0090/detector.py",
   "snippet": "FLOOR = 1"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/detector.py:28",
   "claim": "Circling fires after two consecutive subfloor rounds.",
   "line": 28,
   "path": "command-center/p2-wave/probes/CNL-0090/detector.py",
   "snippet": "WINDOW = 2"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/canonicalize.py:41",
   "claim": "Char-4gram Jaccard >= 0.35 corroborates paraphrase as the same claim.",
   "line": 41,
   "path": "command-center/p2-wave/probes/CNL-0090/canonicalize.py",
   "snippet": "CHAR4_DUP = 0.35"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/fixtures/planted_loop.json:2",
   "claim": "Detector-control known-present instance is the verbatim looping council.",
   "line": 2,
   "path": "command-center/p2-wave/probes/CNL-0090/fixtures/planted_loop.json",
   "snippet": "\"id\": \"planted-loop-verbatim\""
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0090/fixtures/clean_refinement.json:2",
   "claim": "Negative-control sibling: new evidence without new claims must stay silent.",
   "line": 2,
   "path": "command-center/p2-wave/probes/CNL-0090/fixtures/clean_refinement.json",
   "snippet": "\"id\": \"clean-refinement-new-evidence\""
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:38786",
   "claim": "Catalog question this spec answers.",
   "line": 38786,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "How is per-round information gain computed, and what gain threshold means the debate is circling rather than converging?"
  }
 ],
 "false_positive_denominator": 2,
 "false_positive_numerator": 0,
 "false_positive_rate": 0.0,
 "gain_curves": {
  "detector": {
   "loop": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-ring",
      "C-mutex"
     ],
     "new_evidence_ids": [
      "E-trace-1",
      "E-lat-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 2,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 3,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 4,
     "subfloor": true
    }
   ],
   "paraphrase": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-ring",
      "C-mutex"
     ],
     "new_evidence_ids": [
      "E-trace-1",
      "E-lat-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 2,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 3,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 4,
     "subfloor": true
    }
   ],
   "productive": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-ring",
      "C-mutex"
     ],
     "new_evidence_ids": [
      "E-trace-1",
      "E-lat-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-drop",
      "C-backpressure"
     ],
     "new_evidence_ids": [
      "E-overflow-2",
      "E-block-2"
     ],
     "round": 2,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-single-writer",
      "C-shard"
     ],
     "new_evidence_ids": [
      "E-aba-3",
      "E-shard-3"
     ],
     "round": 3,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-model-check",
      "C-litmus"
     ],
     "new_evidence_ids": [
      "E-tla-4",
      "E-litmus-4"
     ],
     "round": 4,
     "subfloor": false
    }
   ],
   "refinement": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-ring",
      "C-mutex"
     ],
     "new_evidence_ids": [
      "E-trace-1",
      "E-lat-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-lost-0",
      "E-p99-2"
     ],
     "round": 2,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-reorder-3",
      "E-starve-3"
     ],
     "round": 3,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-cpu-4",
      "E-tail-4"
     ],
     "round": 4,
     "subfloor": false
    }
   ]
  },
  "id_set_only": {
   "loop": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-mutex",
      "C-ring"
     ],
     "new_evidence_ids": [
      "E-lat-1",
      "E-trace-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 2,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 3,
     "subfloor": true
    },
    {
     "information_units": 0,
     "new_claim_ids": [],
     "new_evidence_ids": [],
     "round": 4,
     "subfloor": true
    }
   ],
   "paraphrase": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-mutex",
      "C-ring"
     ],
     "new_evidence_ids": [
      "E-lat-1",
      "E-trace-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [
      "C-mutex-v2",
      "C-ring-v2"
     ],
     "new_evidence_ids": [],
     "round": 2,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [
      "C-mutex-v3",
      "C-ring-v3"
     ],
     "new_evidence_ids": [],
     "round": 3,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [
      "C-mutex-v4",
      "C-ring-v4"
     ],
     "new_evidence_ids": [],
     "round": 4,
     "subfloor": false
    }
   ],
   "productive": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-mutex",
      "C-ring"
     ],
     "new_evidence_ids": [
      "E-lat-1",
      "E-trace-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-backpressure",
      "C-drop"
     ],
     "new_evidence_ids": [
      "E-block-2",
      "E-overflow-2"
     ],
     "round": 2,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-shard",
      "C-single-writer"
     ],
     "new_evidence_ids": [
      "E-aba-3",
      "E-shard-3"
     ],
     "round": 3,
     "subfloor": false
    },
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-litmus",
      "C-model-check"
     ],
     "new_evidence_ids": [
      "E-litmus-4",
      "E-tla-4"
     ],
     "round": 4,
     "subfloor": false
    }
   ],
   "refinement": [
    {
     "information_units": 4,
     "new_claim_ids": [
      "C-mutex",
      "C-ring"
     ],
     "new_evidence_ids": [
      "E-lat-1",
      "E-trace-1"
     ],
     "round": 1,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-lost-0",
      "E-p99-2"
     ],
     "round": 2,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-reorder-3",
      "E-starve-3"
     ],
     "round": 3,
     "subfloor": false
    },
    {
     "information_units": 2,
     "new_claim_ids": [],
     "new_evidence_ids": [
      "E-cpu-4",
      "E-tail-4"
     ],
     "round": 4,
     "subfloor": false
    }
   ]
  },
  "paraphrase_divergence": {
   "detector_fired": true,
   "detector_units": [
    4,
    0,
    0,
    0
   ],
   "id_set_fired": false,
   "id_set_units": [
    4,
    2,
    2,
    2
   ],
   "note": "Id-set-only stays SILENT on paraphrase because new claim_ids look like gain. The detector FIREs because text corroboration zeros G_t and no new evidence arrives."
  },
  "refinement_discrimination": {
   "detector_fired": false,
   "note": "Rounds 2-4 add evidence and no new claims. G_t stays at 2, above the floor, so careful refinement is not circling.",
   "units": [
    4,
    2,
    2,
    2
   ]
  }
 },
 "mechanism": {
  "information_units": "G_t = |new_claims| + |new_evidence|",
  "signals": [
   {
    "id": "signal-1-structured-ids",
    "reads": "set difference of claim_id and evidence_id against the union of all prior rounds"
   },
   {
    "id": "signal-2-text-corroboration",
    "reads": "token Jaccard >= 0.85 or char-4gram Jaccard >= 0.35 against prior claim_text; either hit marks the claim as not-new even when claim_id is fresh"
   }
  ],
  "summary": "Per-round information gain G_t counts semantically new claims plus new evidence nodes. Structured claim_id identity is signal 1; token Jaccard and char-4gram Jaccard on claim_text are signal 2. A claim is new only if both signals agree it is unseen. Vote motion and Shannon entropy of position_id are diagnostic traces and do not enter G_t.",
  "why_entropy_is_diagnostic": "Entropy collapse without new claims or evidence is premature convergence (IMP-0323). Copy-paste agreement with G_t = 0 still fires here because nothing new was said.",
  "why_votes_are_diagnostic": "Two camps can twitch position labels while restating the same slogans. Counting vote_changes inside G_t would let slogan-swap look like information."
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0090/probe1_both_states.py",
   "exit_code": 0,
   "id": "probe1",
   "raw_output": "detector-control-known-present fixture=planted_loop.json fired=True silent=False fired_at=3 curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 1}, {'round': 3, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 2}, {'round': 4, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 3}]\nplanted-paraphrase fixture=planted_paraphrase.json fired=True silent=False fired_at=3 curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 1}, {'round': 3, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 2}, {'round': 4, 'information_units': 0, 'subfloor': True, 'new_claim_ids': [], 'new_evidence_ids': [], 'consecutive_subfloor': 3}]\nknown-good-productive fixture=clean_productive.json fired=False silent=True fired_at=None curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-drop', 'C-backpressure'], 'new_evidence_ids': ['E-overflow-2', 'E-block-2'], 'consecutive_subfloor': 0}, {'round': 3, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-single-writer', 'C-shard'], 'new_evidence_ids': ['E-aba-3', 'E-shard-3'], 'consecutive_subfloor': 0}, {'round': 4, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-model-check', 'C-litmus'], 'new_evidence_ids': ['E-tla-4', 'E-litmus-4'], 'consecutive_subfloor': 0}]\nknown-good-refinement fixture=clean_refinement.json fired=False silent=True fired_at=None curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 2, 'subfloor': False, 'new_claim_ids': [], 'new_evidence_ids': ['E-lost-0', 'E-p99-2'], 'consecutive_subfloor': 0}, {'round': 3, 'information_units': 2, 'subfloor': False, 'new_claim_ids': [], 'new_evidence_ids': ['E-reorder-3', 'E-starve-3'], 'consecutive_subfloor': 0}, {'round': 4, 'information_units': 2, 'subfloor': False, 'new_claim_ids': [], 'new_evidence_ids': ['E-cpu-4', 'E-tail-4'], 'consecutive_subfloor': 0}]\nfired_on_bad=True silent_on_good=True detector_control_first=True false_positive_rate=0.0\nSUCCESS:CNL-0090-probe1 both-states and detector-control"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0090/probe2_independent_gain.py",
   "id": "probe2",
   "role": "independent-id-set-gain"
  }
 ],
 "negative_control": {
  "state_rejected": "clean-productive-counterexamples: a council that introduces a new counterexample and a new evidence node every round",
  "verbatim": "known-good-productive fixture=clean_productive.json fired=False silent=True fired_at=None curve=[{'round': 1, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-ring', 'C-mutex'], 'new_evidence_ids': ['E-trace-1', 'E-lat-1'], 'consecutive_subfloor': 0}, {'round': 2, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-drop', 'C-backpressure'], 'new_evidence_ids': ['E-overflow-2', 'E-block-2'], 'consecutive_subfloor': 0}, {'round': 3, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-single-writer', 'C-shard'], 'new_evidence_ids': ['E-aba-3', 'E-shard-3'], 'consecutive_subfloor': 0}, {'round': 4, 'information_units': 4, 'subfloor': False, 'new_claim_ids': ['C-model-check', 'C-litmus'], 'new_evidence_ids': ['E-tla-4', 'E-litmus-4'], 'consecutive_subfloor': 0}]",
  "what_the_check_does": "On that state the check stays SILENT (fired=false). If it fired, G_t would be measuring turns rather than information. Recorded verbatim below from probe 1."
 },
 "pathology": {
  "description": "The council keeps producing turns whose claims and evidence are already in the prior set, including paraphrases that mint new ids. Spec failure class: non-converging debate / loops forever without information gain.",
  "id": "circular-debate-no-information-gain",
  "spec_anchors": [
   "_USER-PROMPTS.md:11234",
   "_USER-PROMPTS.md:11338",
   "WORK-UNIT-CATALOG.json:CNL-0090",
   "WORK-UNIT-CATALOG.json:IMP-0322",
   "WORK-UNIT-CATALOG.json:TST-0263"
  ]
 },
 "question": "How is per-round information gain computed, and what gain threshold means the debate is circling rather than converging?",
 "report_kind": "council-detector-spec",
 "residual_unknowns": [
  "Full-rewrite duplicates that share neither tokens nor char-4grams are NOT-CHECKED; that class is CNL-0051's remainder and is not claimed here.",
  "tools/council/simulate.py is absent on this worktree; curves are from constructed fixtures, not 15 recorded live councils (IMP-0322).",
  "Absolute WINDOW=2 is a named policy on these fixtures; a larger corpus may justify a different consecutive-subfloor bound."
 ],
 "reviewer": {
  "independent": true,
  "re_derived_from": "id-set set-difference on the same four fixtures, not from this spec's prose",
  "reviewer_id": "CNL-0090-probe2-independent-gain",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "schema_version": 1,
 "scoped_recall": {
  "in_scope": [
   "verbatim restatement of the same claim_ids",
   "hyphenation and compound paraphrases that mint new ids",
   "refinement that adds evidence without new claims (must not fire)",
   "productive new counterexamples (must not fire)"
  ],
  "not_checked": [
   "embedding-level full rewrite",
   "cross-language paraphrase",
   "live multi-protocol gain curves required by TST-0263"
  ]
 },
 "sentinel": "SUCCESS:CNL-0090",
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "A council can spend two rounds restating a lemma while a participant prepares a proof; firing on G_t = 0 would abort useful incubation. That objection survives as a policy preference for a larger WINDOW, not as a refutation of the metric: a preparing seat can still add an evidence node or a new lemma claim, and WINDOW=2 is the named bound, not a hidden round cap.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0090/probe1_both_states.py",
   "id": "T1-both-states-detector-control",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0090/probe2_independent_gain.py",
   "id": "T2-independent-id-set-vs-jaccard",
   "result": "PASS"
  }
 ],
 "thresholds": {
  "char4_jaccard_duplicate": 0.35,
  "consecutive_subfloor_rounds": 2,
  "floor_information_units": 1,
  "meaning": "G_t < 1 means the round added neither a new claim nor a new evidence node. Two such rounds in a row is circling, not convergence. The bound is not a hardcoded round cap: a productive council that keeps introducing counterexamples never crosses the floor.",
  "token_jaccard_duplicate": 0.85
 },
 "timestamps": {
  "ended_at": "2026-08-25T00:57:30Z"
 },
 "title": "Circular debate: information gain per round",
 "unit_id": "CNL-0090"
}
