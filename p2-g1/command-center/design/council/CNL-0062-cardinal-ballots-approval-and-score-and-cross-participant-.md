{
 "anchors": {
  "calibrate_ballot": "command-center/p2-wave/probes/CNL-0062/tabulate.py:59",
  "pairwise_score_margins": "command-center/p2-wave/probes/CNL-0062/tabulate.py:170",
  "positive_affine_map": "command-center/p2-wave/probes/CNL-0062/tabulate.py:131",
  "tabulate": "command-center/p2-wave/probes/CNL-0062/tabulate.py:218",
  "totals_row_major": "command-center/p2-wave/probes/CNL-0062/tabulate.py:158"
 },
 "answer": "Shared cardinal tabulation is a weighted sum of per-ballot affine-calibrated scores on [0,1], with argmax winner and a priori lex-min tie-break. Approval is that procedure with domain {0,1}; mixed approval ballots are already calibrated. Cross-participant anchors are comparable because a positive affine transform of a ballot (the definition of the same cardinal preference with a different scale) is mapped to the identical [0,1] vector, so substituting one for the other cannot change the winner after calibration. Uncalibrated substitution can and, on the scale-drift fixture, does.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0062-cardinal-ballots-approval-and-score-and-cross-participant-.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0062/tabulate.py",
   "role": "engine"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0062/fixtures/scale_drift.json",
   "role": "fixture"
  }
 ],
 "both_states": {
  "check": "uncalibrated_winner != calibrated_winner",
  "known_good_cal_winner": "A",
  "known_good_fired": false,
  "known_good_fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/known_good.json",
  "known_good_raw_winner": "A",
  "known_good_silent": true,
  "negative_control_on_reject_state": "FIRES",
  "negative_control_verbatim": "On planted_bad.json (affine-stretched drifted ballot tabulated as commensurate) the check FIRES: raw_winner=A cal_winner=C.",
  "planted_bad_cal_winner": "C",
  "planted_bad_fired": true,
  "planted_bad_fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/planted_bad.json",
  "planted_bad_raw_winner": "A"
 },
 "completion_sentinel": "SUCCESS:CNL-0062",
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0062/tabulate.py:218",
   "claim": "Uncalibrated substitution of an affine-stretched copy of the same preference flips the winner on the scale-drift fixture.",
   "signal": "argmax of uncalibrated Fraction totals",
   "verbatim": "raw_with_canonical=C raw_with_drifted=A totals_can={'A': '10', 'B': '11', 'C': '17'} totals_dft={'A': '30', 'B': '26', 'C': '27'}",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0062/tabulate.py:59",
   "claim": "After per-ballot min-max calibration the same substitution does not change the winner (or the totals).",
   "signal": "pairwise score-margin Condorcet on calibrated ballots",
   "verbatim": "cal_with_canonical=C cal_with_drifted=C totals={'A': '1', 'B': '19/14', 'C': '2'} pairwise=C",
   "verdict": "CONFIRMED"
  }
 ],
 "inputs_on_this_worktree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "CNL-0023 artifact": false,
  "USER-PROMPTS.md:10746-10767": false,
  "USER-PROMPTS.md:10915-10946": false,
  "council-design-note.schema.json": true
 },
 "kind": "council-design-note",
 "markdown": "# Cardinal ballots (approval and score) and cross-participant scale calibration\n\nApproval is score voting restricted to {0,1} - what does the shared cardinal tabulation look like, and how are scores comparable across participants who anchor their scales differently?\n\n## Shared tabulation (declared before ballots are seen)\n\nApproval is not a second method. It is score voting with domain {0,1}.\nOne engine tabulates both:\n\n1. Fill omitted candidates with the declared floor L (default 0).\n2. Reject approval scores outside {0,1}; reject score votes outside [L,H].\n3. Affine-calibrate each ballot onto [0,1]: s' = (s-min)/(max-min).\n   A flat ballot (max==min) contributes 0 to every candidate.\n4. T[c] = sum_i weight_i * s'_i[c] as exact rationals (Fraction).\n5. Winner = unique argmax(T). Ties: lexicographically smallest candidate_id.\n\nSeat weight defaults to 1. A weight other than 1 without a provenance\nrecord is rejected (CNL-0023). That provenance schema is NOT-CHECKED here\nbecause the CNL-0023 artifact is absent on this worktree.\n\n## Why calibration is load-bearing\n\ncanonical scores (A,B,C) = (10, 5, 0).\ndrifted scores = 2*canonical + 10 = (30, 20, 10) \u2014 the same preference,\na different anchor. Substituting drifted for canonical in the same\nthree-seat electorate flips the uncalibrated winner and does not flip\nthe calibrated winner. Numbers are in worked_examples.scale_drift.\n\n## Both-states and negative control\n\nCheck: uncalibrated winner != calibrated winner.\nSILENT on known-good mixed approval (calibration is identity).\nFIRES on planted-bad affine-stretched scores. The negative control is\nthat FIRES on planted-bad \u2014 the state the check is meant to reject.\n\nSUCCESS:CNL-0062",
 "min_bytes_threshold": 8000,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0062/probe1_scale_drift.py",
   "id": "probe1"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0062/probe2_both_states.py",
   "id": "probe2"
  }
 ],
 "negative_controls": [
  {
   "id": "scale-drift-uncalibrated",
   "on_reject_state": "FIRES",
   "rejects": "planted_bad.json",
   "verbatim": "raw_winner=A cal_winner=C fired=True"
  },
  {
   "id": "weight-without-provenance",
   "on_reject_state": "ValueError weight_provenance",
   "rejects": "weight!=1 and weight_provenance absent"
  }
 ],
 "notes": "G-1 for CNL-0062. cloud ok=true is not delivery. Did not run global unit_manifest.py --write. Did not git add/commit/push.",
 "procedure": {
  "aggregation": "T[c] = sum weight_i * s'_i[c] as Fraction",
  "calibration": "per-ballot min-max onto [0,1]; flat ballot -> 0 vector",
  "declared_before_ballots": true,
  "domain_approval": "{0,1}",
  "domain_score": "[L,H] with L<H declared in the council spec",
  "executable": "command-center/p2-wave/probes/CNL-0062/tabulate.py",
  "omitted_candidate": "declared floor L (default 0)",
  "tie_break": "lexicographically smallest candidate_id",
  "weight_default": "1",
  "weight_nonequal": "rejected unless weight_provenance is present (CNL-0023)",
  "winner": "unique argmax(T)"
 },
 "question": "Approval is score voting restricted to {0,1} - what does the shared cardinal tabulation look like, and how are scores comparable across participants who anchor their scales differently?",
 "report": {
  "control_ids": [
   "scale-drift-uncalibrated",
   "weight-without-provenance"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0062/tabulate.py:218",
    "measured": true,
    "method": "argmax of uncalibrated Fraction totals",
    "name": "scale_drift_raw_flip"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0062/tabulate.py:59",
    "measured": true,
    "method": "pairwise score-margin Condorcet after min-max",
    "name": "scale_drift_calibrated_stable"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0062/tabulate.py:218",
    "measured": true,
    "method": "shared tabulate() on identical {0,1} ballots",
    "name": "approval_is_score_on_01"
   }
  ]
 },
 "residual_unknowns": [
  "Catalog inputs USER-PROMPTS.md slices and 11/12 council JSON files are Windows restore paths absent on this Linux worktree. The procedure is derived from the catalog question plus re-runnable fixtures, not from those bytes. NOT-CHECKED against the restore tree.",
  "output_schema command-center/schema/council-design-note.schema.json exists as a generated shim ($ref to platform artifact-class-profiles). G-1 json.loads the catalog .md path, so this artifact is a JSON object at a .md suffix. Full Draft 2020-12 validation of the physical council-design-note profile (receipt_core additionalProperties false) is NOT-CHECKED here.",
  "CNL-0023 is a declared dependency and its artifact is absent. Non-equal weights are rejected without provenance; the provenance record shape is NOT specified here."
 ],
 "reviewer": {
  "independent": true,
  "method": "probe2 re-tabulates known_good.json and planted_bad.json with a column-major Fraction loop that does not call totals_row_major, then requires the published winners to match.",
  "reviewer_id": "CNL-0062-probe2-column-major-recount",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0062",
 "state": "SUCCESS",
 "status": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0062/probe1_scale_drift.py",
   "id": "scale-drift",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0062/probe2_both_states.py",
   "id": "both-states-and-negative-control",
   "result": "PASS"
  }
 ],
 "title": "Cardinal ballots (approval and score) and cross-participant scale calibration",
 "ts": "2026-08-25T00:53:34Z",
 "unit_id": "CNL-0062",
 "worked_examples": {
  "scale_drift": {
   "affine_a": "2",
   "affine_b": "10",
   "approval_totals": {
    "X": "2",
    "Y": "2",
    "Z": "1"
   },
   "approval_winner": "X",
   "calibrated_totals": {
    "A": "1",
    "B": "19/14",
    "C": "2"
   },
   "calibrated_winner_with_canonical": "C",
   "calibrated_winner_with_drifted": "C",
   "calibration_stabilizes_winner": true,
   "drift_flips_uncalibrated_winner": true,
   "fixture": "command-center/p2-wave/probes/CNL-0062/fixtures/scale_drift.json",
   "raw_totals_with_canonical": {
    "A": "10",
    "B": "11",
    "C": "17"
   },
   "raw_totals_with_drifted": {
    "A": "30",
    "B": "26",
    "C": "27"
   },
   "raw_winner_with_canonical": "C",
   "raw_winner_with_drifted": "A",
   "score_on_01_winner": "X"
  }
 }
}
