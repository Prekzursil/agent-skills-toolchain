{
 "answer": {
  "what_is_recorded_per_round": "One confidence_statement per (participant, proposition, round). The statement freezes stated_confidence in [0,1] as P(proposition is true), the frozen proposition_text, the vote (which is NOT the prediction), and a resolution_binding that names how a later observable will settle the proposition. The confidence trajectory is that time-ordered list. A later calibration report must be computable from trajectory.json plus a later resolution document; it must not require the original session process or directory.",
  "what_settles_correctness": "A named resolution source declared at record time: EXTERNAL_OBSERVABLE, OWNER_ATTESTED_OUTCOME, or AUDIT_REPLAY. Most council decisions have no ground truth for months: those runs stay PENDING until the binding's observable is recorded, or they are UNSCOREABLE if no binding was declared. The council's own later vote, elapsed silence, and self-reported correctness are forbidden settlers. A run with no resolvable outcome is UNSCOREABLE and is excluded from the calibration population; it is never given a Brier of 0."
 },
 "catalog_anchors": {
  "deferred_test_line": 37966,
  "id_line": 37951,
  "question_line": 37962,
  "score_classify_line": 76,
  "score_run_line": 144,
  "unscoreable_test_line": 37967
 },
 "completion": "SUCCESS:CNL-0074",
 "dependencies_note": "Catalog lists CNL-0069 (what number is 0.95 consensus). That number is a stopping-gate metric. This unit's record is stated_confidence versus a later observable, which does not wait on the consensus definition.",
 "emitted_at": "2026-08-25T00:26:10Z",
 "evidence": [
  {
   "claim": "Unit question requires a per-round record that later calibration can score against a named resolution source.",
   "line": 37962,
   "mechanism": "catalog-file-line",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "signal": 1,
   "snippet": "\"question_or_target\": \"What is recorded per round so that a calibration report can later ask whether stated confidence tracked correctness - and what resolution"
  },
  {
   "claim": "tests_required includes a deferred-resolution fixture scoreable without the original session.",
   "line": 37966,
   "mechanism": "catalog-file-line",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "signal": 1,
   "snippet": "\"a deferred-resolution fixture: the record must remain scoreable after the fact without the original session\","
  },
  {
   "claim": "tests_required: no resolvable outcome must be UNSCOREABLE, not counted as calibrated.",
   "line": 37967,
   "mechanism": "catalog-file-line",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "signal": 1,
   "snippet": "\"a council with no resolvable outcome must be marked UNSCOREABLE rather than counted as calibrated\","
  },
  {
   "claim": "Author classifier marks missing/forbidden source_class as UNSCOREABLE before any Brier is computed.",
   "line": 76,
   "mechanism": "implementation-file-line",
   "path": "command-center/p2-wave/probes/CNL-0074/score.py",
   "signal": 1,
   "snippet": "def classify_statement("
  },
  {
   "claim": "Independent recount uses set-membership status and expanded Brier p*p+y*y-2py, not the author's (p-y)**2 path.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe2_unscoreable_negative.py",
   "line": 36,
   "mechanism": "reproducible-command-independent-recount",
   "path": "command-center/p2-wave/probes/CNL-0074/recount.py",
   "signal": 2,
   "snippet": "def _expanded_brier(p: float, y: int) -> float:"
  },
  {
   "claim": "Deferred scoring copies only trajectory.json and resolution.json; session/ is absent.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py",
   "line": 35,
   "mechanism": "reproducible-command-session-absent",
   "path": "command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py",
   "signal": 2,
   "snippet": "session_dir = dest / \"session\""
  }
 ],
 "fixture_tabulation": {
  "deferred_scoreable": {
   "mean_brier": 0.22999999999999998,
   "mean_log_score": -0.6459806598020456,
   "n_pending": 0,
   "n_rejected_resolution": 0,
   "n_resolved": 3,
   "n_statements": 3,
   "n_unscoreable": 0,
   "not_yet_meaningful": true,
   "statuses": [
    "RESOLVED",
    "RESOLVED",
    "RESOLVED"
   ]
  },
  "hand_brier_deferred": {
   "alice": 0.03999999999999998,
   "bob": 0.16000000000000003,
   "cara": 0.48999999999999994,
   "mean": 0.22999999999999998
  },
  "mismatch_source": {
   "mean_brier": null,
   "mean_log_score": null,
   "n_pending": 0,
   "n_rejected_resolution": 1,
   "n_resolved": 0,
   "n_statements": 1,
   "n_unscoreable": 0,
   "not_yet_meaningful": true,
   "statuses": [
    "REJECTED_RESOLUTION"
   ]
  },
  "pending": {
   "mean_brier": null,
   "mean_log_score": null,
   "n_pending": 1,
   "n_rejected_resolution": 0,
   "n_resolved": 0,
   "n_statements": 1,
   "n_unscoreable": 0,
   "not_yet_meaningful": true,
   "statuses": [
    "PENDING"
   ]
  },
  "unscoreable": {
   "mean_brier": null,
   "mean_log_score": null,
   "n_pending": 0,
   "n_rejected_resolution": 0,
   "n_resolved": 0,
   "n_statements": 2,
   "n_unscoreable": 2,
   "not_yet_meaningful": true,
   "statuses": [
    "UNSCOREABLE",
    "UNSCOREABLE"
   ]
  }
 },
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py",
   "id": "probe1",
   "role": "deferred-resolution"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe2_unscoreable_negative.py",
   "id": "probe2",
   "role": "independent-recount-negative-control"
  }
 ],
 "negative_controls": [
  {
   "description": "the check rejects a scorer that assigns Brier to UNSCOREABLE rows by treating them as resolved-correct (y=1); it stays silent when every statement has a named EXTERNAL_OBSERVABLE and a matching later resolution.",
   "fired_on_bad_state": true,
   "id": "CNL0074-C1",
   "kind": "known-broken-scorer",
   "rejects": "mutant.py treat_unscoreable_and_pending_as_resolved_correct",
   "silent_on_good_state": true
  }
 ],
 "output_schema_named_by_catalog": "command-center/schema/councilspec.v2.schema.json",
 "output_schema_on_this_tree": "command-center/p2-wave/probes/CNL-0074/design-note.schema.json",
 "per_round_record": {
  "record_kind": "confidence_statement",
  "required_fields": [
   "council_run_id",
   "round_id",
   "recorded_at",
   "participant_id",
   "proposition_id",
   "proposition_text",
   "stated_confidence",
   "vote",
   "resolution_binding"
  ],
  "resolution_binding_required_fields": [
   "source_class",
   "observable_id",
   "observable_procedure",
   "due_at",
   "recorder_role"
  ],
  "schema_version": "cnl-0074.v1",
  "session_independence": "proposition_text and resolution_binding are frozen on the statement so a scorer that is given only those bytes plus a later resolution document can classify and score without the session.",
  "stated_confidence": "P(proposition is true) in [0,1], not P(my vote wins) and not a Likert label.",
  "vote_is_not_the_prediction": "vote records for/against/abstain/delegate. Calibration scores stated_confidence against the later binary outcome of the proposition. A participant may vote against while stating p=0.45."
 },
 "phase": "2C",
 "question": "What is recorded per round so that a calibration report can later ask whether stated confidence tracked correctness - and what resolution source settles that, given most council decisions have no ground truth for months?",
 "residual_unknowns": [
  {
   "claim": "command-center/schema/councilspec.v2.schema.json exists on this tree and this note validates against it.",
   "settling_experiment": "CNL-0001 owns the v2 envelope. This unit answers the calibration-record question and validates against probes/CNL-0074/design-note.schema.json.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Harness restore inputs (_USER-PROMPTS.md:10746-10767 and 11-COUNCIL-SPECIFICATION.schema.json) are on this Linux worktree.",
   "settling_experiment": "Place the restore tree and re-cite the spec lines for calibration report / post-run calibration.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Ranking and multi-class propositions have a proper score in this record.",
   "settling_experiment": "Extend outcome beyond binary 0/1; until then those statements are UNSCOREABLE unless rewritten as binary propositions.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "resolution_source_taxonomy": {
  "allowed": {
   "AUDIT_REPLAY": "For process claims only (did the run follow protocol X), a later audit against frozen artifacts.",
   "EXTERNAL_OBSERVABLE": "A named future measurement with procedure, due_at, and an independent recorder who is not a session participant.",
   "OWNER_ATTESTED_OUTCOME": "The owner records what happened after due_at. The owner must not also be a voting participant on that run."
  },
  "forbidden_settlers": [
   "LATER_COUNCIL_AGREEMENT",
   "SELF_FINAL_VOTE",
   "ELAPSED_SILENCE",
   "SELF_REPORTED_CORRECT",
   "NONE"
  ],
  "pending_rule": "A valid binding with no resolution yet is PENDING. PENDING is not scored and is not UNSCOREABLE. Silence after due_at is still PENDING until a resolution is recorded; it is never treated as y=1.",
  "unscoreable_rule": "source_class NONE or missing, or a binding missing required fields, yields UNSCOREABLE. UNSCOREABLE is a terminal honesty state, not a queue. It cannot be retrofitted with a convenient source after the session."
 },
 "reviewer": {
  "independent": true,
  "method": "recount.py re-derives status counts and mean Brier from the fixture files with a different formula. A numeric disagreement with score.py or with fixture_tabulation in this artifact fails probe2.",
  "reviewer_id": "CNL-0074-probe2-independent-recount",
  "verdict": "PASS"
 },
 "scoring_semantics": {
  "brier": "(p - y)^2 on RESOLVED rows only",
  "gameable_metrics_this_closes": [
   "unfalsifiable-metric: a confidence with no named later observable",
   "gameable-metric: counting UNSCOREABLE or PENDING as Brier=0 / y=1",
   "overclaim: a calibration number on n_resolved < 10",
   "spec-underspecified: using the council's own later vote as ground truth"
  ],
  "log_score": "y*log(clip(p)) + (1-y)*log(clip(1-p)) with clip to [1e-15, 1-1e-15]",
  "not_yet_meaningful": "n_resolved < 10 must set not_yet_meaningful true rather than print a confident calibration claim (IMP-0329).",
  "population": "resolved_only",
  "unscoreable_counted_as_calibrated": false
 },
 "sentinel": "SUCCESS:CNL-0074",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe1_deferred_resolution.py",
   "id": "T1-deferred-resolution",
   "name": "Deferred-resolution fixture remains scoreable after the fact without the original session",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe2_unscoreable_negative.py",
   "id": "T2-unscoreable-and-negative-control",
   "name": "No-resolvable-outcome marked UNSCOREABLE; independent recount; mutant that scores UNSCOREABLE as y=1 is rejected",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0074/probe2_unscoreable_negative.py",
   "id": "T3-pending-vs-unscoreable",
   "name": "Valid binding without resolution is PENDING, not UNSCOREABLE and not scored",
   "result": "PASS"
  }
 ],
 "title": "Confidence trajectory and the post-run calibration report",
 "unit_id": "CNL-0074"
}
