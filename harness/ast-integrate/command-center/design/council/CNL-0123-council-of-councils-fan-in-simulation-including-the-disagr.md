{
 "answer": {
  "does_not_emit": "PASS",
  "parent_emits": "DISAGREEMENT",
  "proof": "Holding the three verdict labels fixed and changing only child-gamma's evidence body changes the honest parent_digest (44c212ec0163\u2026 vs edc0f5e8054a\u2026). The vote-counting parent's digest does not move and still emits PASS.",
  "proved_evidence_was_read": true
 },
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0123-council-of-councils-fan-in-simulation-including-the-disagr.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-simulation-spec.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0123/fanin.py",
   "role": "harness"
  }
 ],
 "declared_outcome": {
  "child_verdicts": [
   "PASS",
   "PASS",
   "REFUTED"
  ],
  "fixture_id": "split-2-pass-1-refuted",
  "parent_verdict": "DISAGREEMENT",
  "rejected_parent_verdict": "PASS",
  "why_not_majority": "Two PASS vs one REFUTED is the majority-PASS trap. Spec:11343 names nested councils disagreeing on completion as a failure class. A single merged PASS with no trace of gamma is REFUTED."
 },
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:40519",
   "claim": "CNL-0123 evidence_requirement restates spec:11343 on this tree",
   "line": 40519,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "the fan-in gate rule that a digest is a claim and not a receipt applies to child councils"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:33440",
   "claim": "CNF-0174 restates spec:11343: disagreement must surface, not average",
   "line": 33440,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "Spec:11343 names 'nested councils disagree on completion' as a required failure class"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:89326",
   "claim": "TST-0285 restates the parent must not average nested verdicts",
   "line": 89326,
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "The parent must apply the ONE shared completion predicate (CC-0003) rather than a local rule, must not average the verdicts"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0123/fanin.py:129",
   "claim": "honest parent emits DISAGREEMENT on mixed live child verdicts",
   "line": 129,
   "path": "command-center/p2-wave/probes/CNL-0123/fanin.py",
   "snippet": "verdict, reason = DISAGREEMENT, \"nested-councils-disagree-on-completion\""
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0123/fanin.py:158",
   "claim": "vote-count parent is the planted evidence-blind control, not the spec",
   "line": 158,
   "path": "command-center/p2-wave/probes/CNL-0123/fanin.py",
   "snippet": "Known-broken parent: hashes only (id, verdict). Ignores evidence."
  }
 ],
 "fan_in_rule": {
  "digest_is_claim": true,
  "double_count": "duplicate child ids are rejected before tally",
  "id": "surface-split-never-majority",
  "majority_forbidden": true,
  "parent_on_split": "DISAGREEMENT",
  "pass_requires": "every child RECEIPT-OK and unanimous PASS",
  "unread_child": "parent must not overrule a child whose evidence file it did not read"
 },
 "harness": {
  "deterministic": true,
  "kind": "deterministic-scripted-child-returns",
  "module": "command-center/p2-wave/probes/CNL-0123/fanin.py",
  "not_production_runtime": true,
  "note": "CNL-0117 (scripted-participant harness) and CNL-0037 (fan-in design note) are not on disk. This unit ships its own scripted fan-in under probes/CNL-0123/. It is a simulation of the parent rule, not a second production completion reducer."
 },
 "negative_controls": [
  {
   "fired": true,
   "id": "vote-count-parent-evidence-blind",
   "rejects": "a parent that emits majority PASS and whose digest does not move when only child evidence changes",
   "verbatim": "NEGATIVE CONTROL (evidence-blind parent): On the vote-counting parent that hashes only child verdict labels, perturbing child EVIDENCE while holding the three verdicts fixed (2 PASS, 1 REFUTED) leaves the parent digest unchanged and the parent still emits PASS (majority of labels). The check is meant to reject that parent: it MUST report evidence_blind=true and must NOT treat majority-PASS as the declared outcome. Observed on the planted vote-counter: digest_moved=false, parent_verdict=PASS."
  }
 ],
 "oracles": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0123/probe1_split_children.py",
   "id": "A-scripted-replay",
   "kind": "scripted-participant replay"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0123/probe2_evidence_blind.py",
   "id": "B-evidence-digest-diff",
   "kind": "transcript digest diff"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0123/probe2_evidence_blind.py",
   "id": "C-vote-counter-assertion",
   "kind": "counter assertion"
  }
 ],
 "output_schema": "command-center/schema/council-simulation-spec.schema.json",
 "question": "When three child councils return two PASS and one REFUTED, what does the parent emit - and does the simulation prove the parent read the child evidence rather than counting verdicts?",
 "residual_unknowns": [
  "CNL-0117 and CNL-0037 catalog outputs are absent; this simulation does not import them.",
  "CC-0003 shared reducer is not on disk; this parent is a design-simulation, not a claim that production fan-in already imports CC-0003.",
  "_USER-PROMPTS.md:11343 is cited via catalog restatements; the Windows harness-restore path is not on this Linux worktree."
 ],
 "reviewer": {
  "cross_vendor_live_session": false,
  "executed_both_states": true,
  "independent": true,
  "note": "Catalog asks openai/gpt-5-codex to re-run both-states. This worktree did not dispatch a vendor session. probe2 re-runs split vs all-pass and the evidence-perturbation control from the fixtures; a review that only read this prose would fail that probe.",
  "reviewer_id": "CNL-0123-probe2-both-states-retabulation",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "schema_note": "Catalog output_schema command-center/schema/council-simulation-spec.schema.json is a generated $ref shim to https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json which does not resolve on this worktree. This spec is JSON-parseable with state=SUCCESS. No ADV rebuild of that schema was attempted.",
 "sentinel": "SUCCESS:CNL-0123",
 "simulation": {
  "all_pass": {
   "children": [
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/all_pass/evidence/alpha.json",
     "evidence_sha256": "d98e32e7f8254cc686aeb3d745a6ebd077f8af975c782768b4132f4947c88e91",
     "id": "child-alpha",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/all_pass/evidence/beta.json",
     "evidence_sha256": "1b24cdab4ba082d735d5cbac7bbc86ec7d7553d0669f2417713e42065c467f16",
     "id": "child-beta",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/all_pass/evidence/gamma.json",
     "evidence_sha256": "d6fe78adf727984fd8b53978cc7f97a2f10d9af353a6b708e348ebc110fea11c",
     "id": "child-gamma",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    }
   ],
   "distinct_live_verdicts": [
    "PASS"
   ],
   "distinct_source_count": 3,
   "majority_of_labels": "PASS",
   "minority_ids": [],
   "parent_digest": "1a94a33d738fece7dc382dea856a96414bdb8cabf1188ea7fc2ecba0250deea1",
   "reason": "unanimous-pass-with-receipts",
   "tally": {
    "PASS": 3
   },
   "verdict": "PASS"
  },
  "evidence_blind_control_fired": true,
  "honest_digest_moved": true,
  "labels_held_fixed": true,
  "missing_receipt": {
   "children": [
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/missing_receipt/evidence/alpha.json",
     "evidence_sha256": "5598b94370b01faabe58bcc332e544a18a150a3640b27d272c13af67d71a28ee",
     "id": "child-alpha",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/missing_receipt/evidence/beta.json",
     "evidence_sha256": "4246116ed1dfd9fa74b889aac97e7df907ad9e4aa0f1190ee014c6e798f2a2df",
     "id": "child-beta",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/missing_receipt/evidence/gamma-absent.json",
     "evidence_sha256": null,
     "id": "child-gamma",
     "live_verdict": null,
     "receipt_status": "CLAIM-NOT-RECEIPT"
    }
   ],
   "distinct_live_verdicts": [
    "PASS"
   ],
   "distinct_source_count": 3,
   "majority_of_labels": "PASS",
   "minority_ids": [],
   "parent_digest": "3f402978fe89694e8c5595b465ef7e97721a90c634a35bda3e9e0e61f0132f59",
   "reason": "claim-not-receipt",
   "tally": {
    "CLAIM-NOT-RECEIPT": 1,
    "PASS": 2
   },
   "verdict": "DISAGREEMENT"
  },
  "paths_held_fixed": true,
  "perturbed": {
   "children": [
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/alpha.json",
     "evidence_sha256": "887c6b275caea8868fbc4367a7c2f5c2fdc240b3d3643ebaef521567b44c7218",
     "id": "child-alpha",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/beta.json",
     "evidence_sha256": "e9dbe975de2226830f3567f4145cb623e62a7f0cc81fc71cc18fb4ec4fc4d140",
     "id": "child-beta",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "REFUTED",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/gamma.json",
     "evidence_sha256": "72dbd8b048933bd0639cf5cd7a2bd183ee4c70e988e73cd0bb75771a9a94e89c",
     "id": "child-gamma",
     "live_verdict": "REFUTED",
     "receipt_status": "RECEIPT-OK"
    }
   ],
   "distinct_live_verdicts": [
    "PASS",
    "REFUTED"
   ],
   "distinct_source_count": 3,
   "majority_of_labels": "PASS",
   "minority_ids": [
    "child-gamma"
   ],
   "parent_digest": "edc0f5e8054ab629594bb5de401a376ebbe0eeeaa56b3c3605a38e86ef6f9d56",
   "reason": "nested-councils-disagree-on-completion",
   "tally": {
    "PASS": 2,
    "REFUTED": 1
   },
   "verdict": "DISAGREEMENT"
  },
  "perturbed_parent_digest": "edc0f5e8054ab629594bb5de401a376ebbe0eeeaa56b3c3605a38e86ef6f9d56",
  "split": {
   "children": [
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/alpha.json",
     "evidence_sha256": "887c6b275caea8868fbc4367a7c2f5c2fdc240b3d3643ebaef521567b44c7218",
     "id": "child-alpha",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "PASS",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/beta.json",
     "evidence_sha256": "e9dbe975de2226830f3567f4145cb623e62a7f0cc81fc71cc18fb4ec4fc4d140",
     "id": "child-beta",
     "live_verdict": "PASS",
     "receipt_status": "RECEIPT-OK"
    },
    {
     "claimed_verdict": "REFUTED",
     "evidence_path": "command-center/p2-wave/probes/CNL-0123/fixtures/split/evidence/gamma.json",
     "evidence_sha256": "bace4b7dbb10b45e83c30ea86abec169ccf1f462cde7ee6d21776c2af21c07a5",
     "id": "child-gamma",
     "live_verdict": "REFUTED",
     "receipt_status": "RECEIPT-OK"
    }
   ],
   "distinct_live_verdicts": [
    "PASS",
    "REFUTED"
   ],
   "distinct_source_count": 3,
   "majority_of_labels": "PASS",
   "minority_ids": [
    "child-gamma"
   ],
   "parent_digest": "44c212ec01630c13c1582f4577b2c9a9e30417423b2ca78007d9b96d801e05dc",
   "reason": "nested-councils-disagree-on-completion",
   "tally": {
    "PASS": 2,
    "REFUTED": 1
   },
   "verdict": "DISAGREEMENT"
  },
  "split_parent_digest": "44c212ec01630c13c1582f4577b2c9a9e30417423b2ca78007d9b96d801e05dc",
  "vote_counter_verdict_on_split": "PASS",
  "vote_digest_moved": false,
  "vote_perturbed_digest": "ee313b10aedba799e74b1bc35ab728989a9daf91e91f84256078fe20641abd3e",
  "vote_split_digest": "ee313b10aedba799e74b1bc35ab728989a9daf91e91f84256078fe20641abd3e"
 },
 "simulation_id": "cnl-0123-split-2-pass-1-refuted",
 "spec_anchors": {
  "digest_is_claim": "fan-in gate: a digest is a claim and not a receipt; applies to child councils exactly as to subagents",
  "nested_disagreement": "_USER-PROMPTS.md:11343",
  "on_disk_restatement": "command-center/WORK-UNIT-CATALOG.json CNL-0123 / CNF-0174 / TST-0285"
 },
 "state": "SUCCESS",
 "strongest_surviving_counterargument": "A parent could fold evidence hashes and still decide by majority, so a moving digest alone would not prove DISAGREEMENT is the rule. That is why probe1 also asserts parent_verdict != majority_of_labels on the same fixture, and why the vote-counter (majority PASS, digest frozen) is the named reject state.",
 "tests": [
  {
   "id": "split-children-declared-outcome",
   "observation": "split parent_verdict=DISAGREEMENT tally={'PASS': 2, 'REFUTED': 1} majority_of_labels=PASS",
   "result": "PASS"
  },
  {
   "id": "evidence-blind-parent-detectable",
   "observation": "honest_digest_moved=True vote_digest_moved=False vote_verdict=PASS",
   "result": "PASS"
  },
  {
   "id": "both-states-unanimous-pass",
   "observation": "all_pass parent_verdict=PASS (must stay PASS so DISAGREEMENT is not a constant)",
   "result": "PASS"
  },
  {
   "id": "digest-is-claim-missing-file",
   "observation": "missing-receipt parent_verdict=DISAGREEMENT gamma receipt=CLAIM-NOT-RECEIPT despite claimed PASS + planted digest",
   "result": "PASS"
  }
 ],
 "title": "Council-of-councils fan-in simulation including the disagreement case",
 "ts": "2026-08-25T00:55:06Z",
 "unit_id": "CNL-0123"
}
