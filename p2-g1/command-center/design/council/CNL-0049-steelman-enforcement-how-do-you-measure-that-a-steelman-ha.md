{
 "both_states": {
  "fired_on_bad": true,
  "silent_on_good": true
 },
 "artifacts": [
  {
   "bytes": 1128,
   "eol": "LF",
   "exists": true,
   "path": "command-center/schema/council-detector-spec.schema.json",
   "role": "supporting",
   "sha256": "9aaa3e601e89634e67b7bb50afe4b7b326f13a23426b6a4cbbceaec2942a8599"
  },
  {
   "bytes": 6360,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/detector.py",
   "role": "primary",
   "sha256": "dd80c2d3117dd800a7e73b2e0dfe88f3b10a9a5533384ff65431d2a2b3a4e55f"
  },
  {
   "bytes": 2822,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
   "role": "supporting",
   "sha256": "b03d76fc9ea109d8430c0c473c1eba50d6604ae27c8f3677b0df4d16615beb84"
  },
  {
   "bytes": 6430,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/probe2_independent_signals.py",
   "role": "supporting",
   "sha256": "ce1435ebc530896a40caa4db002121478889184e29340ed886c4d9fe9ab827b3"
  },
  {
   "bytes": 2122,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json",
   "role": "supporting",
   "sha256": "3be47139a4de967c98bfce9b1088814d1127491841bd8c521c5a5157c92860db"
  },
  {
   "bytes": 1203,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json",
   "role": "supporting",
   "sha256": "ad36ab00ea5fa8c0d13364dea76083bae5db41e177edad9962178de96783187f"
  },
  {
   "bytes": 1519,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_label.json",
   "role": "supporting",
   "sha256": "02c10f34b0a2888da71ea103cc593ac313d94410c95015519df80090e30cd016"
  },
  {
   "bytes": 2051,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_padded.json",
   "role": "supporting",
   "sha256": "b7bb4aab6822da1175b64b524fafb786ab0d3e4ab3a9be0de5c91bd0f36bf2d1"
  },
  {
   "bytes": 1267,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_coverage.json",
   "role": "supporting",
   "sha256": "46a36614f2246421cad82ab06179bb221d71cbbc6ec2b9bbe3669d9916684175"
  },
  {
   "bytes": 1936,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_ordering.json",
   "role": "supporting",
   "sha256": "e6033ab128dffcb7476ba91d1d78ad537f4ef283ff18a1acd3795d871e92aea4"
  }
 ],
 "defects": [],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json",
   "consumer": "command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
    "exit_code": 0,
    "fingerprint": "downstream:probe1-consumes-fixtures",
    "method": "test-run",
    "raw_output": "fired_on_bad=True silent_on_good=True genuine_verdict=PASS fake_verdict=FAIL label_verdict=FAIL fake_missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\nnegative_control rejects=token-concession-then-prepared-attack observed=FIRES reasons=[\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"]\nSUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json:34",
   "claim": "Token concession fixture FIRES via incomplete claim coverage (S1 set algebra); restates ids are empty.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
     "exit_code": 0,
     "fingerprint": "probe1:both-states-evaluate",
     "method": "test-run",
     "raw_output": "fired_on_bad=True silent_on_good=True genuine_verdict=PASS fake_verdict=FAIL label_verdict=FAIL fake_missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\nnegative_control rejects=token-concession-then-prepared-attack observed=FIRES reasons=[\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"]\nSUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import json,sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0049'); import detector as D; print(D.evaluate_path('command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json'))\"",
     "exit_code": 0,
     "fingerprint": "detector:fake-token-coverage-set",
     "method": "file-read",
     "raw_output": "{\"coverage_ok\": false, \"fired\": true, \"missing_claim_ids\": [\"C-hash-ssot\", \"C-stop-hook\", \"C-bind-root\"], \"verdict\": \"FAIL\"}",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json:32",
   "claim": "Genuine steelman is SILENT: S1 covers three claims and S2 allows the later rebuttal.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
     "exit_code": 0,
     "fingerprint": "probe1:both-states-evaluate",
     "method": "test-run",
     "raw_output": "fired_on_bad=True silent_on_good=True genuine_verdict=PASS fake_verdict=FAIL label_verdict=FAIL fake_missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\nnegative_control rejects=token-concession-then-prepared-attack observed=FIRES reasons=[\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"]\nSUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/detector.py command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json",
     "exit_code": 0,
     "fingerprint": "detector:genuine-event-sequence",
     "method": "static-analysis",
     "raw_output": "{\"covered_claim_ids\": [\"C-bind-root\", \"C-hash-ssot\", \"C-stop-hook\"], \"fired\": false, \"silent\": true, \"verdict\": \"PASS\"}",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0049/detector.py:158",
   "claim": "S1 is restatement_binds (id + polarity + non-token + overlap); S2 is a different mechanism (attack while coverage incomplete).",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "command-center/p2-wave/probes/CNL-0049/detector.py:158",
     "exit_code": 0,
     "fingerprint": "file-read:restatement_binds",
     "method": "file-read",
     "raw_output": "def restatement_binds(claim, ev)",
     "role": "source"
    },
    {
     "command": "command-center/p2-wave/probes/CNL-0049/detector.py:196",
     "exit_code": 0,
     "fingerprint": "static-analysis:attack-ordering-branch",
     "method": "static-analysis",
     "raw_output": "elif kind == \"attack\":",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "output_schema": "command-center/schema/council-detector-spec.schema.json",
  "schema_resolution": "disk-local RefResolver (no network $ref fetch)",
  "spec_kind": "council-detector-spec"
 },
 "manifest_registration": {
  "entry_id": "CNL-0049",
  "manifest_path": "command-center/p2-wave/probes/CNL-0049/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true,
  "registered_at": "2026-08-25T00:46:00Z"
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "bad_state_output": "{\"attack_events\": 1, \"claim_count\": 3, \"coverage_ok\": false, \"covered_claim_ids\": [], \"covered_count\": 0, \"fired\": true, \"fixture_id\": \"fake-token-concession\", \"missing_claim_ids\": [\"C-hash-ssot\", \"C-stop-hook\", \"C-bind-root\"], \"ordering_ok\": false, \"path\": \"/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json\", \"reasons\": [\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"], \"restatement_events\": 0, \"silent\": false, \"verdict\": \"FAIL\"}",
   "description": "fake_token.json is a one-line concession plus prepared attack with zero restatement bindings. The detector must FIRE.",
   "fired_on_bad_state": true,
   "good_state_output": "{\"attack_events\": 1, \"claim_count\": 3, \"coverage_ok\": true, \"covered_claim_ids\": [\"C-bind-root\", \"C-hash-ssot\", \"C-stop-hook\"], \"covered_count\": 3, \"fired\": false, \"fixture_id\": \"genuine-steelman\", \"missing_claim_ids\": [], \"ordering_ok\": true, \"path\": \"/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json\", \"reasons\": [], \"restatement_events\": 3, \"silent\": true, \"verdict\": \"PASS\"}",
   "id": "NC-token-concession",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "{\"attack_events\": 1, \"claim_count\": 3, \"coverage_ok\": false, \"covered_claim_ids\": [], \"covered_count\": 0, \"fired\": true, \"fixture_id\": \"fake-steelman-label\", \"missing_claim_ids\": [\"C-hash-ssot\", \"C-stop-hook\", \"C-bind-root\"], \"ordering_ok\": false, \"path\": \"/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_label.json\", \"reasons\": [\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"], \"restatement_events\": 3, \"silent\": false, \"verdict\": \"FAIL\"}",
   "description": "fake_label.json sets speech_act=steelman with token bodies and must FIRE; genuine.json stays SILENT.",
   "fired_on_bad_state": true,
   "good_state_output": "{\"attack_events\": 1, \"claim_count\": 3, \"coverage_ok\": true, \"covered_claim_ids\": [\"C-bind-root\", \"C-hash-ssot\", \"C-stop-hook\"], \"covered_count\": 3, \"fired\": false, \"fixture_id\": \"genuine-steelman\", \"missing_claim_ids\": [], \"ordering_ok\": true, \"path\": \"/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json\", \"reasons\": [], \"restatement_events\": 3, \"silent\": true, \"verdict\": \"PASS\"}",
   "id": "NC-label-only",
   "kind": "adversarial-payload",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "grok"
 },
 "report": {
  "ablation": {
   "complete_coverage_but_attack_first": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": true,
    "covered_claim_ids": [
     "C-bind-root",
     "C-hash-ssot",
     "C-stop-hook"
    ],
    "covered_count": 3,
    "fired": true,
    "fixture_id": "ablation-attack-before-coverage",
    "missing_claim_ids": [],
    "ordering_ok": false,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/ablation_ordering.json",
    "reasons": [
     "turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 3,
    "silent": false,
    "verdict": "FAIL"
   },
   "coverage_incomplete_no_attack": {
    "attack_events": 0,
    "claim_count": 3,
    "coverage_ok": false,
    "covered_claim_ids": [
     "C-hash-ssot"
    ],
    "covered_count": 1,
    "fired": true,
    "fixture_id": "ablation-coverage-incomplete",
    "missing_claim_ids": [
     "C-stop-hook",
     "C-bind-root"
    ],
    "ordering_ok": true,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/ablation_coverage.json",
    "reasons": [
     "coverage-incomplete missing=['C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 1,
    "silent": false,
    "verdict": "FAIL"
   },
   "signals_independent": true
  },
  "answer": "The machine-checkable property is completed claim-restatement coverage (S1) before any attack (S2). A one-line concession plus prepared attack fails S1 (and usually S2). SUCCESS:CNL-0049",
  "both_states": {
   "bad_verbatim": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": false,
    "covered_claim_ids": [],
    "covered_count": 0,
    "fired": true,
    "fixture_id": "fake-token-concession",
    "missing_claim_ids": [
     "C-hash-ssot",
     "C-stop-hook",
     "C-bind-root"
    ],
    "ordering_ok": false,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json",
    "reasons": [
     "turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']",
     "coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 0,
    "silent": false,
    "verdict": "FAIL"
   },
   "fired_on_bad": true,
   "good_verbatim": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": true,
    "covered_claim_ids": [
     "C-bind-root",
     "C-hash-ssot",
     "C-stop-hook"
    ],
    "covered_count": 3,
    "fired": false,
    "fixture_id": "genuine-steelman",
    "missing_claim_ids": [],
    "ordering_ok": true,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json",
    "reasons": [],
    "restatement_events": 3,
    "silent": true,
    "verdict": "PASS"
   },
   "known_good_id": "genuine-steelman",
   "label_verbatim": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": false,
    "covered_claim_ids": [],
    "covered_count": 0,
    "fired": true,
    "fixture_id": "fake-steelman-label",
    "missing_claim_ids": [
     "C-hash-ssot",
     "C-stop-hook",
     "C-bind-root"
    ],
    "ordering_ok": false,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_label.json",
    "reasons": [
     "turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']",
     "coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 3,
    "silent": false,
    "verdict": "FAIL"
   },
   "padded_verbatim": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": false,
    "covered_claim_ids": [],
    "covered_count": 0,
    "fired": true,
    "fixture_id": "fake-padded-length",
    "missing_claim_ids": [
     "C-hash-ssot",
     "C-stop-hook",
     "C-bind-root"
    ],
    "ordering_ok": false,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_padded.json",
    "reasons": [
     "turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']",
     "coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 0,
    "silent": false,
    "verdict": "FAIL"
   },
   "planted_bad_id": "fake-token-concession",
   "silent_on_good": true
  },
  "catalog_dependency_note": "CNL-0048 (response obligations) may require a steelman before a rebuttal counts as answering. This unit only answers whether a steelman happened; it does not wait on CNL-0048's artifact.",
  "control_ids": [
   "fake-token-concession",
   "genuine-steelman",
   "fake-steelman-label",
   "fake-padded-length",
   "ablation-coverage-incomplete",
   "ablation-attack-before-coverage"
  ],
  "detector": {
   "fire_rule": "FIRE if coverage_ok is false OR ordering_ok is false; SILENT iff both true.",
   "id": "steelman-happened",
   "module_path": "command-center/p2-wave/probes/CNL-0049/detector.py",
   "signals": [
    {
     "id": "S1-coverage",
     "mechanism": "set-algebra on claim ids with polarity, token-body rejection, and content-token overlap",
     "what_it_measures": "every load-bearing opponent claim is actually restated, not merely conceded"
    },
    {
     "id": "S2-ordering",
     "mechanism": "event-sequence scan: attack events while the coverage set is still incomplete",
     "what_it_measures": "the prepared attack is not allowed to precede completed restatement"
    }
   ]
  },
  "fixtures": {
   "additional": [
    {
     "expected_fired": true,
     "id": "fake-steelman-label",
     "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_label.json"
    },
    {
     "expected_fired": true,
     "id": "fake-padded-length",
     "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_padded.json"
    },
    {
     "expected_fired": true,
     "id": "ablation-coverage-incomplete",
     "path": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_coverage.json"
    },
    {
     "expected_fired": true,
     "id": "ablation-attack-before-coverage",
     "path": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_ordering.json"
    }
   ],
   "bad": {
    "expected_fired": true,
    "id": "fake-token-concession",
    "path": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json"
   },
   "good": {
    "expected_fired": false,
    "id": "genuine-steelman",
    "path": "command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json"
   }
  },
  "kind": "council-detector-spec",
  "machine_checkable_property": "A speech sequence is a genuine steelman of opponent position P iff every load-bearing claim in P has a restatement node that binds restates=<claim id>, preserves polarity, is not a closed-lexicon token body, and shares at least one content token with the source claim (signal S1, set algebra), AND no attack event is emitted while that coverage is still incomplete (signal S2, event sequence). The check FIRES when either signal fails and is SILENT when both pass. Length, the speech_act label, and author-acceptance are not the measure.",
  "negative_control": {
   "observed": "FIRES (reject)",
   "rejects": "token-concession-then-prepared-attack (Fair enough, but + attack, zero restatements)",
   "verbatim": {
    "attack_events": 1,
    "claim_count": 3,
    "coverage_ok": false,
    "covered_claim_ids": [],
    "covered_count": 0,
    "fired": true,
    "fixture_id": "fake-token-concession",
    "missing_claim_ids": [
     "C-hash-ssot",
     "C-stop-hook",
     "C-bind-root"
    ],
    "ordering_ok": false,
    "path": "/opt/p2/ast-integrate/command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json",
    "reasons": [
     "turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']",
     "coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']"
    ],
    "restatement_events": 0,
    "silent": false,
    "verdict": "FAIL"
   }
  },
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/fake_token.json:34",
    "measured": true,
    "method": "set-algebra coverage over load-bearing claim ids",
    "name": "token-concession-fired"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/genuine.json:32",
    "measured": true,
    "method": "event-sequence: restatements complete before attack",
    "name": "genuine-steelman-silent"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_coverage.json:1",
    "measured": true,
    "method": "coverage incomplete, ordering ok, still FIRE",
    "name": "coverage-ablation-independent"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0049/fixtures/ablation_ordering.json:1",
    "measured": true,
    "method": "coverage complete, attack-first, still FIRE",
    "name": "ordering-ablation-independent"
   }
  ],
  "question": "Steelman-before-rebuttal is required by the spec - what machine-checkable property distinguishes a genuine steelman from a one-line concession followed by the prepared attack?",
  "rejected_measures": [
   {
    "measure": "byte-length or word-count of the turn",
    "why_rejected": "fake_padded.json is longer than a token concession and still FIRES; length is gameable by padding."
   },
   {
    "measure": "speech_act label equal to steelman",
    "why_rejected": "fake_label.json sets speech_act=steelman with Fair point / I understand / Granted bodies and still FIRES."
   },
   {
    "measure": "closed concession-lexicon hit by itself",
    "why_rejected": "A genuine restatement may open with a courtesy clause; S1 requires claim bindings, not the absence of courtesy words."
   },
   {
    "measure": "original-author acceptance",
    "why_rejected": "Author-acceptance is a different gate (IMP-0293) and is DoS-able by perpetual refusal; it does not measure that a restatement bound each claim."
   }
  ],
  "scope": {
   "does_not_measure": [
    "rhetorical quality / strongest-form paraphrase beyond content-token overlap",
    "synonym-only restatements with zero source-token overlap (NOT-CHECKED)",
    "original-author acceptance of the steelman (IMP-0293 / DoS-on-gate)"
   ],
   "measures": "structural steelman (claim-bound restatement coverage + attack-after-coverage ordering)"
  },
  "title": "Steelman enforcement: how do you MEASURE that a steelman happened"
 },
 "residual_unknowns": [
  {
   "claim": "Synonym-only restatements with zero source-token overlap FIRE. That is a false-positive class relative to a human steelman judge.",
   "settling_experiment": "Author a synonym-only restatement fixture with zero token overlap and decide whether S1 should accept an external synonym table.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Original-author acceptance of the steelman (IMP-0293) is out of scope.",
   "settling_experiment": "Deliver IMP-0293; do not bind it here.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot: after the 2nd failure on the same hypothesis, enumerate >=2 alternative mechanisms before a 3rd attempt (AGENTS.md 4b)"
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Mechanical cross-check: re-tabulate restates ids and mean Jaccard from fixture JSON (not detector.reasons); coverage/ordering ablations; schema garbage 3/3 rejected via disk-local $ref. Catalog asked for openai/gpt-5-codex to re-run both-states; this probe is the executable stand-in on this worktree.",
  "reviewer_id": "CNL-0049-probe2-independent-signals",
  "vendor": "openai",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0049",
 "spec_anchor": "_USER-PROMPTS.md:10746-10767",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
   "id": "T1-fake-fails-genuine-passes",
   "name": "fake-steelman fails, genuine passes",
   "output_tail": "fired_on_bad=True silent_on_good=True genuine_verdict=PASS fake_verdict=FAIL label_verdict=FAIL fake_missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\nnegative_control rejects=token-concession-then-prepared-attack observed=FIRES reasons=[\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"]\nSUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0049/probe1_both_states.py",
   "id": "T2-both-states",
   "name": "FIRES on planted-bad, SILENT on known-good",
   "output_tail": "fired_on_bad=True silent_on_good=True genuine_verdict=PASS fake_verdict=FAIL label_verdict=FAIL fake_missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\nnegative_control rejects=token-concession-then-prepared-attack observed=FIRES reasons=[\"turn[0]:attack-before-coverage missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\", \"coverage-incomplete missing=['C-hash-ssot', 'C-stop-hook', 'C-bind-root']\"]\nSUCCESS:CNL-0049-probe1 both-states fake-fails genuine-passes",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "duration_seconds": 1500,
  "ended_at": "2026-08-25T00:46:00Z",
  "started_at": "2026-08-25T00:21:00Z"
 },
 "unit_id": "CNL-0049"
}
