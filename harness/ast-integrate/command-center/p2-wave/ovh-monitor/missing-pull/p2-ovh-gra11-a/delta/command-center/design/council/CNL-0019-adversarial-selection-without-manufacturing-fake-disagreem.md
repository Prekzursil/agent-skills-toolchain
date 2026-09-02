{
 "answer": "Seat adversaries only by locked, evidence-backed priors on the question axis. A real prior conflict is opposite polarity plus distinct evidence_id plus a commitment_hash that recomputes from those fields before deliberation. An assigned debating position is assigned_stance or an oppositional role pair (advocate/critic, red/blue, and the other named pairs) that lacks that prior substrate, shares evidence, or contradicts the seat's own polarity. The selector refuses theatre rather than performing it. Role, from the CNL-0005 nine-dial list, is a label and is not a prior. Red/blue topology (CNL-0033) does not become informative by assigning those labels; without independent priors it is still theatre. Executable fixtures show the two rosters diverge: assigned-position has high public disagreement and near-zero revealed disagreement; real-prior has high disagreement on both channels.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0019/note.schema.json",
   "role": "unit-local-schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0019/seating.py",
   "role": "selector"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0019/simulate.py",
   "role": "simulator"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0019/fixtures.json",
   "role": "fixtures"
  }
 ],
 "catalog_inputs_on_tree": {
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": false,
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": false
 },
 "claim_under_test": "A real prior conflict is opposite locked polarities from distinct evidence_id values with verifying commitment hashes; assigned_stance or oppositional role pairs without that substrate are THEATRE and must be refused at seating. Assigned-position and real-prior rosters must produce measurably different revealed-channel disagreement.",
 "claims": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/simulate.py:3",
   "claim": "Assigned-position and real-prior rosters differ on revealed-channel disagreement by at least MEASURABLE_REVEALED_GAP.",
   "id": "C-THEATRE-DIVERGE",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/seating.py:86",
   "claim": "classify_roster FIRES on planted-bad and is SILENT on known-good.",
   "id": "C-BOTH-STATES",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/seating.py:65",
   "claim": "Oppositional roles without priors are THEATRE, not REAL_CONFLICT.",
   "id": "C-ROLE-IS-NOT-PRIOR",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:35244",
   "claim": "Harness-restore CouncilSpec input files are present on this worktree.",
   "id": "C-CATALOG-INPUTS-PRESENT",
   "verdict": "REFUTED"
  }
 ],
 "completion_sentinel": "SUCCESS:CNL-0019",
 "declared_signal": {
  "signal_1": {
   "field": "classify_roster.fired/reason",
   "kind": "file-line",
   "known_good": {
    "fired": false,
    "reason": "INDEPENDENT_OPPOSITE_PRIORS",
    "verdict": "REAL_CONFLICT"
   },
   "planted_bad": {
    "fired": true,
    "reason": "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
    "verdict": "THEATRE"
   }
  },
  "signal_2": {
   "field": "simulate.run_roster.revealed_disagreement",
   "gap": 1.0099642110838303,
   "kind": "numeric-revealed-disagreement",
   "real_prior": 1.0099642110838303,
   "theatre": 0.0
  }
 },
 "dependency_status": {
  "CNL-0005": {
   "artifact_path": "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md",
   "artifact_present": false
  },
  "CNL-0033": {
   "artifact_path": "command-center/design/council/CNL-0033-red-blue-adversarial-topology-with-asymmetric-mandates.md",
   "artifact_present": false
  }
 },
 "distinction": {
  "assigned_debating_position": {
   "code": "THEATRE",
   "definition": "Opposite assigned_stance or oppositional roles used as the conflict signal, including when priors are missing, shared, or same-sign."
  },
  "not_a_dial_from_cnl_0005": "The nine catalog dials are model, vendor, expertise, role, authority, vote weight, tools, effort, context. Prior is a seating substrate those dials do not provide.",
  "real_prior_conflict": {
   "code": "REAL_CONFLICT",
   "definition": "Two seats, same question axis, opposite prior polarity, different evidence_id, verifying commitment_hash, no assigned_stance contradiction."
  }
 },
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/seating.py:103",
   "claim": "Opposite assigned_stance with shared evidence_id is classified THEATRE, not a real prior conflict.",
   "kind": "file-line",
   "line": 103,
   "mechanism": "file-line-token",
   "path": "command-center/p2-wave/probes/CNL-0019/seating.py",
   "snippet": "TOKEN:THEATRE-OPPOSITE-STANCE-SHARED-EVIDENCE",
   "verbatim_output": "classify planted-bad fired=True reason=ASSIGNED_STANCE_CONTRADICTS_PRIOR",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/seating.py:141",
   "claim": "Independent opposite-polarity priors on the question axis classify as REAL_CONFLICT.",
   "kind": "file-line",
   "line": 141,
   "mechanism": "file-line-token",
   "path": "command-center/p2-wave/probes/CNL-0019/seating.py",
   "snippet": "TOKEN:REAL-PRIOR-CONFLICT",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/simulate.py:3",
   "claim": "Public and revealed channels share one update rule; only the anchor differs, so divergence is computed not asserted.",
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0019/probe1_theatre.py",
   "kind": "command-output",
   "line": 3,
   "mechanism": "simulation-channel-gap",
   "path": "command-center/p2-wave/probes/CNL-0019/simulate.py",
   "snippet": "Public channel follows assigned_stance when present (the performed debate).",
   "verbatim_output": "theatre_revealed=0.000000 real_revealed=1.009964 gap=1.009964",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0019/fixtures.json:22",
   "claim": "The assigned-position roster is a planted theatre fixture, not a live LLM run.",
   "kind": "file-line",
   "line": 22,
   "mechanism": "fixture-bytes",
   "path": "command-center/p2-wave/probes/CNL-0019/fixtures.json",
   "snippet": "Four seats, one shared prior, opposite assigned_stance labels. This is manufactured disagreement.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:35248",
   "claim": "The unit question is taken from this worktree's catalog row, not from an absent Windows prompt file.",
   "kind": "file-line",
   "line": 35248,
   "mechanism": "catalog-question-text",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "How do you seat participants with genuinely conflicting priors while preventing the failure where the council performs disagreement it does not hold",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:34549",
   "claim": "CNL-0005 names nine per-seat dials; none of them is a locked prior. Role is not a substitute for prior.",
   "kind": "file-line",
   "line": 34549,
   "mechanism": "catalog-dependency-dials",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "complete participant descriptor type covering model, vendor, expertise, role, authority, vote weight, tools, effort and context",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "catalog-inputs-absent",
   "claim": "Catalog-cited CouncilSpec input files from the 20260806 harness restore are present on this worktree.",
   "kind": "path-is-file",
   "line": 35244,
   "mechanism": "path-is-file",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "CNL-0019-adversarial-selection-without-manufacturing-fake-disagreem.md",
   "verdict": "REFUTED"
  },
  {
   "anchor": "dependency-artifacts-absent",
   "claim": "CNL-0005 and CNL-0033 output artifacts are on disk and were read before seating.",
   "kind": "path-is-file",
   "line": 65,
   "mechanism": "path-is-file",
   "path": "command-center/p2-wave/probes/CNL-0019/seating.py",
   "snippet": "TOKEN:THEATRE-OPPOSITIONAL-ROLES-WITHOUT-PRIOR",
   "verdict": "REFUTED"
  }
 ],
 "live_llm_council_run": false,
 "markdown_note": "# Adversarial selection without manufacturing fake disagreement\n\n## Distinction\nA real prior conflict is a pair of seats whose locked priors on the\nquestion axis have opposite polarity, different evidence_id values,\nand commitment hashes that recompute from those fields before\ndeliberation. An assigned debating position is a prompt- or\nrole-imposed stance (assigned_stance, or an oppositional role pair)\nthat does not rest on such priors. The first is a property of belief\nstate. The second is theatre: the council performs disagreement it\ndoes not hold.\n\n## Selector\nadversarial_select refuses THEATRE. It never invents a prior, never\nflips a polarity to create conflict, and never treats CNL-0005 role\nas a prior. naive_select, which seats opposite labels, is the\nbehaviour this unit rejects.\n\n## Convergence\nSame update rule on public (performed) and revealed (belief) channels.\nTheatre: high public disagreement, low revealed disagreement.\nReal-prior: high disagreement on both channels.\n\nSUCCESS:CNL-0019",
 "mechanism": {
  "module": "command-center/p2-wave/probes/CNL-0019/seating.py",
  "refuse_on": [
   "ASSIGNED_STANCE_WITHOUT_PRIOR",
   "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
   "OPPOSITE_STANCE_SHARED_EVIDENCE",
   "OPPOSITE_STANCE_SHARED_POLARITY",
   "OPPOSITIONAL_ROLES_WITHOUT_PRIOR",
   "OPPOSITIONAL_ROLES_SHARED_POLARITY",
   "COMMITMENT_MISMATCH",
   "AXIS_MISMATCH",
   "CONFLICT_CLAIM_SHARED_EVIDENCE"
  ],
  "simulator": "command-center/p2-wave/probes/CNL-0019/simulate.py",
  "thresholds_declared_before_scoring": {
   "ALPHA": 0.35,
   "MEASURABLE_REVEALED_GAP": 0.5,
   "REAL_PUBLIC_MIN": 1.0,
   "REAL_REVEALED_MIN": 1.0,
   "ROUNDS": 8,
   "THEATRE_PUBLIC_MIN": 1.0,
   "THEATRE_REVEALED_MAX": 0.25
  },
  "update_rule": "vote_i,t = (1 - (1-confidence_i)*alpha)*anchor_i + ((1-confidence_i)*alpha)*mean(others). Public anchor is assigned_stance if present else prior; revealed anchor is prior."
 },
 "negative_controls": [
  {
   "check": "adversarial_select",
   "fires": true,
   "id": "planted-bad-theatre-roster",
   "observed": "negative-control target=planted-bad naive_select.verdict=NAIVE_ACCEPT naive_select.seated=['BAD-PRO', 'BAD-CON'] adversarial_select.rejected=True adversarial_select.reason=ASSIGNED_STANCE_CONTRADICTS_PRIOR",
   "rejects": "opposite assigned_stance with shared same-sign prior (the state naive_select would seat)"
  }
 ],
 "output_schema_catalog": "command-center/schema/council-design-note.schema.json",
 "output_schema_validated_against": "command-center/p2-wave/probes/CNL-0019/note.schema.json",
 "question": "How do you seat participants with genuinely conflicting priors while preventing the failure where the council performs disagreement it does not hold - what distinguishes a real prior conflict from an assigned debating position?",
 "reviewer": {
  "behavioral_second_field": {
   "bad_theatre_signature": true,
   "good_theatre_signature": false
  },
  "cross_vendor_openai_gpt5_codex_seated": false,
  "cross_vendor_reason": "Catalog asked for openai/gpt-5-codex to re-run this control. No such seat is mounted on this worktree. This reviewer is a second mechanical execution of the same fixtures via structural classify_roster and behavioral theatre_signature (different data fields). A review that did not execute the control is rejected; this one did.",
  "independent": true,
  "re_ran_both_states": true,
  "reviewer_id": "CNL-0019-probe2-both-states-reexecution",
  "scope_not_agreement": true,
  "structural": {
   "fired": true,
   "reason": "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
   "verdict": "THEATRE"
  },
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0019",
 "shared_schema_note": "Catalog names command-center/schema/council-design-note.schema.json. That file is contended by parallel CNL units on this worktree. This note is validated against the unit-local schema.",
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "A later prompt can still instruct seated models to perform opposition even after this selector has refused theatre at seating time. This unit gates roster construction; it does not claim a runtime prompt firewall. Residual risk is named, not closed.",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0019/probe1_theatre.py",
   "id": "theatre-probe",
   "measured": {
    "measurably_different": true,
    "real_ok": true,
    "real_public_disagreement": 1.0099642110838303,
    "real_revealed_disagreement": 1.0099642110838303,
    "revealed_gap": 1.0099642110838303,
    "theatre_ok": true,
    "theatre_public_disagreement": 1.271828665568369,
    "theatre_revealed_disagreement": 0.0
   },
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0019/probe2_both_states.py",
   "id": "both-states",
   "measured": {
    "bad_reason": "ASSIGNED_STANCE_CONTRADICTS_PRIOR",
    "behav_bad_theatre_signature": true,
    "behav_good_theatre_signature": false,
    "fired_on_bad": true,
    "good_reason": "INDEPENDENT_OPPOSITE_PRIORS",
    "role_only_reason": "OPPOSITIONAL_ROLES_WITHOUT_PRIOR",
    "silent_on_good": true
   },
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0019/probe2_both_states.py",
   "id": "negative-control",
   "result": "PASS",
   "verbatim": "negative-control target=planted-bad naive_select.verdict=NAIVE_ACCEPT naive_select.seated=['BAD-PRO', 'BAD-CON'] adversarial_select.rejected=True adversarial_select.reason=ASSIGNED_STANCE_CONTRADICTS_PRIOR",
   "what_the_check_does_on_the_state_it_rejects": "On planted-bad (opposite assigned_stance, shared evidence, same prior polarity), adversarial_select raises TheatreReject with reason=ASSIGNED_STANCE_CONTRADICTS_PRIOR. naive_select would have seated ['BAD-PRO', 'BAD-CON']."
  }
 ],
 "title": "Adversarial selection without manufacturing fake disagreement",
 "ts": "2026-08-25T00:52:10Z",
 "unit_id": "CNL-0019",
 "which_stops_the_round": {
  "does_not_stop": "High public disagreement on a REAL_CONFLICT roster is deliberation, not a seating reject.",
  "satisfy_quota_from_padding": false,
  "stops": "THEATRE at seating: adversarial_select raises TheatreReject and does not emit a roster."
 }
}
