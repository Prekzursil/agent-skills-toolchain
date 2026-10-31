{
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0050-protocol-composition-primitives-phase-ordering-and-the-spe.md",
   "role": "primary"
  }
 ],
 "decision": {
  "summary": "Custom protocols are compiled from sequence, splice, nest and repeat-until. Nest is the only split; a stack checker rejects any converge that is not preceded by an unmatched diverge, so converge-before-diverge is a compile error. Independently recomputed from catalog quotations, 7 spec-named protocol(s) have no card among the 58: ['100-idea-brainstorm', 'configurable-council', 'council-of-councils', 'mediation', 'negotiation', 'socratic-cross-examination', 'steelman-before-rebuttal']. Those must be authored. All 7 META-COMPOSITION cards compile in the four primitives (0 gaps in that family)."
 },
 "dependencies_on_tree": {
  "CNL-0010_artifact": false,
  "CNL-0046_artifact": false,
  "note": "CNL-0046 and CNL-0010 artifacts are absent. META-COMPOSITION membership is taken from CNL-0046's catalog enumeration (P52-P58), not from its missing design note. repeat-until's predicate is an explicit hole."
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0050/compose.py:check_order",
   "claim": "A converge-before-diverge composition is rejected at compile time.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json CNL-0038..CNL-0046 question_or_target",
   "claim": "The 58 card names were recovered by two disagreeable parsers, both n=58.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0050/census.py:gap_report",
   "claim": "Spec-vs-corpus gap was set-subtracted from catalog-quoted spec names, not copied from this unit's brief.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0050/meta_trees.py:META_TREES",
   "claim": "Every META-COMPOSITION card is expressible in the primitives or listed as a gap.",
   "verdict": "CONFIRMED"
  }
 ],
 "meta_composition": {
  "all_expressible_or_gapped": true,
  "n": 7,
  "n_compile_fail": 0,
  "n_expressible": 7,
  "n_gap": 0,
  "primitives": [
   "sequence",
   "splice",
   "nest",
   "repeat-until"
  ],
  "rows": [
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P52",
    "reading": "nest = parallel child councils (diverge) then mandatory fan-in (converge). Sequence is not used for the split because sequence cannot express simultaneous children.",
    "slug": "nested-subcouncils-meta-council",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "nest"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P53",
    "reading": "Escalation is a sequence of rungs wrapped in repeat-until. It does not fan out, so nest is unused.",
    "slug": "escalation-ladder",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "repeat-until",
     "sequence"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P54",
    "reading": "Two mirrored copies under nest: diverge, run, converge and compare.",
    "slug": "cross-vendor-mirrored",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "nest"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P55",
    "reading": "Primary and silent shadow as nest inners; converge is the comparison point.",
    "slug": "shadow-council",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "nest"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P56",
    "reading": "Splice inserts the mandatory minority report into the majority sequence so it cannot be omitted by dropping a later optional step.",
    "slug": "minority-report-mandatory",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "sequence",
     "splice"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P57",
    "reading": "Competing stopping rules run as nest inners; converge picks the winner.",
    "slug": "stopping-rule-tournament",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "nest"
    ]
   },
   {
    "accepted": true,
    "code": "ok",
    "gap_reason": null,
    "id": "P58",
    "reading": "Each increment is sequence(work, owner-gate) under repeat-until. The until predicate is a hole for CNL-0010's stopping grammar.",
    "slug": "owner-in-the-loop-stepwise",
    "status": "EXPRESSIBLE",
    "used_ops": [
     "repeat-until",
     "sequence"
    ]
   }
  ]
 },
 "negative_control": {
  "accepted": false,
  "code": "converge-before-diverge",
  "fixture_id": "planted-converge-before-diverge",
  "intended_reject": "converge-before-diverge",
  "stage": "phase-order",
  "verbatim": "compile(planted-converge-before-diverge) accepted=False stage=phase-order code=converge-before-diverge",
  "what_the_check_does_on_the_state_it_rejects": "On a sequence whose first event is phase=converge and whose second event is phase=diverge, compile_expr returns accepted=false at stage=phase-order with code=converge-before-diverge and does not emit a runnable schedule."
 },
 "phase_ordering": {
  "composer_cannot_accidentally_violate": true,
  "enforcement": "compile-time stack: diverge pushes, converge pops; pop on empty stack is reject",
  "known_good": {
   "accepted": true,
   "code": "ok",
   "id": "known-good-nest-diverge-then-converge",
   "n_events": 4
  },
  "planted_bad": {
   "accepted": false,
   "code": "converge-before-diverge",
   "fixture_id": "planted-converge-before-diverge",
   "intended_reject": "converge-before-diverge",
   "stage": "phase-order",
   "verbatim": "compile(planted-converge-before-diverge) accepted=False stage=phase-order code=converge-before-diverge",
   "what_the_check_does_on_the_state_it_rejects": "On a sequence whose first event is phase=converge and whose second event is phase=diverge, compile_expr returns accepted=false at stage=phase-order with code=converge-before-diverge and does not emit a runnable schedule."
  },
  "planted_splice_bad": {
   "accepted": false,
   "code": "converge-before-diverge",
   "id": "planted-splice-converge-at-head"
  },
  "rule": "diverge-before-converge"
 },
 "primitives": {
  "names": [
   "sequence",
   "splice",
   "nest",
   "repeat-until"
  ],
  "nest": "Emit diverge, run inners, emit converge. The only primitive that opens a split.",
  "non_primitive": "There is no fifth 'parallel' op. Parallelism is nest. A composer who wants fan-in without nest must use a converge leaf, which the phase checker rejects unless a diverge is already open.",
  "repeat_until": "Compile one body iteration plus an until:<pred> marker. The predicate is a hole for CNL-0010; this unit does not claim a stopping parser.",
  "sequence": "Concatenate child schedules. No implicit fan-out.",
  "splice": "Insert one compiled schedule into another at a compile-time index."
 },
 "question": "What primitives (sequence, splice, nest, repeat-until) compose two protocols into a custom one, how is divergence-before-convergence enforced as an ordering constraint the composer cannot accidentally violate, and - measured independently - which protocols named in the spec's own list have NO card among the 58 (a first pass finds steelman and negotiation absent) so must be authored rather than composed?",
 "reviewer": {
  "independent": true,
  "recount": {
   "cards_method_b": 58,
   "disagreement_with_author_method_a": false,
   "gap_conservative_n": 7
  },
  "reviewer_id": "CNL-0050-probe2-method-b-comma-split",
  "verdict": "PASS"
 },
 "schema": "command-center/schema/council-design-note.schema.json",
 "sentinel": "SUCCESS:CNL-0050",
 "source_disclosure": {
  "card_census_method": "Two parsers over CNL-0038..CNL-0046 question_or_target (regex P-id+slug vs comma-split of the named-so-no-member list). 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent; the catalog units are the on-tree witness of those 58 P-ids.",
  "card_census_source": "command-center/WORK-UNIT-CATALOG.json",
  "spec_name_source": "_USER-PROMPTS.md is not on this worktree; names are catalog quotations of the spec protocol list, not a read of the original file.",
  "twelve_council_file_on_disk": false,
  "user_prompts_on_disk": false
 },
 "spec_vs_corpus_gap": {
  "brief_first_pass_names": [
   "steelman",
   "negotiation"
  ],
  "gap_conservative": [
   "100-idea-brainstorm",
   "configurable-council",
   "council-of-councils",
   "mediation",
   "negotiation",
   "socratic-cross-examination",
   "steelman-before-rebuttal"
  ],
  "gap_substring": [
   "100-idea-brainstorm",
   "configurable-council",
   "council-of-councils",
   "mediation",
   "negotiation",
   "socratic-cross-examination",
   "steelman-before-rebuttal"
  ],
  "inherited_from_unit_brief": false,
  "must_be_authored_not_composed": [
   "100-idea-brainstorm",
   "configurable-council",
   "council-of-councils",
   "mediation",
   "negotiation",
   "socratic-cross-examination",
   "steelman-before-rebuttal"
  ],
  "n_cards": 58,
  "n_gap_conservative": 7,
  "n_gap_substring": 7,
  "n_spec_named": 12,
  "rows": [
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "configurable-council",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "100-idea-brainstorm",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [
     {
      "id": "P20",
      "slug": "delphi-anonymous-rounds"
     },
     {
      "id": "P21",
      "slug": "wideband-delphi-estimation"
     }
    ],
    "has_card_conservative": true,
    "name": "delphi",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [
     {
      "id": "P07",
      "slug": "oxford-debate"
     }
    ],
    "has_card_conservative": true,
    "name": "oxford-debate",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "socratic-cross-examination",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [
     {
      "id": "P14",
      "slug": "judge-and-jury"
     },
     {
      "id": "P16",
      "slug": "grand-jury-threshold"
     },
     {
      "id": "P17",
      "slug": "jury-with-allowed-hung"
     }
    ],
    "has_card_conservative": true,
    "name": "jury",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "negotiation",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "mediation",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "council-of-councils",
    "source_unit": "IMP-0256"
   },
   {
    "conservative_hits": [],
    "has_card_conservative": false,
    "name": "steelman-before-rebuttal",
    "source_unit": "TST-0294"
   },
   {
    "conservative_hits": [
     {
      "id": "P43",
      "slug": "premortem"
     }
    ],
    "has_card_conservative": true,
    "name": "premortem",
    "source_unit": "RES-0158"
   },
   {
    "conservative_hits": [
     {
      "id": "P48",
      "slug": "kill-the-company (war-game)"
     }
    ],
    "has_card_conservative": true,
    "name": "war-game",
    "source_unit": "RES-0158"
   }
  ],
  "spec_named": [
   "configurable-council",
   "100-idea-brainstorm",
   "delphi",
   "oxford-debate",
   "socratic-cross-examination",
   "jury",
   "negotiation",
   "mediation",
   "council-of-councils",
   "steelman-before-rebuttal",
   "premortem",
   "war-game"
  ]
 },
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0050/probe1_compile_order.py",
   "id": "T-compile-order",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0050/probe2_gap_and_meta.py",
   "id": "T-gap-and-meta",
   "result": "PASS"
  }
 ],
 "ts": "2026-08-25T00:52:26Z",
 "unit_id": "CNL-0050"
}
