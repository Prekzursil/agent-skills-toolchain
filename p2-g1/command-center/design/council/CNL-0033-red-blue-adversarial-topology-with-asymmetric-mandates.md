{
 "answer": "The informative asymmetry is not 'give red less clock.' Clock is a right to spend, never a scoring input. Red is scored in attempt-budget (existence search for one reproducible artifact). Blue is scored in coverage-obligation discharge (universality over a named surface). Red wins on one confirmed finding (repro_poc / failing_control / concrete_counterexample). Blue wins only when confirmed_findings==0 AND red's attempt budget is exhausted AND the coverage checklist is complete. Every other terminal \u2014 including red clock death with attempts remaining \u2014 is INCONCLUSIVE, labelled not-refuted-within-budget never 'secure'. A topology that awards the side with leftover clock is refuted by the symmetry-swap control: swapping the larger clock deterministically swaps the winner, so that topology measures budget not truth.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0033/topology.py",
   "role": "supporting"
  }
 ],
 "claim_under_test": "Asymmetry that makes red/blue informative is three-axis (currencies, evidence, win condition), not a smaller red clock. A clock-only swap must not swap the winner on the good topology and must swap it on remaining-clock scoring.",
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py",
   "claim": "Clock-only swap of 100/10 vs 10/100 does not change the winner on asymmetric-mandates-v1 (finding stays RED, clean stays BLUE).",
   "id": "C1",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/fixtures/topology_timeout_wins.json",
   "claim": "The same clock permutation swaps the winner on remaining-clock (timeout-wins) scoring, so the detector is not vacuous.",
   "id": "C2",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/topology.py:timeout_trap",
   "claim": "Red clock death with leftover attempts is INCONCLUSIVE on the good topology, not a blue win.",
   "id": "C3",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "protocol_anchor.library_present",
   "claim": "P08 red-blue-team protocol body was read from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json on this worktree.",
   "id": "C4",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0033",
 "currencies": [
  {
   "description": "Wall/token budget. May not decide the winner.",
   "id": "clock",
   "role": "right",
   "scoring_input_on_good": false
  },
  {
   "description": "Existence search. Exhaustion is required for BLUE_WIN.",
   "id": "red_attempt_budget",
   "role": "finding-currency",
   "scoring_input_on_good": true
  },
  {
   "description": "Named surface discharge. Incomplete coverage blocks BLUE_WIN.",
   "id": "blue_coverage_slots",
   "role": "obligation-currency",
   "scoring_input_on_good": true
  }
 ],
 "defective_topology": {
  "clock_is_scoring_input": true,
  "id": "timeout-wins-defective",
  "scoring": "remaining-clock",
  "timeout_policy": "side-with-remaining-clock-wins"
 },
 "dependency_cnl_0022": {
  "artifact_present": false,
  "id": "CNL-0022",
  "note": "Waiting for CNL-0022 before closing CNL-0033 is a deadlock; G-1 for this unit does not require that circle. No ADV rebuild.",
  "trichotomy_used_locally": true
 },
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
   "consumer": "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py",
   "executed": true
  },
  {
   "artifact_path": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
   "consumer": "command-center/p2-wave/_measure_one_delivered.py CNL-0033",
   "executed": false,
   "note": "Measure runs after emit and after named probes."
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py",
   "claim": "On asymmetric-mandates-v1, swapping clocks 100/10 vs 10/100 leaves the winner unchanged on both a planted finding (RED) and a clean surface (BLUE).",
   "signal": "winner-identity-pair",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/topology.py:recount_from_events",
   "claim": "The same invariance is recovered by recounting confirmed/attempts_exhausted/coverage_complete from the event log, a different field than winner.",
   "signal": "event-log-score-vector",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/fixtures/topology_timeout_wins.json",
   "claim": "Remaining-clock scoring swaps the winner under the same clock permutation on both worlds, so the detector is not vacuous.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0033/topology.py:timeout_trap",
   "claim": "Red clock death with leftover attempts is INCONCLUSIVE on the good topology and a BLUE win on timeout-wins \u2014 the scripted-loss state the question names.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "protocol_anchor.library_present",
   "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json P08 body was read from disk on this worktree.",
   "verdict": "REFUTED"
  }
 ],
 "evidence_standard": {
  "blue_may_claim_secure": false,
  "blue_terminal_label_on_win": "not-refuted-within-budget",
  "narrative_claim_confirms": false,
  "red_positive_claim_requires": [
   "repro_poc",
   "failing_control",
   "concrete_counterexample"
  ]
 },
 "id": "CNL-0033",
 "mandates": {
  "blue": {
   "obligations": [
    "discharge_named_coverage_checklist"
   ],
   "permissions": [
    "patch_in_exercise",
    "request_scope_clarification"
   ],
   "rights": [
    "coverage_slots_not_revocable_mid_round",
    "timeout_cannot_be_scored_as_secure",
    "outcome_label_is_not_refuted_not_secure"
   ]
  },
  "red": {
   "obligations": [],
   "permissions": [
    "attempt_attack",
    "submit_finding_artifact"
   ],
   "rights": [
    "private_red_channel",
    "attempt_budget_not_revocable_mid_round",
    "finding_judged_on_artifact_not_clock"
   ]
  }
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0033/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "markdown_body": "# CNL-0033 Red/blue adversarial topology with asymmetric mandates\n\n## Question\n\nRed and blue are not symmetric (one attacks, one defends) \u2014 what asymmetry\nin budget, evidence standard and win condition makes the exercise informative\nrather than a scripted loss for whichever side was given less time?\n\n## Claim under test\n\nEqual clocks and a shared 'who still has budget wins' condition make the\nexercise a scripted loss for the side given less time. The repair is three\nasymmetric axes (budget currencies, evidence standard, win condition), not\na smaller red clock.\n\n## Mandates (obligation / permission / right)\n\nThis unit depends on CNL-0022's trichotomy. The CNL-0022 artifact is not on\nthis worktree; the trichotomy is used here as a local contract so G-1 for\nTHIS unit does not deadlock waiting on CNL-0022.\n\n| Seat | Obligation (MUST) | Permission (MAY) | Right (nobody may deny) |\n| --- | --- | --- | --- |\n| Red | none \u2014 failing to find a bug is not a red failure | attempt_attack, submit_finding_artifact | private channel; attempt budget not revocable mid-round; finding judged on artifact not clock |\n| Blue | discharge_named_coverage_checklist | patch_in_exercise, request_scope_clarification | coverage slots not revocable; timeout cannot be scored as secure; outcome label is not-refuted, not secure |\n\nA schema that stores a single `capabilities[]` string list conflates these\nthree (CNL-0022's load-bearing question). Red's unused permission must not\nfail the role check; blue's unmet coverage obligation must.\n\n## Three currencies\n\n1. Clock / token budget \u2014 a right, not a score.\n2. Red attempt budget \u2014 finding currency.\n3. Blue coverage slots \u2014 obligation currency.\n\nSwapping (1) while holding (2) and (3) fixed must not swap the winner.\n\n## Evidence standard\n\nRed's positive claim requires a reproducible artifact. A narrative_claim is\nrejected. Blue has no 'secure' claim; blue may only reach BLUE_WIN as\nnot-refuted after attempts exhausted and coverage complete.\n\n## Win condition\n\n- RED_WIN: confirmed_findings >= 1, even if blue still has clock and coverage left.\n- BLUE_WIN: confirmed==0 AND attempts exhausted AND coverage complete.\n- INCONCLUSIVE: otherwise, including clock death with leftover attempts.\n\n## Defective alternative (refuted)\n\nScore remaining clock. The side that outlasts the other wins. The\nsymmetry-swap control fires: 100/10 vs 10/100 swaps the winner on both a\nplanted-finding world and a clean-surface world.\n\n## Live measurements (embedded at emit)\n\nSee `symmetry_swap` and `negative_controls` in this document. Named probes\nre-run the same fixtures.\n",
 "min_bytes_threshold": 8000,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py",
   "id": "probe1",
   "role": "symmetry-swap"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0033/probe2_negative_control.py",
   "id": "probe2",
   "role": "negative-control"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "REJECT: winner swapped after clock-only permutation; topology measures budget not truth",
   "check": "clock_swap_changes_winner",
   "description": "The check fires when a clock-only permutation changes the winner. Planted-bad state is remaining-clock scoring (timeout-wins-defective). Known-good state is asymmetric-mandates-v1.",
   "fired_on_bad_state": true,
   "good_state_output": "OK: winner invariant under clock-only permutation",
   "id": "CNL0033-C1",
   "kind": "known-broken-fixture",
   "reject_state": "timeout-wins-defective scores remaining clock; swapping the larger clock swaps the winner (budget, not truth)",
   "silent_on_good_state": true,
   "verbatim_bad_finding": "fired=True winners=RED->BLUE verdict=REJECT: winner swapped after clock-only permutation; topology measures budget not truth",
   "verbatim_good_finding": "fired=False winners=RED->RED verdict=OK: winner invariant under clock-only permutation"
  }
 ],
 "output_schema": "command-center/schema/council-design-note.schema.json",
 "protocol_anchor": {
  "family": "ADVERSARIAL",
  "library_present": false,
  "named_record": "P08 red-blue-team",
  "note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; P08 is cited from the catalog text of CNL-0039, not from a live library count."
 },
 "question": "Red and blue are not symmetric (one attacks, one defends) - what asymmetry in budget, evidence standard and win condition makes the exercise informative rather than a scripted loss for whichever side was given less time?",
 "residual_unknowns": [
  {
   "claim": "P08 red-blue-team protocol record body in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
   "settling_experiment": "Place the library on disk and bind this topology's mandates onto the live P08 record field-by-field.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "both_states_rerun": true,
  "independent": true,
  "method": "probe2_negative_control.py re-runs clock_swap_changes_winner on planted-bad and known-good fixtures and records both transcripts verbatim. A review that did not execute this control is rejected by the probe.",
  "reviewer_id": "CNL-0033-probe2-both-states-control",
  "scope_not_agreement": true,
  "vendor_role": "openai/gpt-5-codex",
  "verdict": "PASS"
 },
 "schema_note": "Catalog output_schema command-center/schema/council-design-note.schema.json is a generated $ref shim to https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json which does not resolve on this worktree. This note is JSON-parseable with state=SUCCESS. No ADV rebuild of that schema was attempted.",
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0033",
 "spec_anchor": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10746-10767",
 "state": "SUCCESS",
 "symmetry_swap": {
  "clock_hi": 100,
  "clock_lo": 10,
  "defective_clean_winners": [
   "RED",
   "BLUE"
  ],
  "defective_finding_winners": [
   "RED",
   "BLUE"
  ],
  "defective_winner_swapped": true,
  "good_clean_winners": [
   "BLUE",
   "BLUE"
  ],
  "good_finding_winners": [
   "RED",
   "RED"
  ],
  "good_winner_swapped": false,
  "narrative_good": {
   "confirmed": 0,
   "outcome": "BLUE_WIN",
   "winner": "BLUE"
  },
  "signal1": "winner identity pair under clock-only permutation",
  "signal2": "event-log score_vector recount (confirmed/exhausted/complete)",
  "signal2_clean_recount_winner": "BLUE",
  "signal2_finding_recount_winner": "RED",
  "timeout_trap_defective": {
   "outcome": "CLOCK_BLUE",
   "winner": "BLUE"
  },
  "timeout_trap_good": {
   "attempts_exhausted": false,
   "attempts_used": 1,
   "outcome": "INCONCLUSIVE",
   "winner": "NONE"
  }
 },
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0033/probe1_symmetry_swap.py",
   "id": "T1-symmetry-swap",
   "name": "Clock-only swap must not swap the winner on the good topology and must swap it on remaining-clock scoring",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0033/probe2_negative_control.py",
   "id": "T2-negative-control-both-states",
   "name": "clock_swap_changes_winner FIRES on timeout-wins and is SILENT on asymmetric-mandates; timeout is not a blue win",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:53:33Z"
 },
 "title": "Red/blue adversarial topology with asymmetric mandates",
 "topology": {
  "allowed_evidence": [
   "repro_poc",
   "failing_control",
   "concrete_counterexample"
  ],
  "clock_is_scoring_input": false,
  "id": "asymmetric-mandates-v1",
  "mandates": {
   "blue": {
    "obligations": [
     "discharge_named_coverage_checklist"
    ],
    "permissions": [
     "patch_in_exercise",
     "request_scope_clarification"
    ],
    "rights": [
     "coverage_slots_not_revocable_mid_round",
     "timeout_cannot_be_scored_as_secure",
     "outcome_label_is_not_refuted_not_secure"
    ]
   },
   "red": {
    "obligations": [],
    "permissions": [
     "attempt_attack",
     "submit_finding_artifact"
    ],
    "rights": [
     "private_red_channel",
     "attempt_budget_not_revocable_mid_round",
     "finding_judged_on_artifact_not_clock"
    ]
   }
  },
  "scoring": "findings-and-coverage",
  "timeout_policy": "inconclusive"
 },
 "unit_id": "CNL-0033",
 "win_conditions": {
  "BLUE_WIN": "confirmed_findings == 0 AND attempts_exhausted AND coverage_complete",
  "INCONCLUSIVE": "otherwise, including red clock death with leftover attempts; label is not-refuted-within-budget, never secure",
  "RED_WIN": "confirmed_findings >= 1"
 }
}
