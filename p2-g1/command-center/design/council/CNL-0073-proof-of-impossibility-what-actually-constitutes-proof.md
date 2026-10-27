{
 "answer": "proof_of_impossibility == true is discharged only by a closed-world exhaustive refutation: a finite named universe, a mechanical membership predicate on disk bytes, a visit receipt for every member, set-equality between universe and visited (checked by sequential walk AND by set difference), a named settling experiment, and a negative existence result on every member. The claimed flag is recorded then ignored. A searched-but-not-exhaustive log is classified UNSUCCESSFUL_SEARCH even when unread members happen to also lack a witness, so 'we could not find it' cannot be recorded as 'it cannot be found'. Attempt-limit termination is GAVE_UP on a distinct path from EXHAUSTIVE_REFUTATION. SUCCESS:CNL-0073",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0073-proof-of-impossibility-what-actually-constitutes-proof.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0073/design-note.schema.json",
   "role": "unit-schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0073/proof.py",
   "role": "detector"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0073/reviewer.py",
   "role": "independent-recount"
  }
 ],
 "both_states": {
  "author_reviewer_agree": "author-walk-and-reviewer-set-difference-agree",
  "both_directions_ok": true,
  "exhaustive_classification": "EXHAUSTIVE_REFUTATION",
  "exhaustive_fixture": "exhaustive",
  "exhaustive_qualifies": true,
  "exhaustive_unvisited_count": 0,
  "gave_up_classification": "GAVE_UP",
  "gave_up_distinct_from_proof": true,
  "incomplete_classification": "UNSUCCESSFUL_SEARCH",
  "incomplete_fixture": "incomplete-luck",
  "incomplete_qualifies": false,
  "incomplete_unread_also_lacks_witness": true,
  "incomplete_unvisited": [
   "d.txt",
   "e.txt"
  ],
  "incomplete_unvisited_count": 2,
  "missed_fixture_classification": "UNSUCCESSFUL_SEARCH",
  "missed_unread_has_witness": true
 },
 "claim_under_test": "An unsuccessful search ('we could not find it') may be recorded as proof_of_impossibility == true and stop the round.",
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/proof.py:129",
   "claim": "The class of evidence that discharges proof_of_impossibility == true is a closed-world exhaustive refutation, not an unsuccessful search.",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/proof.py:149",
   "claim": "'We could not find it' is prevented from being recorded as 'it cannot be found' because incompleteness classifies as UNSUCCESSFUL_SEARCH even when the unread remainder is clean.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/proof.py:21",
   "claim": "Gave-up (attempt limit) and proved-impossible do not share a classification or a qualifies=true path.",
   "id": "C3",
   "verdict": "CONFIRMED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0073",
 "declared_signal": {
  "claimed_flag_ignored": true,
  "name": "closed-world-exhaustiveness",
  "predicate": "file bytes contain WITNESS",
  "set_difference": "set(universe) - set(visited) must be empty",
  "walk": "sequential membership of every universe member in visited"
 },
 "dependency_cnl_0083": {
  "note": "CNL-0083 binds this evidence class to the executable expression proof_of_impossibility == true. This unit defines the class; it does not claim the evaluator schema is already on disk.",
  "present_on_this_worktree": false,
  "required_by_catalog": true
 },
 "discharge_class": "closed-world-exhaustive-refutation",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/proof.py:129",
   "claim": "Exhaustive enumeration of a closed universe with no WITNESS discharges proof_of_impossibility.",
   "kind": "detector-rule",
   "line": 129,
   "mechanism": "sequential-walk",
   "path": "command-center/p2-wave/probes/CNL-0073/proof.py",
   "snippet": "RULE-EXHAUSTIVENESS: unvisited must be empty",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/proof.py:149",
   "claim": "A searched-but-not-exhaustive log cannot discharge the flag, including the lucky-true remainder.",
   "kind": "detector-rule",
   "line": 149,
   "mechanism": "sequential-walk",
   "path": "command-center/p2-wave/probes/CNL-0073/proof.py",
   "snippet": "RULE-NO-LAUNDER: unsuccessful search never discharges proof_of_impossibility",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0073/reviewer.py:3",
   "claim": "Independent set-difference recount agrees with the walk on all four fixtures.",
   "kind": "independent-recount",
   "line": 3,
   "mechanism": "set-difference",
   "path": "command-center/p2-wave/probes/CNL-0073/reviewer.py",
   "snippet": "Does not call proof.qualify or proof.walk_unvisited",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:37914",
   "claim": "Catalog question names proof_of_impossibility == true as a required stopping expression.",
   "kind": "catalog",
   "line": 37914,
   "mechanism": "catalog-citation",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "One required stopping expression is proof_of_impossibility == true",
   "verdict": "CONFIRMED"
  }
 ],
 "kind": "council-design-note",
 "markdown_body": "# Proof of impossibility: what actually constitutes proof\n\nOne required stopping expression is proof_of_impossibility == true - what class of evidence discharges it, and how is 'we could not find it' prevented from being recorded as 'it cannot be found'?\n\nproof_of_impossibility == true is discharged only by a closed-world exhaustive refutation: a finite named universe, a mechanical membership predicate on disk bytes, a visit receipt for every member, set-equality between universe and visited (checked by sequential walk AND by set difference), a named settling experiment, and a negative existence result on every member. The claimed flag is recorded then ignored. A searched-but-not-exhaustive log is classified UNSUCCESSFUL_SEARCH even when unread members happen to also lack a witness, so 'we could not find it' cannot be recorded as 'it cannot be found'. Attempt-limit termination is GAVE_UP on a distinct path from EXHAUSTIVE_REFUTATION. SUCCESS:CNL-0073\n",
 "negative_controls": [
  {
   "fixture": "incomplete-luck",
   "id": "NC-unsuccessful-search-is-not-proof",
   "observed": "qualifies=False classification=UNSUCCESSFUL_SEARCH unvisited=['d.txt', 'e.txt'] omniscient_witness_in_unvisited=False",
   "rejects": "searched-but-not-exhaustive recorded as proof_of_impossibility",
   "verbatim": "qualifies=False classification=UNSUCCESSFUL_SEARCH unvisited=['d.txt', 'e.txt'] omniscient_witness_in_unvisited=False",
   "what_the_check_does": "On incomplete-luck the detector returns qualifies=false and classification=UNSUCCESSFUL_SEARCH even though unread members also lack WITNESS, so a true-by-luck remainder cannot discharge proof_of_impossibility."
  }
 ],
 "non_discharge_classes": [
  "UNSUCCESSFUL_SEARCH",
  "GAVE_UP",
  "COUNTEREXAMPLE_FOUND",
  "OPEN_WORLD",
  "MALFORMED"
 ],
 "proof_rule": {
  "claimed_flag_cannot_self_certify": true,
  "existence_predicate": "file_contains_WITNESS",
  "gave_up_distinct_from_proof": true,
  "mechanisms": [
   "sequential-walk",
   "set-difference"
  ],
  "settling_experiment_required": true,
  "universe_must_be_closed_and_finite": true,
  "visited_must_equal_universe": true
 },
 "question": "One required stopping expression is proof_of_impossibility == true - what class of evidence discharges it, and how is 'we could not find it' prevented from being recorded as 'it cannot be found'?",
 "reviewer": {
  "agree_with_author": "author-walk-and-reviewer-set-difference-agree",
  "independent": true,
  "mechanism": "set-difference",
  "re_ran_both_states": true,
  "reviewer_id": "CNL-0073-probe2-set-difference",
  "role": "cross-vendor both-states re-runner",
  "vendor": "openai",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0073",
 "source_availability": {
  "council_specification_schema_v1": false,
  "harness_restore_user_prompts": false,
  "note": "Catalog inputs cite C:/Users/Prekzursil/.claude/harness-restore-20260806 which is absent on this Linux worktree. The question, tests_required, and stopping-expression name are taken from WORK-UNIT-CATALOG.json."
 },
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "Exhaustiveness proves impossibility only inside the named closed universe. If that universe was drawn too small, the proof is conditional on a bad frame, not on the open world. The detector does not certify that the universe itself is the right one; it only refuses to treat an incomplete search of a declared universe as proof.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0073/probe1_both_states.py",
   "expect": "incomplete-luck FAIL to qualify; exhaustive PASS; both directions",
   "id": "T1-both-states",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0073/probe2_reviewer.py",
   "expect": "independent set-difference re-run of both-states before sign-off",
   "id": "T2-reviewer-rerun",
   "result": "PASS"
  }
 ],
 "title": "Proof of impossibility: what actually constitutes proof",
 "ts": "2026-08-25T00:52:55Z",
 "unit_id": "CNL-0073",
 "which_stops_the_round": {
  "does_not_stop": "UNSUCCESSFUL_SEARCH or GAVE_UP, including a lucky-true unread remainder",
  "satisfy_quota_from_padding": false,
  "stops": "EXHAUSTIVE_REFUTATION (closed universe, visited==universe, no WITNESS)"
 }
}
