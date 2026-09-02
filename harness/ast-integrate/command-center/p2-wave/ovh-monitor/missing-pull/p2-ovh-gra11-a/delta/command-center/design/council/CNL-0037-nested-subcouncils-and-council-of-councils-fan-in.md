{
 "unit_id": "CNL-0037",
 "state": "SUCCESS",
 "sentinel": "SUCCESS:CNL-0037",
 "title": "Nested subcouncils and council-of-councils fan-in",
 "question": "When nested councils return conflicting verdicts, what is the fan-in rule - and is a parent council permitted to overrule a child whose evidence it never read?",
 "answer": "Fan-in rule FANIN-NESTED-V1: (1) each child verdict is a claim; a missing or empty artifact, or a verdict with no evidence body, normalizes to INCOMPLETE (a digest is not a receipt). (2) duplicate child_id is MALFORMED (no double-count). (3) any required INCOMPLETE child makes the parent INCOMPLETE \u2014 not a vote. (4) if remaining normalized verdicts are identical, that is the parent outcome. (5) if they conflict, the parent may overrule a named child only by citing that child's own evidence ids with matching digests AND by having ingested those evidence bodies; otherwise overrule is rejected. (6) unresolved conflict emits IRREDUCIBLE_DISAGREEMENT, a defined fan-in outcome that is not parent completion and is not a majority PASS. (7) every child dissent id is forwarded. A parent is not permitted to overrule a child whose evidence it never read: the blind fixture is rejected as BLIND_OVERRULE. Regression anchor is FC-11343 (spec 11343, nested councils disagree on completion).",
 "claim_under_test": "Conflicting child councils fan in by evidence-gated resolution or defined irreducible disagreement; a parent cannot overrule unread evidence.",
 "fan_in_rule": {
  "id": "FANIN-NESTED-V1",
  "parent_may_overrule_unread_child": false,
  "majority_of_verdict_strings": false,
  "digest_is_receipt": false,
  "irreducible_disagreement_is_defined_outcome": true,
  "irreducible_is_parent_completion": false
 },
 "declared_signal": {
  "name": "child-evidence-normalized-verdicts",
  "not": "majority-of-child-verdict-strings"
 },
 "which_stops_the_round": {
  "stops": "defined fan-in outcome: unanimous PASS/REFUTED, IRREDUCIBLE_DISAGREEMENT, INCOMPLETE, or MALFORMED",
  "does_not_stop": "majority PASS, averaged verdict, or digest-without-artifact",
  "satisfy_quota_from_padding": false
 },
 "dependency_status": {
  "CNL-0031": {
   "artifact_present": false,
   "path": "command-center/design/council/CNL-0031-flat-committee-and-caucus-grouping-when-structure-helps-an.md",
   "note": "absent on this worktree; CNL-0037 states the nesting-depth rule without inheriting their numbers"
  },
  "CNL-0071": {
   "artifact_present": false,
   "path": "command-center/design/council/CNL-0071-irreducible-disagreement-when-to-stop-trying-to-converge.md",
   "note": "absent on this worktree; CNL-0037 states the nesting-depth rule without inheriting their numbers"
  }
 },
 "catalog_inputs_on_tree": {
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": false,
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": false,
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false
 },
 "residual_unknowns": [
  "Harness-restore _USER-PROMPTS.md:11343 and command-center/phase3/A1/FAILURE-MODES.json are absent on this Linux worktree; in-tree replicas are TST-0295/seeded_classes.py (FC-11343) and CC-0024 prompt-two-slice.md:11343.",
  "CNL-0071 owns the information-gain threshold for a single council loop; this unit only requires that fan-in of already-returned children be defined.",
  "CNL-0031 owns grouping granularity (flat/committee/caucus); nesting depth is a different axis."
 ],
 "claims": [
  {
   "id": "C1",
   "claim": "Two-PASS one-REFUTED children must not fan in to PASS by majority.",
   "verdict": "CONFIRMED",
   "anchor": "command-center/p2-wave/probes/CNL-0037/fanin.py:88"
  },
  {
   "id": "C2",
   "claim": "A parent may not overrule a child whose evidence body it never ingested.",
   "verdict": "CONFIRMED",
   "anchor": "command-center/p2-wave/probes/CNL-0037/fanin.py:88"
  },
  {
   "id": "C3",
   "claim": "Disagreeing children reach IRREDUCIBLE_DISAGREEMENT, a defined non-complete outcome (FC-11343).",
   "verdict": "CONFIRMED",
   "anchor": "command-center/p2-wave/probes/TST-0295/seeded_classes.py:60"
  }
 ],
 "evidence": [
  {
   "path": "command-center/p2-wave/probes/TST-0295/seeded_classes.py",
   "line": 60,
   "snippet": "FC-11343",
   "kind": "fixture-replica",
   "claim": "Spec 11343 is recorded in-tree as FC-11343 (FAILURE-MODES.json absent on this worktree)."
  },
  {
   "path": "command-center/p2-wave/probes/TST-0295/seeded_classes.py",
   "line": 60,
   "snippet": "nested councils disagree on completion",
   "kind": "fixture-replica",
   "claim": "Failure-mode name matches the catalog evidence requirement."
  },
  {
   "path": "command-center/p2-wave/probes/CC-0024/fixtures/prompt-two-slice.md",
   "line": 11343,
   "snippet": "nested councils disagree on completion",
   "kind": "spec-replica",
   "claim": "Recovered prompt slice keeps original line 11343 of the nested-completion failure class."
  },
  {
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "line": 36108,
   "snippet": "nested councils disagree on completion",
   "kind": "catalog-anchor",
   "claim": "CNL-0037 evidence requirement cites _USER-PROMPTS.md:11343."
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0037/fanin.py",
   "line": 88,
   "snippet": "BLIND_OVERRULE",
   "kind": "live-tree",
   "claim": "Blind overrule is a named rejection, not a silent parent PASS.",
   "verbatim_output": "negative-control target=overrule-blind overrule.accepted=False overrule.reason=BLIND_OVERRULE outcome=IRREDUCIBLE_DISAGREEMENT parent_complete=False"
  }
 ],
 "tests": [
  {
   "id": "probe1",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0037/probe1_disagreeing_children.py",
   "result": "PASS"
  },
  {
   "id": "probe2",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0037/probe2_overrule_evidence.py",
   "result": "PASS"
  }
 ],
 "measured_fixtures": {
  "agreeing_pass": {
   "outcome": "PASS",
   "parent_complete": true
  },
  "disagree_irreducible": {
   "outcome": "IRREDUCIBLE_DISAGREEMENT",
   "parent_complete": false,
   "fan_in_defined": true,
   "forwarded_dissent_ids": [
    "dissent-gamma-1"
   ]
  },
  "majority_trap": {
   "outcome": "IRREDUCIBLE_DISAGREEMENT",
   "parent_complete": false,
   "majority_would_pass": true
  },
  "overrule_cited": {
   "outcome": "PASS",
   "overrule_accepted": true,
   "forwarded_dissent_ids": [
    "dissent-gamma-1"
   ]
  },
  "overrule_blind": {
   "outcome": "IRREDUCIBLE_DISAGREEMENT",
   "overrule_accepted": false,
   "overrule_reason": "BLIND_OVERRULE"
  },
  "claim_without_artifact": {
   "outcome": "INCOMPLETE",
   "parent_complete": false
  },
  "completion_split": {
   "outcome": "IRREDUCIBLE_DISAGREEMENT",
   "parent_complete": false
  }
 },
 "negative_controls": [
  {
   "id": "NC-blind-overrule",
   "rejects": "parent overrule that cites a child evidence id/digest copied from the header without ingesting the evidence body",
   "verbatim": "negative-control target=overrule-blind overrule.accepted=False overrule.reason=BLIND_OVERRULE outcome=IRREDUCIBLE_DISAGREEMENT parent_complete=False"
  }
 ],
 "reviewer": {
  "reviewer_id": "CNL-0037-adversarial-blind-overrule",
  "verdict": "PASS",
  "independent": true,
  "scope_not_agreement": true,
  "re_ran_both_states": true,
  "counterexample_instance": {
   "id": "overrule-blind",
   "shape": "parent copies child evidence id+digest from the header and emits new_verdict=PASS without ingesting the evidence body",
   "observed_outcome": "IRREDUCIBLE_DISAGREEMENT",
   "observed_overrule_reason": "BLIND_OVERRULE",
   "rejected": true
  },
  "refuted_not_attempted": false
 },
 "strongest_surviving_counterargument": "A parent that copies evidence ids from a child header might claim it cited the child without reading the body. FANIN-NESTED-V1 rejects that as BLIND_OVERRULE unless the parent ingested the matching body. Residual risk: an implementation could treat header-copy as ingest; the probe's parent_ingested map is the mechanical distinction.",
 "artifacts": [
  {
   "path": "command-center/design/council/CNL-0037-nested-subcouncils-and-council-of-councils-fan-in.md",
   "exists": true,
   "role": "primary"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0037/fanin.py",
   "exists": true,
   "role": "supporting"
  },
  {
   "path": "command-center/schema/council-design-note.schema.json",
   "exists": true,
   "role": "supporting"
  },
  {
   "path": "command-center/p2-wave/probes/CNL-0037/note.schema.json",
   "exists": true,
   "role": "supporting"
  }
 ],
 "ts": "2026-08-25T00:56:51Z"
}
