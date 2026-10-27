{
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
   "bytes": 3293,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/detector.py",
   "role": "supporting",
   "sha256": "cc1fd85d58e00eac5bebbe14028c33dfcf9081d898a33f91c03fab84dcb5cab5"
  },
  {
   "bytes": 5251,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/fixtures.py",
   "role": "supporting",
   "sha256": "2c106b81a71dca5c04789603b81c60e2cf58e5dedd19ddce60fdfe7d2acf471f"
  },
  {
   "bytes": 3458,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/both_states.py",
   "role": "supporting",
   "sha256": "312965b83adc25a9ff6a9550450392772b85b6878ee74742b8ca8fa7da1a9e5d"
  },
  {
   "bytes": 3298,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/probe1_both_states.py",
   "role": "supporting",
   "sha256": "e16072d31dc61242f7fc77e7abb2433df2adcf3f533c5e082be9d3cd7d20365a"
  },
  {
   "bytes": 4644,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/probe2_independent_rerun.py",
   "role": "supporting",
   "sha256": "b584208b8734ba4f09d4535f1123e9a47e7c287e9abe1fe01d668c322b172e03"
  },
  {
   "bytes": 2024,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/fixtures/planted-masquerade.json",
   "role": "fixture",
   "sha256": "3073924622a7f6656d8a6012315580fb4f7d65e02bc8c8a0140eae544a5d6dc7"
  },
  {
   "bytes": 1980,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/fixtures/good-cap-exhausted.json",
   "role": "fixture",
   "sha256": "6d1f01210682615ed61209c347aeb35de5093448c56f928b21b8bd694a2d150b"
  },
  {
   "bytes": 1360,
   "eol": "LF",
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0096/fixtures/good-genuine-no-decision.json",
   "role": "fixture",
   "sha256": "3b9cbdcb7f9a28f8d5056d94471ab87d7af11934cb29381c349d416a5e85addd"
  }
 ],
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md",
   "consumer": "schema_local.iter_errors of catalog output_path",
   "executed": true,
   "exit_code": 0,
   "probe": {
    "command": "json.loads command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md",
    "exit_code": 0,
    "fingerprint": "d8d1b33bf5072683922d0129127ccc89c2647a1aca30687d2d5cfdc6e3fc86fd",
    "method": "file-read",
    "raw_output": "schema_errors=0",
    "role": "verifier"
   },
   "read_ok": true
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0096/detector.py:14",
   "claim": "Detector-control first: planted-masquerade (cap-hit labelled no-decision) FIREs; three planted fixtures FIRE; four clean fixtures are SILENT; false_positive_rate is the number 0.0 not an adjective.",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0096/probe1_both_states.py",
     "exit_code": 0,
     "fingerprint": "6ad40b50bb101067f754c4a756747ed62920c4e133fcc09ec50b2a1b65054fb4",
     "method": "test-run",
     "raw_output": "detector_control_fired=True planted_bad_fired=True known_good_silent=True false_positive_rate=0.0 pair_distinct=True",
     "role": "source"
    },
    {
     "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0096/probe2_independent_rerun.py",
     "exit_code": 0,
     "fingerprint": "e4fc4d9db8468d9522c57a408f42faf87ea00398a09482ba1eb357631e0a97ae",
     "method": "byte-compare",
     "raw_output": "independent_ok=True negative_control_fired=True codes=['masquerade-as-non-exhausted-kind', 'masquerade-as-spec-variant:no-decision', 'termination-cause-not-hard-cap'] rewrite kind=no-decision termination_cause=deliberative on good-cap-exhausted; detect.fired=True codes=['masquerade-as-non-exhausted-kind', 'masquerade-as-spec-variant:no-decision', 'termination-cause-not-hard-cap']",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0096/detector.py:58",
   "claim": "Cap-hit without a decision is distinguishable from genuine no-decision by the tuple (kind, termination_cause, cap_remaining): ['exhausted_without_decision', 'hard_cap', 0] vs ['no-decision', 'deliberative', 6] (distinct=True).",
   "confidence": "almost-certain",
   "probes": [
    {
     "command": "command-center/p2-wave/probes/CNL-0096/detector.py:58",
     "exit_code": 0,
     "fingerprint": "3a2dcd80dfdd1aae1bcdfb6e171834f0bc7326d923dc69bf01237275edf76d2b",
     "method": "file-read",
     "raw_output": "distinguisher returns tuple(kind, termination_cause, cap_remaining)",
     "role": "source"
    },
    {
     "command": "json.loads command-center/design/council/CNL-0096-endless-debate-cap-and-graceful-degradation.md",
     "exit_code": 0,
     "fingerprint": "d8d1b33bf5072683922d0129127ccc89c2647a1aca30687d2d5cfdc6e3fc86fd",
     "method": "file-read",
     "raw_output": "schema_errors=0",
     "role": "verifier"
    }
   ],
   "verdict": "CONFIRMED"
  }
 ],
 "extensions": {
  "answer": "On hard-cap without a decision the council emits exhausted_without_decision (termination_cause=hard_cap, cap_remaining=0) plus the preserved-work payload (transcript, last_positions, vote_snapshot, information_gain_by_round). That record is distinguishable from genuine no-decision because the distinguisher tuple (kind, termination_cause, cap_remaining) differs: ['exhausted_without_decision', 'hard_cap', 0] vs ['no-decision', 'deliberative', 6]. A consumer that only understands no-decision will not coerce the cap-hit record. Work is not lost because empty preserved-work fields fire the detector. SUCCESS:CNL-0096",
  "both_states": {
   "clean": {
    "good-cap-exhausted": {
     "codes": [],
     "fired": false
    },
    "good-decision-before-cap": {
     "codes": [],
     "fired": false
    },
    "good-decision-on-last-round": {
     "codes": [],
     "fired": false
    },
    "good-genuine-no-decision": {
     "codes": [],
     "fired": false
    }
   },
   "known_good_silent": true,
   "planted": {
    "planted-false-exhaustion": {
     "codes": [
      "false-exhaustion-claim"
     ],
     "fired": true
    },
    "planted-masquerade": {
     "codes": [
      "masquerade-as-non-exhausted-kind",
      "masquerade-as-spec-variant:no-decision",
      "termination-cause-not-hard-cap"
     ],
     "fired": true
    },
    "planted-work-lost": {
     "codes": [
      "preserved-work-lost:transcript,last_positions,vote_snapshot,information_gain_by_round"
     ],
     "fired": true
    }
   },
   "planted_bad_fired": true
  },
  "distinguisher_pair": {
   "cap_exhausted": [
    "exhausted_without_decision",
    "hard_cap",
    0
   ],
   "distinct": true,
   "genuine_no_decision": [
    "no-decision",
    "deliberative",
    6
   ],
   "mechanism": "tuple(kind, termination_cause, cap_remaining) \u2014 not detect().fired"
  },
  "false_positive_rate": {
   "clean_count": 4,
   "fired_on_clean": 0,
   "formula": "fired_on_clean / clean_count",
   "rate": 0.0
  },
  "graceful_degradation": {
   "cap_remaining": 0,
   "emitted_kind": "exhausted_without_decision",
   "not_the_same_as": "no-decision",
   "preserved_work": [
    "transcript",
    "last_positions",
    "vote_snapshot",
    "information_gain_by_round"
   ],
   "termination_cause": "hard_cap",
   "why_not_no_decision": "no-decision is a deliberative choice with remaining budget; cap-hit is an environmental stop. Collapsing them loses the cause and lets downstream consumers treat exhaustion as epistemic refusal."
  },
  "question": "When a council hits its hard cap without a decision, what is emitted so the work is not lost - and is that artifact distinguishable from a real no-decision outcome?"
 },
 "manifest_registration": {
  "manifest_path": "command-center/p2-wave/probes/CNL-0096/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "min_bytes_threshold": 2048,
 "negative_controls": [
  {
   "bad_state_output": "rewrite kind=no-decision termination_cause=deliberative on good-cap-exhausted; detect.fired=True codes=['masquerade-as-non-exhausted-kind', 'masquerade-as-spec-variant:no-decision', 'termination-cause-not-hard-cap']",
   "description": "Rewrite good-cap-exhausted kind to no-decision with termination_cause=deliberative. The detector MUST FIRE. Unmutated good-cap-exhausted MUST stay SILENT.",
   "fired_on_bad_state": true,
   "good_state_output": "good-cap-exhausted detect.fired=False codes=[]",
   "id": "NC-REWRITE-EXHAUSTED-AS-NO-DECISION",
   "kind": "mutation",
   "silent_on_good_state": true
  },
  {
   "bad_state_output": "planted-masquerade detect.fired=True codes=['masquerade-as-non-exhausted-kind', 'masquerade-as-spec-variant:no-decision', 'termination-cause-not-hard-cap']",
   "description": "planted-masquerade is the known-present detector-control. The detector MUST FIRE before any absence is claimed. good-genuine-no-decision MUST stay SILENT.",
   "fired_on_bad_state": true,
   "good_state_output": "good-genuine-no-decision detect.fired=False codes=[]",
   "id": "NC-PLANTED-MASQUERADE",
   "kind": "known-broken-fixture",
   "silent_on_good_state": true
  }
 ],
 "produced_by": {
  "execution_substrate": "local-parallel",
  "model": "opus",
  "role": "council-anti-failure-detector-designer",
  "vendor": "anthropic"
 },
 "profile": "council-detector-spec",
 "report": {
  "answer": "On hard-cap without a decision the council emits exhausted_without_decision (termination_cause=hard_cap, cap_remaining=0) plus the preserved-work payload (transcript, last_positions, vote_snapshot, information_gain_by_round). That record is distinguishable from genuine no-decision because the distinguisher tuple (kind, termination_cause, cap_remaining) differs: ['exhausted_without_decision', 'hard_cap', 0] vs ['no-decision', 'deliberative', 6]. A consumer that only understands no-decision will not coerce the cap-hit record. Work is not lost because empty preserved-work fields fire the detector. SUCCESS:CNL-0096",
  "both_states": {
   "clean": {
    "good-cap-exhausted": {
     "codes": [],
     "fired": false
    },
    "good-decision-before-cap": {
     "codes": [],
     "fired": false
    },
    "good-decision-on-last-round": {
     "codes": [],
     "fired": false
    },
    "good-genuine-no-decision": {
     "codes": [],
     "fired": false
    }
   },
   "known_good_silent": true,
   "planted": {
    "planted-false-exhaustion": {
     "codes": [
      "false-exhaustion-claim"
     ],
     "fired": true
    },
    "planted-masquerade": {
     "codes": [
      "masquerade-as-non-exhausted-kind",
      "masquerade-as-spec-variant:no-decision",
      "termination-cause-not-hard-cap"
     ],
     "fired": true
    },
    "planted-work-lost": {
     "codes": [
      "preserved-work-lost:transcript,last_positions,vote_snapshot,information_gain_by_round"
     ],
     "fired": true
    }
   },
   "planted_bad_fired": true
  },
  "control_ids": [
   "planted-masquerade",
   "planted-work-lost",
   "planted-false-exhaustion",
   "good-genuine-no-decision",
   "good-cap-exhausted",
   "good-decision-before-cap",
   "good-decision-on-last-round"
  ],
  "dependencies_on_this_tree": {
   "CNL-0072": "absent \u2014 17-value $defs.outcome mapping not inherited; distinguisher binds to the six named spec variants plus exhausted_without_decision",
   "CNL-0084": "absent \u2014 deadlock (stuck with remaining cap) is out of scope; this unit is budget exhaustion"
  },
  "detector": {
   "fires_when": "cap-hit without a decision is labelled as no-decision or another spec variant, termination_cause is not hard_cap, preserved work is missing, or exhaustion is claimed with remaining budget",
   "id": "CNL-0096-cap-exhaustion",
   "implementation": "command-center/p2-wave/probes/CNL-0096/detector.py",
   "signals": {
    "A": "detect().fired boolean plus codes",
    "B": "distinguisher tuple (kind, termination_cause, cap_remaining) compared across the genuine/exhausted pair without using detect().fired"
   },
   "silent_when": "genuine no-decision with remaining cap, well-formed exhausted_without_decision with preserved work, or a decision (including last-round agreement)"
  },
  "detector_control": {
   "codes": [
    "masquerade-as-non-exhausted-kind",
    "masquerade-as-spec-variant:no-decision",
    "termination-cause-not-hard-cap"
   ],
   "fired": true,
   "fired_before_absence_claimed": true,
   "known_present_id": "planted-masquerade"
  },
  "distinguisher_pair": {
   "cap_exhausted": [
    "exhausted_without_decision",
    "hard_cap",
    0
   ],
   "distinct": true,
   "genuine_no_decision": [
    "no-decision",
    "deliberative",
    6
   ],
   "mechanism": "tuple(kind, termination_cause, cap_remaining) \u2014 not detect().fired"
  },
  "false_positive_rate": {
   "clean_count": 4,
   "fired_on_clean": 0,
   "formula": "fired_on_clean / clean_count",
   "rate": 0.0
  },
  "fixture_anchors": {
   "good_cap_exhausted": "command-center/p2-wave/probes/CNL-0096/fixtures/good-cap-exhausted.json:31",
   "good_genuine_no_decision": "command-center/p2-wave/probes/CNL-0096/fixtures/good-genuine-no-decision.json:28",
   "planted_masquerade": "command-center/p2-wave/probes/CNL-0096/fixtures/planted-masquerade.json:31"
  },
  "graceful_degradation": {
   "cap_remaining": 0,
   "emitted_kind": "exhausted_without_decision",
   "not_the_same_as": "no-decision",
   "preserved_work": [
    "transcript",
    "last_positions",
    "vote_snapshot",
    "information_gain_by_round"
   ],
   "termination_cause": "hard_cap",
   "why_not_no_decision": "no-decision is a deliberative choice with remaining budget; cap-hit is an environmental stop. Collapsing them loses the cause and lets downstream consumers treat exhaustion as epistemic refusal."
  },
  "kind": "council-detector-spec",
  "negative_control": {
   "codes": [
    "masquerade-as-non-exhausted-kind",
    "masquerade-as-spec-variant:no-decision",
    "termination-cause-not-hard-cap"
   ],
   "fired": true,
   "id": "NC-REWRITE-EXHAUSTED-AS-NO-DECISION",
   "rejects": "good-cap-exhausted with kind rewritten to no-decision",
   "verbatim": "rewrite kind=no-decision termination_cause=deliberative on good-cap-exhausted; detect.fired=True codes=['masquerade-as-non-exhausted-kind', 'masquerade-as-spec-variant:no-decision', 'termination-cause-not-hard-cap']"
  },
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0096/detector.py:14",
    "measured": 0.0,
    "method": "fired_on_clean / clean_count over four known-good fixtures",
    "name": "false_positive_rate"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0096/detector.py:58",
    "measured": true,
    "method": "tuple(kind, termination_cause, cap_remaining) without detect().fired",
    "name": "distinguisher_pair_distinct"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0096/fixtures/planted-masquerade.json:31",
    "measured": true,
    "method": "detect() on planted-masquerade before any absence claim",
    "name": "detector_control_fired"
   }
  ],
  "pathology": {
   "absent_when": "cap-hit emits exhausted_without_decision with termination_cause=hard_cap and non-empty preserved work, or the run never hit the cap (including a decision on the last allowed round)",
   "id": "cap-hit-masquerade-or-lost-work",
   "name": "Hard-cap exhaustion labelled as deliberative no-decision, or cap-hit with dropped work",
   "present_when": "rounds_consumed >= hard_cap and outcome is not a decision, and either kind is a spec non-decision variant or preserved-work fields are empty; or exhausted_without_decision is claimed while cap budget remains"
  },
  "question": "When a council hits its hard cap without a decision, what is emitted so the work is not lost - and is that artifact distinguishable from a real no-decision outcome?",
  "spec_variants_distinguished": [
   "decision",
   "conditional_decision",
   "no-decision",
   "irreducible_disagreement",
   "dissent-with-minority-report",
   "proof_of_impossibility"
  ],
  "title": "Endless debate cap and graceful degradation"
 },
 "residual_unknowns": [
  {
   "claim": "The 17-value $defs.outcome enum from CNL-0072 is not on this tree; exhausted_without_decision is specified as a seventh kind relative to the six named spec variants, not mapped onto that enum.",
   "settling_experiment": "When CNL-0072's mapping artifact is present, join exhausted_without_decision onto $defs.outcome and re-run the distinguisher pair.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "CNL-0084 deadlock (frozen ledger plus wait-for cycle with remaining cap) is out of scope for this hard-cap unit.",
   "settling_experiment": "Feed a CNL-0084 planted-deadlock fixture with cap remaining into detect() and require SILENT for cap-exhaustion codes.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot, PLUS a mandatory detector-control retry: if the both-states control does not fire on the planted-bad fixture, the attempt does not count as a failure of the mechanism - fix the fixture first, once. Max 3 mechanism attempts (AGENTS.md 4b)."
 },
 "reviewer": {
  "fresh_context": true,
  "independent": true,
  "notes": "Probe2 re-runs the both-states matrix, applies the kind-rewrite negative control, rejects adjective FPR, and validates the receipt against council-detector-spec via disk-mapped RefResolver (jsonschema 4.10, no network). Agreement with emit prose is not required.",
  "reviewer_id": "CNL-0096-probe2-independent-rerun",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0096",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:39102",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0096/probe1_both_states.py",
   "id": "T1-both-states-detector-control",
   "name": "Detector-control, planted FIRE, clean SILENT, numeric FPR",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0096/probe2_independent_rerun.py",
   "id": "T2-independent-rerun-negative-control",
   "name": "Independent matrix rerun, kind-rewrite negative control, schema",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "duration_seconds": 0,
  "ended_at": "2026-08-25T00:59:52Z",
  "started_at": "2026-08-25T00:59:52Z"
 },
 "unit_id": "CNL-0096"
}
