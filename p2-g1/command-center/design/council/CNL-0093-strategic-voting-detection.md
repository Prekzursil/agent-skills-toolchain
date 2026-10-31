{
 "answer": "The load-bearing pattern is a three-part predicate over ballot history, not a lone ranking delta. Take each participant's latest stated_position ranking and latest ballot. If they match, the detector is silent \u2014 that is an honest (or at least openly revised) position, including the case where both the statement and the ballot moved together after an earlier round. If they differ, re-tabulate IRV twice: once on submitted ballots, once with that participant's ballot replaced by the stated ranking. The detector fires only when the winner changes AND the stated ranking prefers the actual winner to the counterfactual winner. That is the signature of a pivotal misreport that improved the outcome relative to the participant's declared preference (classic IRV compromise on the planted 5-voter A/B/C profile: p3 states C>B>A, submits B>A>C, A loses to B). Honest revision is distinguished because contemporaneous stated and ballot agree, so the counterfactual is identical to the actual tabulation. A lower-rank swap that does not change the winner is inconsistent but not evidence of influence; it stays silent. false_positive_rate=0.0 on three clean fixtures (known-good, honest-revision, non-pivotal). SUCCESS:CNL-0093",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0093-strategic-voting-detection.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-detector-spec.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py",
   "role": "named-probe"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
   "role": "named-probe"
  }
 ],
 "both_states": {
  "detector_control_known_present_found": true,
  "known_good_silent": true,
  "known_good_verbatim": "detector_control_known_present_found=True\nsilent_on_known_good=True\nsilent_on_honest_revision=True\nsilent_on_non_pivotal=True\nfalse_positive_count=0\nfalse_positive_denominator=3\nfalse_positive_rate=0.0\nnegative_control_verbatim=honest-revision (p3 updated stated_position AND ballot to B>A>C) fires=False \u2014 detector must reject this state\n{\"false_positive_rate\": 0.0, \"honest_revision\": {\"fires\": false, \"id\": \"honest-revision\"}, \"known_good\": {\"fires\": false, \"id\": \"known-good\"}, \"non_pivotal\": {\"fires\": false, \"id\": \"non-pivotal\"}, \"planted\": {\"fires\": true, \"id\": \"planted-bad\"}}\nSUCCESS:CNL-0093-probe2 known-good silent fp_rate=0.0",
  "negative_control_verbatim": "honest-revision fixture: p3 updates stated_position AND ballot to B>A>C; detector fires=False. That is the state the check is meant to reject (not flag as strategic).",
  "planted_bad_fires": true,
  "planted_bad_verbatim": "fixture=planted-bad\ndetector_control_known_present_found=True\nfires_on_planted_bad=True\np3_flagged=True\nwinner_actual=B\nwinner_if_stated=A\nstated=['C', 'B', 'A']\nballot=['B', 'A', 'C']\n{\"result\": {\"council_id\": \"planted-bad\", \"findings\": [{\"kind\": \"pivotal-misreport-gain\", \"participant\": \"p3\", \"stated_ranking\": [\"C\", \"B\", \"A\"], \"submitted_ballot\": [\"B\", \"A\", \"C\"], \"winner_if_stated_ballot\": \"A\", \"winner_with_submitted_ballots\": \"B\"}], \"fires\": true, \"honest_matches\": 4, \"inconsistencies_non_pivotal\": 0, \"method\": \"irv\", \"voters\": 5, \"winner_actual\": \"B\"}}\nSUCCESS:CNL-0093-probe1 planted-bad fires detector-control"
 },
 "completion_sentinel": "SUCCESS:CNL-0093",
 "dependencies_note": "CNL-0061 (IRV tabulation) and CNL-0066 (strategic abstention) are catalog dependencies. Their design artifacts are absent on this worktree. This unit therefore carries a local IRV procedure with a declared a-priori elimination tie-break rather than importing a missing note. Abstention is out of scope here: CNL-0066 covers denominator/no/park; this detector is stated-vs-ballot + pivot.",
 "detector": {
  "fires_when": "a participant's submitted ranking is a pivotal misreport that improves the IRV outcome relative to their latest stated ranking",
  "honest_revision_rule": "If the participant updates stated_position to match the new ballot in the same history (latest stated == latest ballot), the detector is silent even when the new ranking would have been a successful strategy against the previous statement.",
  "id": "stated-vs-ballot-irv-pivot-gain",
  "inputs": [
   "per-participant stated_position events in chronological history",
   "per-participant ballot events in chronological history",
   "candidate set and IRV tabulation with lex-last fewest-first elimination"
  ],
  "predicate": "latest stated_position ranking != latest ballot AND IRV winner with ballot replaced by stated ranking differs AND stated ranking prefers the actual winner to that counterfactual winner",
  "silent_when": "stated ranking equals ballot, or a disagreement is not winner-pivotal, or a winner change is not a gain on the stated ranking"
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0093/detector.py:85",
   "kind": "detector-predicate",
   "line": 85,
   "path": "command-center/p2-wave/probes/CNL-0093/detector.py",
   "snippet": "kind\": \"pivotal-misreport-gain\""
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0093/irv.py:46",
   "kind": "irv-tie-break",
   "line": 46,
   "path": "command-center/p2-wave/probes/CNL-0093/irv.py",
   "snippet": "drop = sorted(tied)[-1]"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0093/fixtures/planted-bad.json:2",
   "kind": "planted-defect",
   "line": 2,
   "path": "command-center/p2-wave/probes/CNL-0093/fixtures/planted-bad.json",
   "snippet": "\"id\": \"planted-bad\""
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0093/fixtures/honest-revision.json:2",
   "kind": "negative-control",
   "line": 2,
   "path": "command-center/p2-wave/probes/CNL-0093/fixtures/honest-revision.json",
   "snippet": "\"id\": \"honest-revision\""
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py:54",
   "kind": "false-positive-rate",
   "line": 54,
   "path": "command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
   "snippet": "false_positive_rate={fp_rate}"
  }
 ],
 "false_positive_rate": {
  "clean_fixtures": [
   "known-good",
   "honest-revision",
   "non-pivotal"
  ],
  "denominator": 3,
  "numerator": 0,
  "rate": 0.0
 },
 "kind": "council-detector-spec",
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py",
   "exit_code": 0,
   "id": "probe1",
   "raw_output": "fixture=planted-bad\ndetector_control_known_present_found=True\nfires_on_planted_bad=True\np3_flagged=True\nwinner_actual=B\nwinner_if_stated=A\nstated=['C', 'B', 'A']\nballot=['B', 'A', 'C']\n{\"result\": {\"council_id\": \"planted-bad\", \"findings\": [{\"kind\": \"pivotal-misreport-gain\", \"participant\": \"p3\", \"stated_ranking\": [\"C\", \"B\", \"A\"], \"submitted_ballot\": [\"B\", \"A\", \"C\"], \"winner_if_stated_ballot\": \"A\", \"winner_with_submitted_ballots\": \"B\"}], \"fires\": true, \"honest_matches\": 4, \"inconsistencies_non_pivotal\": 0, \"method\": \"irv\", \"voters\": 5, \"winner_actual\": \"B\"}}\nSUCCESS:CNL-0093-probe1 planted-bad fires detector-control"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
   "exit_code": 0,
   "id": "probe2",
   "raw_output": "detector_control_known_present_found=True\nsilent_on_known_good=True\nsilent_on_honest_revision=True\nsilent_on_non_pivotal=True\nfalse_positive_count=0\nfalse_positive_denominator=3\nfalse_positive_rate=0.0\nnegative_control_verbatim=honest-revision (p3 updated stated_position AND ballot to B>A>C) fires=False \u2014 detector must reject this state\n{\"false_positive_rate\": 0.0, \"honest_revision\": {\"fires\": false, \"id\": \"honest-revision\"}, \"known_good\": {\"fires\": false, \"id\": \"known-good\"}, \"non_pivotal\": {\"fires\": false, \"id\": \"non-pivotal\"}, \"planted\": {\"fires\": true, \"id\": \"planted-bad\"}}\nSUCCESS:CNL-0093-probe2 known-good silent fp_rate=0.0"
  }
 ],
 "question": "What pattern in the ballot history indicates a participant voted against its stated position to influence the tabulation, and can it be distinguished from an honest revision?",
 "reviewer": {
  "independent": true,
  "method": "Re-executed probe1 and probe2 in a separate process. PASS iff planted-bad fires, known-good and honest-revision are silent, and false_positive_rate is 0.0. Agreement with the prose answer is not required.",
  "reran_both_states": true,
  "reviewer_id": "CNL-0093-independent-both-states-reviewer",
  "scope_not_agreement": true,
  "verbatim": "reran_probe1_exit=0\nreran_probe2_exit=0\nplanted_bad_fires=True\nknown_good_and_revision_silent=True\nfalse_positive_rate_zero=True\nscope=re-ran planted-bad and known-good/honest-revision controls; agreement with the design prose is not required for PASS\nSUCCESS:CNL-0093-reviewer PASS",
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0093",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py",
   "id": "T-planted-defect-fires",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
   "id": "T-known-good-silent-fp-rate",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe1_planted_bad.py",
   "id": "T-detector-control-known-present",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0093/probe2_known_good.py",
   "id": "T-negative-control-honest-revision",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:54:29Z"
 },
 "title": "Strategic voting detection",
 "unit_id": "CNL-0093",
 "worked_example": {
  "candidates": [
   "A",
   "B",
   "C"
  ],
  "honest_profile": {
   "eliminated": "B",
   "irv_winner": "A",
   "p0": [
    "A",
    "B",
    "C"
   ],
   "p1": [
    "A",
    "B",
    "C"
   ],
   "p2": [
    "B",
    "A",
    "C"
   ],
   "p3": [
    "C",
    "B",
    "A"
   ],
   "p4": [
    "C",
    "B",
    "A"
   ],
   "round1_first_preferences": {
    "A": 2,
    "B": 1,
    "C": 2
   },
   "round2": {
    "A": 3,
    "C": 2
   }
  },
  "p3_strategic_ballot": [
   "B",
   "A",
   "C"
  ],
  "roster_size": 5,
  "strategic_eliminated": "C",
  "strategic_irv_winner": "B",
  "strategic_round1": {
   "A": 2,
   "B": 2,
   "C": 1
  },
  "why_gain": "stated C>B>A ranks B above A, so electing B instead of A is a gain"
 }
}
