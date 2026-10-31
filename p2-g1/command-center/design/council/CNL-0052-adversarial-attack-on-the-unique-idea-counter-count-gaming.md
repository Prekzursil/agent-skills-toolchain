{
 "$schema": "command-center/schema/council-detector-spec.schema.json",
 "unit_id": "CNL-0052",
 "state": "SUCCESS",
 "sentinel": "SUCCESS:CNL-0052",
 "detector_id": "F01",
 "title": "Adversarial attack on the unique-idea counter (count gaming)",
 "question": "Acting as an adversary paid per idea, what is the cheapest sequence of trivial variants that inflates the unique-idea count past 100 while adding no information - and does the F01 counter survive that attack?",
 "claim_under_test": "A cheapest trivial-variant sequence can inflate a string-equality unique-idea counter past 100 with no new information, reproducing _USER-PROMPTS.md:11339; F01 (Jaccard OR folded mechanism key) collapses that corpus to a unique count of 1 and therefore survives.",
 "named_failure": {
  "cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11339",
  "description": "A 100-idea brainstorm satisfies the unique-idea count with trivial wording variants.",
  "reproduced": true,
  "naive_unique": 100,
  "naive_gate_ge_100": true
 },
 "f01": {
  "implemented_at": "command-center/p2-wave/probes/CNL-0052/f01.py",
  "note": "CNL-0051's design artifact is absent on this tree. F01 under test is the two-signal operationalization named by CNL-0051 (lexical Jaccard plus a corroborating mechanism key), local to this attack unit. IMP-0300 remains the production port.",
  "s1": "raw-token Jaccard >= 0.50 (no synonym fold)",
  "s2": "folded mechanism-key equality (synonym table + stem + number strip)",
  "merge_rule": "OR: merge if S1 or S2 fires",
  "jaccard_threshold": 0.5,
  "rename_jaccard": 0.8
 },
 "attack": {
  "executed": true,
  "id": "suffix-integer",
  "sequence": [
   "Start from one seed mechanism sentence.",
   "For i in 1..99 append a unique integer token (one extra token, no new mechanism).",
   "Submit the 100 strings to the unique-idea counter."
  ],
  "extra_tokens": 99,
  "information_added": 0,
  "naive_unique": 100,
  "jaccard_only_unique": 1,
  "f01_unique": 1,
  "f01_connected_components_unique": 1,
  "naive_gate_ge_100": true,
  "f01_gate_ge_100": false,
  "f01_survives": true,
  "result_number": 1,
  "mixed_seed_and_rewrite": {
   "naive_unique": 100,
   "jaccard_only_unique": 2,
   "f01_unique": 1,
   "jaccard_only_splits_rewrite": true,
   "f01_collapses_rewrite": true
  },
  "all_attacks": [
   {
    "name": "suffix-integer",
    "n_rows": 100,
    "extra_tokens": 99,
    "naive_unique": 100,
    "jaccard_only_unique": 1,
    "f01_union_find_unique": 1,
    "f01_connected_components_unique": 1,
    "algorithms_agree": true,
    "naive_gate_ge_100": true,
    "f01_gate_ge_100": false
   },
   {
    "name": "synonym-rotate",
    "n_rows": 100,
    "extra_tokens": 100,
    "naive_unique": 100,
    "jaccard_only_unique": 1,
    "f01_union_find_unique": 1,
    "f01_connected_components_unique": 1,
    "algorithms_agree": true,
    "naive_gate_ge_100": true,
    "f01_gate_ge_100": false
   },
   {
    "name": "one-parameter-ttl",
    "n_rows": 100,
    "extra_tokens": 100,
    "naive_unique": 100,
    "jaccard_only_unique": 1,
    "f01_union_find_unique": 1,
    "f01_connected_components_unique": 1,
    "algorithms_agree": true,
    "naive_gate_ge_100": true,
    "f01_gate_ge_100": false
   },
   {
    "name": "full-rewrite-in-vocab",
    "n_rows": 100,
    "extra_tokens": 99,
    "naive_unique": 100,
    "jaccard_only_unique": 1,
    "f01_union_find_unique": 1,
    "f01_connected_components_unique": 1,
    "algorithms_agree": true,
    "naive_gate_ge_100": true,
    "f01_gate_ge_100": false
   },
   {
    "name": "mixed-seed-and-rewrite",
    "n_rows": 100,
    "extra_tokens": 98,
    "naive_unique": 100,
    "jaccard_only_unique": 2,
    "f01_union_find_unique": 1,
    "f01_connected_components_unique": 1,
    "algorithms_agree": true,
    "naive_gate_ge_100": true,
    "f01_gate_ge_100": false
   }
  ]
 },
 "answer": "Cheapest sequence: suffix-integer (99 extra tokens). Naive unique=100 (gate unique_ideas>=100 PASSES \u2014 :11339 reproduced). F01 unique=1 (gate FAILS). F01 survives. Jaccard-only on a mixed seed+rewrite corpus unique=2; F01 still unique=1. SUCCESS:CNL-0052",
 "negative_control": {
  "reject_state": "100 trivial suffix variants of one seed counted as 100 unique ideas by string equality (the :11339 count-gaming failure)",
  "observed": "F01 unique_count=1; unique_ideas>=100 is False",
  "verbatim": "reject_state=100 suffix-variants of one seed; naive_unique=100 naive_gate_ge_100=True; f01_unique=1 f01_gate_ge_100=False"
 },
 "both_states": {
  "planted_bad": {
   "fixture": "suffix-integer x100",
   "f01_unique": 1,
   "f01_gate_ge_100": false,
   "fires_reject": true,
   "verbatim": "reject_state=100 suffix-variants of one seed; naive_unique=100 naive_gate_ge_100=True; f01_unique=1 f01_gate_ge_100=False"
  },
  "known_good": {
   "fixture": "distinct-100",
   "f01_unique": 100,
   "f01_gate_ge_100": true,
   "silent_accept": true,
   "verbatim": "known_good=100 distinct mechanisms; f01_unique=100 f01_gate_ge_100=True"
  }
 },
 "distinct_audit": {
  "n": 100,
  "max_jaccard": 0.25,
  "max_jaccard_pair": [
   79,
   81,
   0.25
  ],
  "key_collisions": 0,
  "unique_keys": 100,
  "below_threshold": true
 },
 "residual": "An out-of-vocabulary full rewrite whose token Jaccard drops below 0.5 and whose folded mechanism key is not in the synonym table will still increment F01. That class is NOT-CHECKED here beyond the in-vocabulary rewrite attack.",
 "required_fix": null,
 "adv_rebuild_circle": false,
 "tests": [
  {
   "id": "T1-attack-executed",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0052/probe1_execute_attack.py",
   "result": "PASS"
  },
  {
   "id": "T2-negative-control-and-reviewer-both-states",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0052/probe2_reviewer_rerun.py",
   "result": "PASS"
  }
 ],
 "reviewer": {
  "reviewer_id": "CNL-0052-probe2-connected-components",
  "vendor_role": "openai/gpt-5-codex",
  "verdict": "PASS",
  "independent": true,
  "executed_both_states": true,
  "scope_not_agreement": true,
  "method": "Re-clustered the planted-bad suffix corpus and the known-good 100-distinct corpus with BFS connected components on the same S1-OR-S2 predicates, without reading the author's union-find counts as authority. Agreement is on the number, not the prose.",
  "bad_unique": 1,
  "good_unique": 100
 },
 "evidence": [
  {
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "line": 36870,
   "snippet": "100-idea brainstorm satisfies the count with trivial wording variants",
   "kind": "catalog",
   "claim": "Named failure :11339 (trivial wording variants satisfy a 100-idea count) is the failure this unit must reproduce before claiming a defense."
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0052/f01.py",
   "line": 7,
   "snippet": "token-set Jaccard >= JACCARD_THRESHOLD",
   "kind": "live-tree",
   "claim": "S1 is raw-token Jaccard, mechanically different from S2's folded mechanism key."
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0052/f01.py",
   "line": 8,
   "snippet": "canonical mechanism keys are equal after stopword drop",
   "kind": "live-tree",
   "claim": "S2 folds synonyms then compares canonical mechanism keys, catching full in-vocab rewrites Jaccard misses."
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0052/attack.py",
   "line": 136,
   "snippet": "Cheapest attack: one extra integer token per extra 'idea'.",
   "kind": "live-tree",
   "claim": "The cheapest executed sequence is suffix-integer: 99 extra tokens, zero new mechanisms."
  }
 ],
 "artifacts": [
  {
   "path": "command-center/design/council/CNL-0052-adversarial-attack-on-the-unique-idea-counter-count-gaming.md",
   "exists": true,
   "role": "primary"
  },
  {
   "path": "command-center/schema/council-detector-spec.schema.json",
   "exists": true,
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0052/f01.py",
   "exists": true,
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0052/attack.py",
   "exists": true,
   "role": "supporting"
  }
 ],
 "named_probes": [
  {
   "id": "probe1",
   "role": "execute-attack",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0052/probe1_execute_attack.py"
  },
  {
   "id": "probe2",
   "role": "independent-both-states",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0052/probe2_reviewer_rerun.py"
  }
 ],
 "ts": "2026-08-25T00:53:54Z"
}
