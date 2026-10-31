{
 "answer": "A same-seat pair is structurally incompatible iff the union of the two roles' capability predicates both authors and adjudicates (judge, vote, or veto) the same artifact kind. On the closed 8-role template set that is exactly 8 unordered pairs (critic+judge, critic+juror, judge+juror, judge+proposer, judge+synthesiser, judge+vetoer, juror+proposer, proposer+vetoer); equivalently 16 of 64 ordered dual-hat assignments, with 48 compatible. The check is those constraints plus declared-interest overlap on adjudicate capabilities and a hard fail when capability or interest fields are absent. A two-row named-pair if-ladder of the catalog examples (proposer+judge, critic+juror) silently misses 6 template pairs including judge+synthesiser, and it accepts custom scribe+grader which the solver rejects. Independent bitmask recount matched the set-overlap solver on every cell. This is not a census of the 58 protocol records (file absent). SUCCESS:CNL-0029",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0029-incompatible-role-and-conflict-of-interest-checker-as-a-co.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0029/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0029/solver.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0029/bitmask_recount.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0029/fixtures/templates.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json",
   "role": "supporting"
  }
 ],
 "both_states": {
  "coi_known_good_silent": true,
  "coi_planted_bad_fired": true,
  "known_good": {
   "fired": false,
   "id": "known_good_pcj",
   "silent": true,
   "verbatim": "{\"fired\": false, \"roster_id\": \"known-good-pcj\", \"silent\": true, \"violation_count\": 0, \"violations\": []}"
  },
  "planted_bad": {
   "fired": true,
   "id": "planted_bad_self_review",
   "silent": false,
   "verbatim": "{\"fired\": true, \"roster_id\": \"planted-bad-self-review\", \"silent\": false, \"violation_count\": 1, \"violations\": [{\"adjudicate_caps\": [\"judge\"], \"constraint\": \"SAME-SEAT-AUTHOR-ADJUDICATE\", \"kind\": \"proposal\", \"roles\": [\"proposer\", \"judge\"], \"seat\": \"s-dual\"}]}"
  }
 },
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/solver.py:25",
   "claim": "Same-seat incompatibility is author-and-adjudicate overlap on one artifact kind, not a name table.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/bitmask_recount.py:49",
   "claim": "Exhaustive scan of the 8-template set yields 16 incompatible and 48 compatible ordered pairs.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/ladder.py:11",
   "claim": "A two-row named-pair if-ladder of the catalog examples is a complete incompatible-role check.",
   "defect_locus": "DESIGN",
   "id": "C3",
   "scoped_restatement": "The ladder hits proposer+judge and critic+juror and misses 6 solver-incompatible unordered pairs: ['critic+judge', 'judge+juror', 'judge+synthesiser', 'judge+vetoer', 'juror+proposer', 'proposer+vetoer'].",
   "verdict": "REFUTED",
   "why_locus": "ladder.py is the losing design, not a wording slip."
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json:94",
   "claim": "Custom scribe+grader (author proposal / judge proposal) is rejected by the solver and accepted by the ladder.",
   "id": "C4",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/fixtures/templates.json:5",
   "claim": "This unit enumerated every role named across the 58 catalogued protocol records.",
   "defect_locus": "SENTENCE",
   "id": "C5",
   "scoped_restatement": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent. The template set is the closed 8-role library named by CNL-0022..CNL-0032.",
   "verdict": "REFUTED",
   "why_locus": "Coverage of 58 protocols is a catalog-adjacent sentence, not a rule in the solver."
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json:94",
   "claim": "The check fires on planted-bad proposer+judge and is silent on a three-seat PCJ roster.",
   "id": "C6",
   "verdict": "CONFIRMED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0029",
 "custom_role_contract": {
  "must_supply": [
   "author/judge/vote/veto/chair predicates over artifact kinds",
   "declared_interests list (may be empty)"
  ],
  "mystery_no_caps_refused": true,
  "scribe_grader_ladder_fired": false,
  "scribe_grader_solver_fired": true
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/solver.py:25",
   "claim": "Structural COI is discharged as author/adjudicate kind overlap.",
   "kind": "live-tree",
   "line": 25,
   "mechanism": "python-set-overlap",
   "path": "command-center/p2-wave/probes/CNL-0029/solver.py",
   "snippet": "STRUCTURAL = \"SAME-SEAT-AUTHOR-ADJUDICATE\"",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/bitmask_recount.py:49",
   "claim": "Independent bitmask OR/AND recount of the same matrix.",
   "kind": "live-tree",
   "line": 49,
   "mechanism": "bitmask-OR-then-AND",
   "path": "command-center/p2-wave/probes/CNL-0029/bitmask_recount.py",
   "snippet": "return (author_kinds(merged, n) & adjudicate_kinds(merged, n)) != 0",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/fixtures/templates.json:5",
   "claim": "Template set is closed and does not claim 58-protocol coverage.",
   "kind": "fixture",
   "line": 5,
   "mechanism": "fixture-literal",
   "path": "command-center/p2-wave/probes/CNL-0029/fixtures/templates.json",
   "snippet": "Closed 8-role library covering roles named by CNL-0022 through CNL-0032",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:35738",
   "claim": "Catalog question names the two examples and the if-ladder failure mode.",
   "kind": "catalog",
   "line": 35738,
   "mechanism": "catalog-field",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "Which role pairs are structurally incompatible on one seat",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json:94",
   "claim": "Planted-bad roster seats proposer and judge on one seat.",
   "kind": "fixture",
   "line": 94,
   "mechanism": "fixture-literal",
   "path": "command-center/p2-wave/probes/CNL-0029/fixtures/rosters.json",
   "snippet": "\"id\": \"planted-bad-self-review\"",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0029/ladder.py:11",
   "claim": "If-ladder hard-codes only the two catalog examples.",
   "kind": "live-tree",
   "line": 11,
   "mechanism": "named-pair-ladder",
   "path": "command-center/p2-wave/probes/CNL-0029/ladder.py",
   "snippet": "frozenset({\"proposer\", \"judge\"})",
   "verdict": "REFUTED"
  }
 ],
 "family": {
  "counted_n": 8,
  "expected_n": 8,
  "members": [
   {
    "author": [],
    "chair": [
     "agenda"
    ],
    "id": "chair",
    "judge": [],
    "record_id": "chair",
    "veto": [],
    "vote": []
   },
   {
    "author": [
     "objection"
    ],
    "chair": [],
    "id": "critic",
    "judge": [],
    "record_id": "critic",
    "veto": [],
    "vote": []
   },
   {
    "author": [
     "ruling"
    ],
    "chair": [],
    "id": "judge",
    "judge": [
     "objection",
     "proposal",
     "synthesis"
    ],
    "record_id": "judge",
    "veto": [],
    "vote": []
   },
   {
    "author": [],
    "chair": [],
    "id": "juror",
    "judge": [],
    "record_id": "juror",
    "veto": [],
    "vote": [
     "objection",
     "proposal",
     "ruling"
    ]
   },
   {
    "author": [],
    "chair": [
     "agenda"
    ],
    "id": "moderator",
    "judge": [],
    "record_id": "moderator",
    "veto": [],
    "vote": []
   },
   {
    "author": [
     "proposal"
    ],
    "chair": [],
    "id": "proposer",
    "judge": [],
    "record_id": "proposer",
    "veto": [],
    "vote": []
   },
   {
    "author": [
     "synthesis"
    ],
    "chair": [],
    "id": "synthesiser",
    "judge": [],
    "record_id": "synthesiser",
    "veto": [],
    "vote": []
   },
   {
    "author": [],
    "chair": [],
    "id": "vetoer",
    "judge": [],
    "record_id": "vetoer",
    "veto": [
     "proposal",
     "ruling"
    ],
    "vote": []
   }
  ],
  "name": "cnl-0029-role-template-library"
 },
 "id": "CNL-0029",
 "matrix": {
  "bitmask_agree": true,
  "cells": [
   {
    "a": "chair",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "judge",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "juror",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "proposer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "chair",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "judge",
    "incompatible": true,
    "kinds": [
     "objection"
    ]
   },
   {
    "a": "critic",
    "b": "juror",
    "incompatible": true,
    "kinds": [
     "objection"
    ]
   },
   {
    "a": "critic",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "proposer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "critic",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "judge",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "judge",
    "b": "critic",
    "incompatible": true,
    "kinds": [
     "objection"
    ]
   },
   {
    "a": "judge",
    "b": "judge",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "judge",
    "b": "juror",
    "incompatible": true,
    "kinds": [
     "ruling"
    ]
   },
   {
    "a": "judge",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "judge",
    "b": "proposer",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "judge",
    "b": "synthesiser",
    "incompatible": true,
    "kinds": [
     "synthesis"
    ]
   },
   {
    "a": "judge",
    "b": "vetoer",
    "incompatible": true,
    "kinds": [
     "ruling"
    ]
   },
   {
    "a": "juror",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "juror",
    "b": "critic",
    "incompatible": true,
    "kinds": [
     "objection"
    ]
   },
   {
    "a": "juror",
    "b": "judge",
    "incompatible": true,
    "kinds": [
     "ruling"
    ]
   },
   {
    "a": "juror",
    "b": "juror",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "juror",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "juror",
    "b": "proposer",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "juror",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "juror",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "judge",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "juror",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "proposer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "moderator",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "judge",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "proposer",
    "b": "juror",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "proposer",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "proposer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "proposer",
    "b": "vetoer",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "synthesiser",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "judge",
    "incompatible": true,
    "kinds": [
     "synthesis"
    ]
   },
   {
    "a": "synthesiser",
    "b": "juror",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "proposer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "synthesiser",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "chair",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "critic",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "judge",
    "incompatible": true,
    "kinds": [
     "ruling"
    ]
   },
   {
    "a": "vetoer",
    "b": "juror",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "moderator",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "proposer",
    "incompatible": true,
    "kinds": [
     "proposal"
    ]
   },
   {
    "a": "vetoer",
    "b": "synthesiser",
    "incompatible": false,
    "kinds": []
   },
   {
    "a": "vetoer",
    "b": "vetoer",
    "incompatible": false,
    "kinds": []
   }
  ],
  "compatible_ordered": 48,
  "computed_not_asserted": true,
  "incompatible_ordered": 16,
  "incompatible_unordered": [
   "critic+judge",
   "critic+juror",
   "judge+juror",
   "judge+proposer",
   "judge+synthesiser",
   "judge+vetoer",
   "juror+proposer",
   "proposer+vetoer"
  ],
  "incompatible_unordered_count": 8,
  "ladder_misses": [
   "critic+judge",
   "judge+juror",
   "judge+synthesiser",
   "judge+vetoer",
   "juror+proposer",
   "proposer+vetoer"
  ],
  "ladder_named_pairs": [
   "critic+juror",
   "judge+proposer"
  ],
  "ordered_pair_count": 64,
  "template_count": 8,
  "template_names": [
   "chair",
   "critic",
   "judge",
   "juror",
   "moderator",
   "proposer",
   "synthesiser",
   "vetoer"
  ]
 },
 "negative_control": {
  "fired": true,
  "fixture": "planted_bad_self_review",
  "intended_reject_state": "one seat holds proposer and judge",
  "silent": false,
  "verbatim": "{\"fired\": true, \"roster_id\": \"planted-bad-self-review\", \"silent\": false, \"violation_count\": 1, \"violations\": [{\"adjudicate_caps\": [\"judge\"], \"constraint\": \"SAME-SEAT-AUTHOR-ADJUDICATE\", \"kind\": \"proposal\", \"roles\": [\"proposer\", \"judge\"], \"seat\": \"s-dual\"}]}",
  "violations": [
   {
    "adjudicate_caps": [
     "judge"
    ],
    "constraint": "SAME-SEAT-AUTHOR-ADJUDICATE",
    "kind": "proposal",
    "roles": [
     "proposer",
     "judge"
    ],
    "seat": "s-dual"
   }
  ]
 },
 "output_schema": "command-center/schema/council-design-note.schema.json",
 "question": "Which role pairs are structurally incompatible on one seat (proposer judging its own proposal, critic voting on its own objection), and can the check be expressed as constraints a solver discharges rather than a hand-written if-ladder that silently misses a pair?",
 "residual_unknowns": [
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json and 11-COUNCIL-SPECIFICATION.schema.json are not on this worktree, so this note does not claim a 58-protocol role census (that is CNL-0028).",
  "CNL-0022 role-mandate schema is not delivered here; capability predicates are the contract a custom role must supply for this checker to reason."
 ],
 "reviewer": {
  "independent": true,
  "method": "Re-tabulate every ordered pair from fixtures/templates.json via bitmask_recount.py without reading this note's matrix field as the source of truth.",
  "reviewer_id": "CNL-0029-probe2-bitmask-recount",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0029",
 "signals": [
  {
   "compatible_ordered": 48,
   "id": "S1",
   "incompatible_ordered": 16,
   "mechanism": "python-set-overlap"
  },
  {
   "compatible_ordered": 48,
   "id": "S2",
   "incompatible_ordered": 16,
   "mechanism": "bitmask-OR-then-AND"
  }
 ],
 "state": "SUCCESS",
 "status": "DELIVERED",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0029/probe1_exhaustive_both_states.py",
   "id": "exhaustive-matrix",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0029/probe2_independent_recount.py",
   "id": "independent-bitmask-recount",
   "result": "PASS"
  }
 ],
 "title": "Incompatible-role and conflict-of-interest checker as a constraint solver",
 "ts": "2026-08-25T00:27:44Z",
 "unit_id": "CNL-0029",
 "verdicts": [
  {
   "record_id": "chair",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "critic",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "judge",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "juror",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "moderator",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "proposer",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "synthesiser",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "vetoer",
   "verdict": "EXECUTABLE"
  }
 ]
}
