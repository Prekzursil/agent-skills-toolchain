{
 "artifacts": [
  {
   "bytes": 4442,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/tabulator.py",
   "role": "primary",
   "sha256": "81e10f82401d0dccfed8b54cba6bed7bb2df81f2fce43b62b7e7d01a746d78cc"
  },
  {
   "bytes": 4942,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/recount.py",
   "role": "supporting",
   "sha256": "5d9287639c23976b5602791839e9f13d8cd3960458199aa4fdaf6e4cb1d7c89f"
  },
  {
   "bytes": 4883,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/simulate.py",
   "role": "supporting",
   "sha256": "ca765d2be465c1af6127d1cd3d894d77be8a4eb271e0ad3a7bc4d29a39e5541e"
  },
  {
   "bytes": 3743,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/fixtures.py",
   "role": "supporting",
   "sha256": "1d4df6e42acb0f49570e0ae730b9ab0c40ec08b16d8ea2df645192e50b274f8d"
  },
  {
   "bytes": 12648,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/fixtures/profiles.json",
   "role": "supporting",
   "sha256": "f6f03c41e0ced896f1124ab429d6064648a38bd36c156961edfa9be5832c1e2d"
  },
  {
   "bytes": 676,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/fixtures/rules.json",
   "role": "supporting",
   "sha256": "ce67dd834cc99c1a4bc5c0a7c414a146ba54be6f933a9f6d9180bd18c11ad730"
  },
  {
   "bytes": 11632,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0119/runtime/simulation-report.json",
   "role": "supporting",
   "sha256": "0f857d4e6c14efce51a4baf465402b208b61def3e69923a8592bae4dd79ab994"
  }
 ],
 "defects": [],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0119-voting-method-differential-simulation-over-one-ballot-set.md",
   "consumer": "CNL-0119 probe1 disagreement-sensitivity",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py",
    "exit_code": 0,
    "fingerprint": "cnl0119:consumer:probe1",
    "method": "command",
    "raw_output": "n_fixtures=9 n_disagree=5 disagreement_rate=0.555556 most_sensitive=approval_top2 n_winner_changes=33",
    "role": "source"
   },
   "read_ok": true
  },
  {
   "artifact_path": "command-center/design/council/CNL-0119-voting-method-differential-simulation-over-one-ballot-set.md",
   "consumer": "CNL-0119 probe2 independent recount",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
    "exit_code": 0,
    "fingerprint": "cnl0119:consumer:probe2",
    "method": "command",
    "raw_output": "recount n_disagree=5/9 rate=0.555556 most_sensitive=approval_top2\nNEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:115",
   "claim": "5 of 9 declared fixtures have a method disagreement (rate 0.555556).",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py",
     "exit_code": 0,
     "fingerprint": "cnl0119:probe1:tabulator-disagreement",
     "method": "command",
     "raw_output": "n_fixtures=9 n_disagree=5 disagreement_rate=0.555556 most_sensitive=approval_top2 n_winner_changes=33",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "cnl0119:probe2:pointer-irv-recount",
     "method": "command",
     "raw_output": "recount n_disagree=5/9 rate=0.555556 most_sensitive=approval_top2\nNEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:88",
   "claim": "Most flip-sensitive method is approval_top2 with 33 winner changes over 79 flips.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py",
     "exit_code": 0,
     "fingerprint": "cnl0119:probe1:flip-sweep",
     "method": "command",
     "raw_output": "n_fixtures=9 n_disagree=5 disagreement_rate=0.555556 most_sensitive=approval_top2 n_winner_changes=33",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "cnl0119:probe2:flip-recount",
     "method": "command",
     "raw_output": "recount n_disagree=5/9 rate=0.555556 most_sensitive=approval_top2\nNEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0119/recount.py:44",
   "claim": "Independent pointer-IRV / matrix Copeland recount matches the primary tabulator on every fixture winner and the sensitivity table.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "command-center/p2-wave/probes/CNL-0119/recount.py:44",
     "exit_code": 0,
     "fingerprint": "cnl0119:recount.py:pointer-irv",
     "method": "file-read",
     "raw_output": "Continuing-pointer IRV (not first-match rescans)",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
     "exit_code": 0,
     "fingerprint": "cnl0119:probe2:engines-match",
     "method": "command",
     "raw_output": "recount n_disagree=5/9 rate=0.555556 most_sensitive=approval_top2\nNEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "answer": "On the declared 9-fixture ranking corpus, 5 fixtures produce a method disagreement about the winner (rate 5/9 = 0.555556). Disagreeing ids: spoiler-triple, center-squeeze, approval-split, cycle-asymmetric, score-borda-split. A single flipped ballot is demote-first-to-last on exactly one voter. Most sensitive method: approval_top2 with 33 winner-changing flips out of 79 (rate 0.417722). Sensitivity table: plurality 12/79 (0.151899); irv 25/79 (0.316456); borda 21/79 (0.265823); approval_top2 33/79 (0.417722); score_5310 22/79 (0.278481); copeland_minimax 22/79 (0.278481). Cardinal methods read the same ranking via declared projections (approval top-2; score vector 5,3,1,0); they are not a second ballot.",
  "both_states": {
   "bad_state": {
    "detector": "FIRE",
    "id": "spoiler-triple",
    "winners": {
     "approval_top2": "B",
     "borda": "B",
     "copeland_minimax": "B",
     "irv": "C",
     "plurality": "A",
     "score_5310": "B"
    }
   },
   "good_state": {
    "detector": "SILENT",
    "id": "unanimous-3",
    "winners": {
     "approval_top2": "A",
     "borda": "A",
     "copeland_minimax": "A",
     "irv": "A",
     "plurality": "A",
     "score_5310": "A"
    }
   },
   "pass": true
  },
  "catalog_question_anchor": "command-center/WORK-UNIT-CATALOG.json:40330",
  "dependencies_noted": {
   "CNL-0061": "IRV elimination + lex-largest last-place tie-break implemented here",
   "CNL-0062": "approval_top2 and score_5310 are declared projections of the same ranking",
   "CNL-0063": "Copeland, then minimax (max votes-against), then lex, declared before ballots",
   "CNL-0065": "credence pooling is not a ranking SCF; excluded from the method list",
   "CNL-0117": "determinism via frozen fixtures, not the missing harness artifact",
   "blocked_on_missing_deps": false
  },
  "family": {
   "counted_n": 6,
   "expected_n": 6,
   "members": [
    {
     "id": "plurality"
    },
    {
     "id": "irv"
    },
    {
     "id": "borda"
    },
    {
     "id": "approval_top2"
    },
    {
     "id": "score_5310"
    },
    {
     "id": "copeland_minimax"
    }
   ],
   "name": "implemented-winner-selection-methods"
  },
  "named_probes": [
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py",
    "id": "probe1",
    "role": "disagreement-sensitivity"
   },
   {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
    "id": "probe2",
    "role": "independent-recount"
   }
  ],
  "negative_control": {
   "control_fixture": "unanimous-3, seven identical A>B>C rankings",
   "state_the_check_is_meant_to_reject": "a planted ranking profile on which implemented methods elect different winners (spoiler-triple)",
   "verbatim": "NEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
   "what_the_check_does_on_that_state": "SILENT: plurality, IRV, Borda, approval_top2, score_5310, and copeland_minimax all elect A"
  },
  "phase": "2C",
  "question": "Run one fixed set of ballots through every implemented voting method - on how many fixtures do the methods disagree about the winner, and which method is most sensitive to a single flipped ballot?",
  "results": {
   "agreeing_fixture_ids": [
    "unanimous-3",
    "majority-clear",
    "close-plurality",
    "unanimous-4"
   ],
   "disagreeing_fixture_ids": [
    "spoiler-triple",
    "center-squeeze",
    "approval-split",
    "cycle-asymmetric",
    "score-borda-split"
   ],
   "disagreement_rate": 0.5555555555555556,
   "fixtures": [
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 7,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "unanimous-3",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "negative-control-agree",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 5,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "majority-clear",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "agree-majority",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 0,
      "borda": 2,
      "copeland_minimax": 2,
      "irv": 5,
      "plurality": 0,
      "score_5310": 2
     },
     "id": "spoiler-triple",
     "methods_disagree": true,
     "n_ballots": 13,
     "n_flips": 13,
     "role": "planted-disagreement",
     "winner_set": [
      "A",
      "B",
      "C"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "B",
      "copeland_minimax": "B",
      "irv": "C",
      "plurality": "A",
      "score_5310": "B"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 0,
      "borda": 2,
      "copeland_minimax": 2,
      "irv": 4,
      "plurality": 0,
      "score_5310": 2
     },
     "id": "center-squeeze",
     "methods_disagree": true,
     "n_ballots": 11,
     "n_flips": 11,
     "role": "disagreement",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "B",
      "copeland_minimax": "B",
      "irv": "A",
      "plurality": "A",
      "score_5310": "B"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 3,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 3,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "approval-split",
     "methods_disagree": true,
     "n_ballots": 9,
     "n_flips": 9,
     "role": "disagreement",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 4,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 4,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "close-plurality",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "sensitivity",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 3,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 3,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "cycle-asymmetric",
     "methods_disagree": true,
     "n_ballots": 9,
     "n_flips": 9,
     "role": "cycle",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C",
      "D"
     ],
     "flip_changes": {
      "approval_top2": 5,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "unanimous-4",
     "methods_disagree": false,
     "n_ballots": 5,
     "n_flips": 5,
     "role": "negative-control-agree",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C",
      "D"
     ],
     "flip_changes": {
      "approval_top2": 6,
      "borda": 5,
      "copeland_minimax": 6,
      "irv": 6,
      "plurality": 0,
      "score_5310": 6
     },
     "id": "score-borda-split",
     "methods_disagree": true,
     "n_ballots": 11,
     "n_flips": 11,
     "role": "ordinal-cardinal",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "B",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    }
   ],
   "most_sensitive": {
    "method": "approval_top2",
    "n_winner_changes": 33,
    "rate": 0.4177215189873418,
    "rule": "max n_winner_changes, then max rate, then lex-smallest method id",
    "tied_methods": [
     "approval_top2"
    ]
   },
   "n_agree": 4,
   "n_disagree": 5,
   "n_fixtures": 9,
   "sensitivity_table": [
    {
     "method": "plurality",
     "n_flips_tried": 79,
     "n_winner_changes": 12,
     "rate": 0.1518987341772152
    },
    {
     "method": "irv",
     "n_flips_tried": 79,
     "n_winner_changes": 25,
     "rate": 0.31645569620253167
    },
    {
     "method": "borda",
     "n_flips_tried": 79,
     "n_winner_changes": 21,
     "rate": 0.26582278481012656
    },
    {
     "method": "approval_top2",
     "n_flips_tried": 79,
     "n_winner_changes": 33,
     "rate": 0.4177215189873418
    },
    {
     "method": "score_5310",
     "n_flips_tried": 79,
     "n_winner_changes": 22,
     "rate": 0.27848101265822783
    },
    {
     "method": "copeland_minimax",
     "n_flips_tried": 79,
     "n_winner_changes": 22,
     "rate": 0.27848101265822783
    }
   ]
  },
  "reviewer_method": "Probe 2 re-tabulates every fixture with recount.py (continuing-pointer IRV and an n-by-n pairwise matrix).",
  "simulation": {
   "fixture_set": {
    "ids": [
     "unanimous-3",
     "majority-clear",
     "spoiler-triple",
     "center-squeeze",
     "approval-split",
     "close-plurality",
     "cycle-asymmetric",
     "unanimous-4",
     "score-borda-split"
    ],
    "n_fixtures": 9,
    "note": "Complete rankings. Odd n_ballots per fixture so pairwise contests have no ties.",
    "path": "command-center/p2-wave/probes/CNL-0119/fixtures/profiles.json"
   },
   "harness": "frozen JSON rankings (one ranking per voter); not a live LLM council",
   "implemented_on_this_tree": [
    "plurality",
    "irv",
    "borda",
    "approval_top2",
    "score_5310",
    "copeland_minimax"
   ],
   "method_rules": {
    "approval_k": 2,
    "condorcet_completion": "Copeland (wins minus losses) declared first; Copeland ties completed by minimax (smallest maximum pairwise votes-against), then lex-smallest id",
    "irv_eliminate": "fewest-continuing-first-preferences, then lexicographically-largest candidate id",
    "methods": [
     "plurality",
     "irv",
     "borda",
     "approval_top2",
     "score_5310",
     "copeland_minimax"
    ],
    "score_vector": [
     5,
     3,
     1,
     0
    ],
    "single_ballot_flip": "demote the voter's first-ranked candidate to last place (remaining ranks shift up); other ballots held fixed",
    "tie_break": "lexicographically-smallest candidate id among remaining tied winners"
   },
   "methods": [
    "plurality",
    "irv",
    "borda",
    "approval_top2",
    "score_5310",
    "copeland_minimax"
   ],
   "not_implemented_here": [
    "majority-threshold / supermajority / unanimity / consent",
    "juror / judge / veto / quorum / abstention / delegation",
    "weighted (all weights=1, so weighted plurality collapses to plurality)",
    "Bayesian-as-ranking-SCF (CNL-0065 is credence pooling, not a winner)"
   ]
  },
  "spoiler_fixture_anchor": "command-center/p2-wave/probes/CNL-0119/fixtures/profiles.json:252",
  "title": "Voting-method differential simulation over one ballot set",
  "verdicts": [
   {
    "record_id": "plurality",
    "verdict": "EXECUTABLE"
   },
   {
    "record_id": "irv",
    "verdict": "EXECUTABLE"
   },
   {
    "record_id": "borda",
    "verdict": "EXECUTABLE"
   },
   {
    "record_id": "approval_top2",
    "verdict": "EXECUTABLE"
   },
   {
    "record_id": "score_5310",
    "verdict": "EXECUTABLE"
   },
   {
    "record_id": "copeland_minimax",
    "verdict": "EXECUTABLE"
   }
  ]
 },
 "manifest_registration": {
  "entry_id": "CNL-0119",
  "manifest_path": "command-center/p2-wave/probes/CNL-0119/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 4000,
 "negative_controls": [
  {
   "bad_state_output": "FIRE on spoiler-triple: plurality=A irv=C borda=B",
   "description": "Disagreement detector on unanimous-3 (every ranking A>B>C). Meant to stay SILENT: every implemented method elects A.",
   "fired_on_bad_state": true,
   "good_state_output": "SILENT on unanimous-3: plurality=irv=borda=approval_top2=score_5310=copeland_minimax=A",
   "id": "unanimous-3-silent",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "NEGATIVE-CONTROL verbatim: the disagreement check is SILENT on unanimous-3 (every method elects A) and FIRES on spoiler-triple (plurality=A, irv=C, borda=B).",
   "description": "Planted disagreement: spoiler-triple must FIRE (plurality A, IRV C, Borda B). This is the state the check is meant to reject if methods were claimed unanimous.",
   "fired_on_bad_state": true,
   "good_state_output": "SILENT on unanimous-3",
   "id": "spoiler-triple-fire",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-linux",
  "model": "opus",
  "role": "council-simulation-designer",
  "vendor": "anthropic"
 },
 "profile": "council-simulation-spec",
 "report": {
  "control_ids": [
   "unanimous-3",
   "spoiler-triple"
  ],
  "kind": "council-simulation-spec",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:115",
    "measured": 9,
    "method": "tabulator-over-declared-fixtures",
    "name": "n_fixtures"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:115",
    "measured": 5,
    "method": "tabulator-over-declared-fixtures",
    "name": "n_disagree"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:115",
    "measured": 0.5555555555555556,
    "method": "k-over-n",
    "name": "disagreement_rate"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:88",
    "measured": "approval_top2",
    "method": "demote-first-to-last-sweep",
    "name": "most_sensitive_method"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0119/simulate.py:88",
    "measured": 33,
    "method": "demote-first-to-last-sweep",
    "name": "most_sensitive_winner_changes"
   }
  ],
  "results": {
   "agreeing_fixture_ids": [
    "unanimous-3",
    "majority-clear",
    "close-plurality",
    "unanimous-4"
   ],
   "disagreeing_fixture_ids": [
    "spoiler-triple",
    "center-squeeze",
    "approval-split",
    "cycle-asymmetric",
    "score-borda-split"
   ],
   "disagreement_rate": 0.5555555555555556,
   "fixtures": [
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 7,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "unanimous-3",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "negative-control-agree",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 5,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "majority-clear",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "agree-majority",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 0,
      "borda": 2,
      "copeland_minimax": 2,
      "irv": 5,
      "plurality": 0,
      "score_5310": 2
     },
     "id": "spoiler-triple",
     "methods_disagree": true,
     "n_ballots": 13,
     "n_flips": 13,
     "role": "planted-disagreement",
     "winner_set": [
      "A",
      "B",
      "C"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "B",
      "copeland_minimax": "B",
      "irv": "C",
      "plurality": "A",
      "score_5310": "B"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 0,
      "borda": 2,
      "copeland_minimax": 2,
      "irv": 4,
      "plurality": 0,
      "score_5310": 2
     },
     "id": "center-squeeze",
     "methods_disagree": true,
     "n_ballots": 11,
     "n_flips": 11,
     "role": "disagreement",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "B",
      "copeland_minimax": "B",
      "irv": "A",
      "plurality": "A",
      "score_5310": "B"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 3,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 3,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "approval-split",
     "methods_disagree": true,
     "n_ballots": 9,
     "n_flips": 9,
     "role": "disagreement",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 4,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 4,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "close-plurality",
     "methods_disagree": false,
     "n_ballots": 7,
     "n_flips": 7,
     "role": "sensitivity",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C"
     ],
     "flip_changes": {
      "approval_top2": 3,
      "borda": 4,
      "copeland_minimax": 4,
      "irv": 3,
      "plurality": 4,
      "score_5310": 4
     },
     "id": "cycle-asymmetric",
     "methods_disagree": true,
     "n_ballots": 9,
     "n_flips": 9,
     "role": "cycle",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "B",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C",
      "D"
     ],
     "flip_changes": {
      "approval_top2": 5,
      "borda": 0,
      "copeland_minimax": 0,
      "irv": 0,
      "plurality": 0,
      "score_5310": 0
     },
     "id": "unanimous-4",
     "methods_disagree": false,
     "n_ballots": 5,
     "n_flips": 5,
     "role": "negative-control-agree",
     "winner_set": [
      "A"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "A",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    },
    {
     "candidates": [
      "A",
      "B",
      "C",
      "D"
     ],
     "flip_changes": {
      "approval_top2": 6,
      "borda": 5,
      "copeland_minimax": 6,
      "irv": 6,
      "plurality": 0,
      "score_5310": 6
     },
     "id": "score-borda-split",
     "methods_disagree": true,
     "n_ballots": 11,
     "n_flips": 11,
     "role": "ordinal-cardinal",
     "winner_set": [
      "A",
      "B"
     ],
     "winners": {
      "approval_top2": "A",
      "borda": "B",
      "copeland_minimax": "A",
      "irv": "A",
      "plurality": "A",
      "score_5310": "A"
     }
    }
   ],
   "most_sensitive": {
    "method": "approval_top2",
    "n_winner_changes": 33,
    "rate": 0.4177215189873418,
    "rule": "max n_winner_changes, then max rate, then lex-smallest method id",
    "tied_methods": [
     "approval_top2"
    ]
   },
   "n_agree": 4,
   "n_disagree": 5,
   "n_fixtures": 9,
   "sensitivity_table": [
    {
     "method": "plurality",
     "n_flips_tried": 79,
     "n_winner_changes": 12,
     "rate": 0.1518987341772152
    },
    {
     "method": "irv",
     "n_flips_tried": 79,
     "n_winner_changes": 25,
     "rate": 0.31645569620253167
    },
    {
     "method": "borda",
     "n_flips_tried": 79,
     "n_winner_changes": 21,
     "rate": 0.26582278481012656
    },
    {
     "method": "approval_top2",
     "n_flips_tried": 79,
     "n_winner_changes": 33,
     "rate": 0.4177215189873418
    },
    {
     "method": "score_5310",
     "n_flips_tried": 79,
     "n_winner_changes": 22,
     "rate": 0.27848101265822783
    },
    {
     "method": "copeland_minimax",
     "n_flips_tried": 79,
     "n_winner_changes": 22,
     "rate": 0.27848101265822783
    }
   ]
  }
 },
 "residual_unknowns": [
  {
   "claim": "CNL-0061/0062/0063 design notes are not on this tree; method semantics here are fixtures/rules.json.",
   "settling_experiment": "Place those design artifacts on disk and diff the declared IRV/approval/Copeland rules against them.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Schulze and ranked-pairs completions were not compared; Copeland-then-minimax is the declared cycle rule.",
   "settling_experiment": "Add Schulze and ranked-pairs engines and re-run the 9-fixture disagreement table.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b). Max 3 attempts."
 },
 "reviewer": {
  "independent": true,
  "notes": "Probe 2 re-tabulates every fixture with recount.py (continuing-pointer IRV and an n-by-n pairwise matrix) and must match the artifact winner table and sensitivity counts. It does not import tabulator.py.",
  "reviewer_id": "CNL-0119-probe2-pointer-irv-matrix-copeland",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0119",
 "spec_anchor": "_USER-PROMPTS.md:10746-10767; WORK-UNIT-CATALOG.json:CNL-0119",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe1_disagreement_sensitivity.py",
   "id": "probe1-disagreement-sensitivity",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
   "id": "probe2-independent-recount",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0119/probe2_independent_recount.py",
   "id": "negative-control-unanimous-silent",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:33:03Z",
  "started_at": "2026-08-24T20:40:00Z"
 },
 "unit_id": "CNL-0119"
}
