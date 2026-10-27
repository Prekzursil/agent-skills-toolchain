{
 "answer": "A vote is actively harmful when the council is not aggregating preferences among already-valid options, but is instead being asked to name a fact, a cause, a scalar, a reading of evidence, or a meaning of text. In those classes plurality still emits a winner and a mean still emits a center. Those numbers are social statistics. They are not the missing finding. The 2-1 diagnosis fixture shows the method harm with seats held fixed: vote names cache; synthesis-only keeps {cache, deploy} live and emits no winner. The scalar fixture shows a manufactured 40.0 that no seat held. Synthesis-only owes the reader live hypotheses, seat provenance, a census labeled as census, an explicit no-tally statement, preserved dissent, and the next measurement that would drop a hypothesis. A census of unanimous reports is still not a vote-as-decision: the detector fires on method=vote even when every seat names the same cause. Mixed questions (rollback?) must be split: diagnosis stays synthesis-only; the residual preference may be voted.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0057-synthesis-only-mode-when-taking-no-vote-is-the-correct-des.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py",
   "role": "supporting"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0057",
 "dependencies": {
  "CNL-0023": {
   "note": "Vote-weight provenance is a sibling concern. Synthesis-only is the claim that some decision classes must not be closed by any tally, equal-weight or not.",
   "required_for_this_answer": false,
   "status_this_tree": "not-used"
  }
 },
 "detector": {
  "fire": "FIRE manufactured_tally",
  "fire_line": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:204",
  "mean_line": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:111",
  "rejects": "vote-as-decision on a vote-harmful decision_class (plurality winner or mean scalar emitted as the council decision)",
  "rejects_line": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:48",
  "silent": "SILENT",
  "silent_line": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:212"
 },
 "evidence": [
  {
   "claim": "On identical diagnosis ballots, plurality names cache while synthesis-only emits no winner and keeps cache and deploy live; attribution is method.",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:145",
    "kind": "file_line",
    "line": 145,
    "path": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py",
    "snippet": "\"winner\": None,"
   },
   "verdict": "CONFIRMED"
  },
  {
   "claim": "Named probes re-ran: method-disagreement and the negative control (FIRE on planted vote, SILENT on synthesis-only and on preference vote).",
   "signal": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe1_method_disagreement.py && PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe2_negative_control.py",
    "kind": "command_output",
    "output": "diagnosis disagree=True reason=method detail=vote_winner_hides_live_set vote_winner=cache synthesis_winner=None live=['cache', 'deploy']\ndiagnosis_ballot_fp=70558d6d9f5d645436e757e98d91d90e98428922c3d7987ca26076dc557e7324 attribution=method\nscalar disagree=True reason=method mean=40.0 held=[10.0, 20.0, 90.0] mean_in_held=False\nmutated_vs_original reason=participants\nnote_present=False (pre-emit)\nmethod_not_participants=True vote_hides_minority=True mean_manufactures_unheld_scalar=True\nSUCCESS:CNL-0057-probe1 method disagreement attributed to method\nnegative_control_rejects: vote-as-decision on a vote-harmful decision_class (plurality winner or mean scalar emitted as the council decision)\nplanted_vote_on_diagnosis: FIRE manufactured_tally\nsynthesis_on_same_diagnosis: SILENT\nvote_on_preference: SILENT\nvote_on_mixed_unsplit: FIRE manufactured_tally\nfired_on_bad=True silent_on_good=True silent_on_preference_vote=True both_states_recorded=True\nrecount_diagnosis winner=cache tally={'cache': 2, 'deploy': 1}\nengine_diagnosis winner=cache tally={'cache': 2, 'deploy': 1}\nrecount_scalar mean=40.0 held=[10.0, 20.0, 90.0] mean_in_held=False\nrecount_live=['cache', 'deploy'] synthesis_live=['cache', 'deploy'] winner=None\ncounterexample id=CX-unanimous-diagnosis-vote attempted=True census_unanimous=True detect=FIRE manufactured_tally refutes=False\npreference_vote detect=SILENT fires=False\nreviewer_verdict=PASS independent=True counterexample_attempted=True refutes=False\nSUCCESS:CNL-0057-reviewer\nSUCCESS:CNL-0057-probe2 negative control fires on manufactured tally"
   },
   "verdict": "CONFIRMED"
  },
  {
   "claim": "VOTE_HARMFUL includes diagnosis and scalar_estimate; detect() emits FIRE manufactured_tally iff method=vote on those classes.",
   "signal": {
    "anchor": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py:28",
    "kind": "file_line",
    "line": 28,
    "path": "command-center/p2-wave/probes/CNL-0057/synthesis_only.py",
    "snippet": "\"diagnosis\","
   },
   "verdict": "CONFIRMED"
  },
  {
   "claim": "11-COUNCIL-SPECIFICATION.schema.json was read from disk on this worktree.",
   "signal": {
    "anchor": "inputs_on_this_tree",
    "kind": "file_line",
    "line": 1,
    "path": "command-center/design/council/CNL-0057-synthesis-only-mode-when-taking-no-vote-is-the-correct-des.md",
    "snippet": "inputs_on_this_tree"
   },
   "verdict": "NOT-CHECKED"
  }
 ],
 "evidence_mechanisms": [
  "file:line citation into synthesis_only.py",
  "subprocess stdout of probe1 and probe2 (different mechanism)"
 ],
 "inputs_on_this_tree": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false
 },
 "kind": "council-design-note",
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0057/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "markdown_body": "# CNL-0057 Synthesis-only mode: when taking no vote is the correct design\n\n## Question\n\nFor which decision types is a vote actively harmful (it manufactures a number\nwhere none exists), and what does synthesis-only owe the reader in place of a\ntally?\n\n## Harm test\n\nA closing procedure is a vote when it emits a `winner` or a mean scalar as\nthe council decision. That is the right procedure when, and only when, the\nobject of the council is a preference among options that remain valid after\nthe facts are in.\n\nIt is the wrong procedure when the object is a finding. Findings are not\ncreated by counting seats. A 2-1 on a cause does not make the minority cause\nfalse. A mean of 10, 90, and 20 is 40, a quantity no seat estimated.\n\n## Vote-harmful decision types\n\n1. Diagnosis / causal attribution. The system has a causal structure. A tally\n   is a social fact about seats.\n2. Scalar estimation. The mean/median is an aggregation rule, not a\n   measurement. If no seat held the aggregate, the number is manufactured.\n3. Evidence interpretation. Whether an artifact supports a claim is a\n   relation between artifacts. Voting does not create the relation.\n4. Meaning of text. Majority is not semantics.\n5. Incommensurable synthesis. Ranking legal vs safety vs product by vote\n   pretends they share a scale.\n6. Unsplit mixed questions. \"Should we rollback?\" smuggles a diagnosis into\n   a preference. Harmful until split.\n\n## Vote-ok decision types (contrast)\n\nPreference choice, resource allocation, and procedure selection among options\nthat remain valid after synthesis of the facts. The 2-1 shape is the same as\nthe diagnosis fixture; the class is different. The detector is silent.\n\n## What synthesis-only owes instead of a tally\n\n- Live hypotheses (the set of still-open claims), never a winner.\n- Seat provenance for each claim.\n- Census counts labeled census, never `vote_outcome`.\n- Explicit no-tally statement and the decision_class that forbids the tally.\n- Dissent preserved, not folded into remainder.\n- The next measurement that would drop a live hypothesis.\n\nUnanimous reports are a census, not a proof. Synthesis-only may say \"3/3\nnamed cache\" and still refuse to close by vote.\n\n## Method, not participants\n\nThe diagnosis fixture holds seats, ballots, and evidence hashes fixed. Vote\nand synthesis-only disagree. Attribution is `method`. Mutating seat C's\nballot changes the fingerprint; that disagreement is `participants`. The\nunit's required fixture is the former.\n\n## Mixed questions\n\nSplit: (a) diagnosis, synthesis-only; (b) preference over residual risk,\nvote-ok. A single vote on the mixed question fires.\n\n## Dependency CNL-0023\n\nUnequal vote weights (CNL-0023) do not convert a finding into a preference.\nThis unit's detector does not read weights. Not blocked on CNL-0023.\n\n## Inputs absent on this tree\n\n`11-COUNCIL-SPECIFICATION.schema.json` and\n`12-COUNCIL-PROTOCOLS-AND-PRESETS.json` are not on this worktree. Claims\nabout those files are NOT-CHECKED. The design is executable from the catalog\nquestion and the fixtures in this unit.\n",
 "method_disagreement_fixture": {
  "ballot_fingerprint": "70558d6d9f5d645436e757e98d91d90e98428922c3d7987ca26076dc557e7324",
  "detail": "vote_winner_hides_live_set",
  "disagree": true,
  "id": "FX-diagnosis-2-1",
  "live_hypotheses": [
   "cache",
   "deploy"
  ],
  "participants_held_fixed": true,
  "reason": "method",
  "synthesis_winner": null,
  "vote_winner": "cache"
 },
 "min_bytes_threshold": 2048,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe1_method_disagreement.py",
   "id": "probe1",
   "role": "method-disagreement"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe2_negative_control.py",
   "id": "probe2",
   "role": "negative-control"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "FIRE manufactured_tally",
   "fired_on_bad_state": true,
   "good_state_output": "SILENT",
   "id": "CNL0057-C1",
   "kind": "known-broken-fixture",
   "preference_vote_output": "SILENT",
   "rejects": "vote-as-decision on a vote-harmful decision_class (plurality winner or mean scalar emitted as the council decision)",
   "silent_on_good_state": true,
   "verbatim": "The check rejects: vote-as-decision on a vote-harmful decision_class (plurality winner or mean scalar emitted as the council decision). On planted vote-on-diagnosis it prints 'FIRE manufactured_tally'. On synthesis-only of the same ballots it prints 'SILENT'. On a 2-1 preference vote it prints 'SILENT'."
  }
 ],
 "output_schema": "command-center/schema/council-design-note.schema.json",
 "produced_by": {
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "cursor"
 },
 "question": "For which decision types is a vote actively harmful (it manufactures a number where none exists), and what does synthesis-only owe the reader in place of a tally?",
 "report_kind": "council-design-note",
 "residual_unknowns": [
  {
   "claim": "Field-by-field alignment with 11-COUNCIL-SPECIFICATION.schema.json $defs for voting.",
   "settling_experiment": "Place the harness restore CouncilSpec schema on disk and diff VOTE_HARMFUL against named decision_class enums.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after two failed attempts on the same framing, enumerate at least two alternative decompositions before a third attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "counterexample": {
   "attempted": true,
   "id": "CX-unanimous-diagnosis-vote",
   "instance": "Three seats, identical cause 'cache', method=vote. A census number 3 exists. If the claim were 'any seat count is fake', this would refute. The claim is that vote-as-decision still manufactures a winner from a census; detect() still FIRE manufactured_tally.",
   "refutes": false
  },
  "fresh_context": true,
  "independent": true,
  "method": "reviewer.py re-derives plurality, mean, and live-set from fixture bytes with collections.Counter; it does not read the design note. Disagreement with the engine blocks.",
  "reviewer_id": "CNL-0057-reviewer-stdlib-recount",
  "verdict": "PASS"
 },
 "scalar_fixture": {
  "disagree": true,
  "held_by_any_seat": false,
  "held_values": [
   10.0,
   20.0,
   90.0
  ],
  "id": "FX-scalar-spread",
  "manufactured_scalar": 40.0,
  "reason": "method"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0057",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0057]",
 "state": "SUCCESS",
 "synthesis_only_owes": [
  "live_hypotheses",
  "seat_provenance",
  "census_not_winner",
  "no_tally_statement",
  "dissent_preserved",
  "next_measurement"
 ],
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe1_method_disagreement.py",
   "id": "T1-method-disagreement",
   "name": "Fixture where voting and synthesis-only disagree with reason attributed to the method rather than the participants",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0057/probe2_negative_control.py",
   "id": "T2-negative-control",
   "name": "Detector FIRES on planted vote-as-decision for diagnosis and is SILENT on synthesis-only of the same ballots and on a preference vote of the same 2-1 shape",
   "result": "PASS"
  }
 ],
 "tests_required_catalog": [
  "a fixture where voting and synthesis-only disagree, with the reason attributed to the method rather than the participants",
  "negative control recorded verbatim: state what the check does on the state it is meant to reject"
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:54:08Z",
  "started_at": "2026-08-24T18:33:00Z"
 },
 "title": "Synthesis-only mode: when taking no vote is the correct design",
 "unit_id": "CNL-0057",
 "vote_harmful_decision_types": [
  {
   "harm": "plurality names a unique cause; etiology is not a preference",
   "id": "diagnosis"
  },
  {
   "harm": "mean/median can be a value no seat held",
   "id": "scalar_estimate"
  },
  {
   "harm": "a tally does not create evidential support",
   "id": "evidence_interpretation"
  },
  {
   "harm": "majority is not semantics",
   "id": "meaning_of_text"
  },
  {
   "harm": "vote pretends incommensurable frames share a scale",
   "id": "incommensurable_synthesis"
  },
  {
   "harm": "preference vote launders an unresolved diagnosis",
   "id": "mixed_unsplit"
  }
 ],
 "vote_ok_decision_types": [
  "preference_choice",
  "resource_allocation",
  "procedure_selection"
 ]
}
