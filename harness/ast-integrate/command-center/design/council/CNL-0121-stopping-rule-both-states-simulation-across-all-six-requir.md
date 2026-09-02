{
 "answer": "Yes for all six expressions on this harness: 6 FIRE cells on the true fixtures and 6 SILENT cells on the false fixtures. See outcome_table. AND does not fire when only one conjunct is true, nor when a conjunct is NOT-CHECKED. proof_of_impossibility does not fire on an unsuccessful search. SUCCESS:CNL-0121",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0121-stopping-rule-both-states-simulation-across-all-six-requir.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-simulation-spec.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0121/fixtures/catalog.json",
   "role": "supporting"
  }
 ],
 "claim_under_test": "Each of the six spec-named stopping expressions FIRES on a fixture that makes it true and stays SILENT on a fixture that makes it false. The answer is the 6x2 table, not a summary sentence.",
 "completion_sentinel": "SUCCESS:CNL-0121",
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0121-stopping-rule-both-states-simulation-across-all-six-requir.md",
   "consumer": "probe1_six_by_two.py",
   "executed": true,
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
   "claim": "All twelve 6x2 cells are populated; true fixtures FIRE; false fixtures SILENT.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
   "signal": "parser-eval",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0121/probe2_negative_and_recount.py",
   "claim": "Independent direct predicates recount the same 12 outcomes; an AND-as-OR mutant fires on the partial-AND fixture while the real evaluator stays SILENT or NOT-CHECKED.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe2_negative_and_recount.py",
   "signal": "direct-recount-plus-mutant",
   "verdict": "CONFIRMED"
  }
 ],
 "expressions": [
  {
   "expression": "unique_ideas >= 100 AND completeness_score >= 0.90",
   "id": "E1",
   "source_unit": "CNL-0078"
  },
  {
   "expression": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
   "id": "E2",
   "source_unit": "CNL-0079"
  },
  {
   "expression": "unanimity == true OR max_rounds == 12",
   "id": "E3",
   "source_unit": "CNL-0080"
  },
  {
   "expression": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
   "id": "E4",
   "source_unit": "CNL-0081"
  },
  {
   "expression": "evidence_saturation == true OR time_minutes >= 180",
   "id": "E5",
   "source_unit": "CNL-0082"
  },
  {
   "expression": "proof_of_impossibility == true",
   "id": "E6",
   "source_unit": "CNL-0083"
  }
 ],
 "format_note": "Catalog output_path ends in .md; body is JSON so G-1 can json.loads it. Catalog shim $ref is not fetched on this host; CONTRACT_SCHEMA is the live probe contract. SUCCESS:CNL-0121",
 "harness": {
  "description": "Each fixture is an end-of-round council metric snapshot. No live LLM participants. Stopping expressions are evaluated against those snapshots. CNL-0117 is not on this worktree; this unit supplies the minimum deterministic substrate needed to answer the 6x2 question.",
  "deterministic": true,
  "kind": "scripted-metric-snapshots"
 },
 "manifest_registration": {
  "manifest_path": "command-center/p2-wave/probes/CNL-0121/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "id": "and-one-false",
   "observed": "SILENT",
   "rejects": "AND with one conjunct true and one false must not fire (AND-as-OR trap).",
   "verbatim": "NEG and-one-false: real=SILENT eval=False mutant_and_as_or=FIRE mutant_eval=True metrics={\"completeness_score\": 0.4, \"unique_ideas\": 150}"
  },
  {
   "id": "and-missing-conjunct",
   "observed": "NOT-CHECKED",
   "rejects": "completeness_score absent is NOT-CHECKED; AND must not fire under partial evidence.",
   "verbatim": "NEG and-missing-conjunct: real=NOT-CHECKED eval=None mutant_and_as_or=FIRE mutant_eval=True metrics={\"unique_ideas\": 150}"
  },
  {
   "id": "unsuccessful-search",
   "observed": "SILENT",
   "rejects": "Failed search must not bind proof_of_impossibility true.",
   "verbatim": "NEG unsuccessful-search: real=SILENT eval=False search_log_attempts=40 hits=0 planted_true_would=FIRE note=Failed search must not bind proof_of_impossibility true."
  },
  {
   "id": "vacuous-always-fire",
   "observed": "SILENT",
   "rejects": "A detector that fires on every fixture (true and false) measures nothing.",
   "verbatim": "NEG vacuous-always-fire: mutant would FIRE on all 6 false fixtures; real evaluator SILENT on 6/6 false fixtures"
  }
 ],
 "outcome_table": {
  "cell_count": 12,
  "populated_cells": 12,
  "rows": [
   {
    "expression": "unique_ideas >= 100 AND completeness_score >= 0.90",
    "expression_id": "E1",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E1-false.json",
     "observed": "SILENT",
     "verbatim": "E1 false: expected=SILENT observed=SILENT eval=False fixture=E1-false.json metrics={\"completeness_score\": 0.4, \"proof_of_impossibility\": false, \"unique_ideas\": 12}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0078",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E1-true.json",
     "observed": "FIRE",
     "verbatim": "E1 true: expected=FIRE observed=FIRE eval=True fixture=E1-true.json metrics={\"completeness_score\": 0.95, \"proof_of_impossibility\": false, \"unique_ideas\": 120}",
     "verdict": "PASS"
    }
   },
   {
    "expression": "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "expression_id": "E2",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E2-false.json",
     "observed": "SILENT",
     "verbatim": "E2 false: expected=SILENT observed=SILENT eval=False fixture=E2-false.json metrics={\"consensus\": 0.4, \"no_new_objection_rounds\": 0, \"proof_of_impossibility\": false}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0079",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E2-true.json",
     "observed": "FIRE",
     "verbatim": "E2 true: expected=FIRE observed=FIRE eval=True fixture=E2-true.json metrics={\"consensus\": 0.97, \"no_new_objection_rounds\": 3, \"proof_of_impossibility\": false}",
     "verdict": "PASS"
    }
   },
   {
    "expression": "unanimity == true OR max_rounds == 12",
    "expression_id": "E3",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E3-false.json",
     "observed": "SILENT",
     "verbatim": "E3 false: expected=SILENT observed=SILENT eval=False fixture=E3-false.json metrics={\"max_rounds\": 5, \"proof_of_impossibility\": false, \"unanimity\": false}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0080",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E3-true.json",
     "observed": "FIRE",
     "verbatim": "E3 true: expected=FIRE observed=FIRE eval=True fixture=E3-true.json metrics={\"max_rounds\": 5, \"proof_of_impossibility\": false, \"unanimity\": true}",
     "verdict": "PASS"
    }
   },
   {
    "expression": "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "expression_id": "E4",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E4-false.json",
     "observed": "SILENT",
     "verbatim": "E4 false: expected=SILENT observed=SILENT eval=False fixture=E4-false.json metrics={\"proof_of_impossibility\": false, \"quality_gate\": \"FAIL\", \"unresolved_load_bearing_counterexample\": 2}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0081",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E4-true.json",
     "observed": "FIRE",
     "verbatim": "E4 true: expected=FIRE observed=FIRE eval=True fixture=E4-true.json metrics={\"proof_of_impossibility\": false, \"quality_gate\": \"PASS\", \"unresolved_load_bearing_counterexample\": 0}",
     "verdict": "PASS"
    }
   },
   {
    "expression": "evidence_saturation == true OR time_minutes >= 180",
    "expression_id": "E5",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E5-false.json",
     "observed": "SILENT",
     "verbatim": "E5 false: expected=SILENT observed=SILENT eval=False fixture=E5-false.json metrics={\"evidence_saturation\": false, \"proof_of_impossibility\": false, \"time_minutes\": 20}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0082",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E5-true.json",
     "observed": "FIRE",
     "verbatim": "E5 true: expected=FIRE observed=FIRE eval=True fixture=E5-true.json metrics={\"evidence_saturation\": true, \"proof_of_impossibility\": false, \"time_minutes\": 20}",
     "verdict": "PASS"
    }
   },
   {
    "expression": "proof_of_impossibility == true",
    "expression_id": "E6",
    "false_state": {
     "expected": "SILENT",
     "fixture": "E6-false.json",
     "observed": "SILENT",
     "verbatim": "E6 false: expected=SILENT observed=SILENT eval=False fixture=E6-false.json metrics={\"proof_of_impossibility\": false}",
     "verdict": "PASS"
    },
    "source_unit": "CNL-0083",
    "true_state": {
     "expected": "FIRE",
     "fixture": "E6-true.json",
     "observed": "FIRE",
     "verbatim": "E6 true: expected=FIRE observed=FIRE eval=True fixture=E6-true.json metrics={\"proof_of_impossibility\": true}",
     "verdict": "PASS"
    }
   }
  ],
  "unpopulated_cells": 0
 },
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-simulation-designer",
  "vendor": "xai"
 },
 "question": "For each of the six required stopping expressions, does it fire exactly when true and never when false \u2014 reported as a 6\u00d72 outcome table rather than a summary sentence?",
 "report": {
  "control_ids": [
   "and-one-false",
   "and-missing-conjunct",
   "unsuccessful-search",
   "vacuous-always-fire"
  ],
  "kind": "council-simulation-spec",
  "observations": [
   {
    "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
    "measured": 6,
    "method": "parser-eval-plus-direct-recount",
    "name": "fire_on_true"
   },
   {
    "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
    "measured": 6,
    "method": "parser-eval-plus-direct-recount",
    "name": "silent_on_false"
   }
  ]
 },
 "residual_unknowns": [
  {
   "claim": "Byte-identity against a CNL-0117 scripted-participant harness, if that unit later ships on this worktree.",
   "settling_experiment": "Replay the six true/false snapshots through CNL-0117 and diff stop decisions.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "up to 3 attempts, each with a MECHANICALLY DIFFERENT oracle (scripted-participant replay, transcript diff, counter assertion)"
 },
 "reviewer": {
  "independent": true,
  "method": "Re-tabulated all 12 cells from fixtures using direct.py (per-id predicates, no lexer). Parser table must match. Disagreement blocks the unit.",
  "reviewer_id": "CNL-0121-direct-predicate-recount",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0121",
 "spec_anchor": "WORK-UNIT-CATALOG.json titles CNL-0078..CNL-0083 (on-tree stand-in for _USER-PROMPTS.md:10937-10942, which is not on this worktree)",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe1_six_by_two.py",
   "id": "T1-six-by-two-verbatim-cells",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0121/probe2_negative_and_recount.py",
   "id": "T2-negative-control-and-recount",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:55:45Z",
  "started_at": "2026-08-25T00:55:45Z"
 },
 "unit_id": "CNL-0121"
}
