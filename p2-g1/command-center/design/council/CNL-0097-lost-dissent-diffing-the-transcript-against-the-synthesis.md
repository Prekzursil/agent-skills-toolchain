{
  "answer": "Lost dissent is the set-difference of transcript-harvested dissent records minus dissent whose content-token set is covered by the synthesis body. Harvest reads only transcript turns, against-votes and minority records. Coverage reads only the synthesis body. The synthesizer's self-attestation is ignored, so a synthesis that declares all_dissent_preserved while dropping the claim still fires. On planted-bad the detector fires and lists ['d-rollback-required']. On known-good it is silent. False-positive rate on 4 clean fixtures is 0.0 (0/4).",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0097-lost-dissent-diffing-the-transcript-against-the-synthesis.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-detector-spec.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0097/detector.py",
      "role": "detector"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
      "role": "named-probe"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
      "role": "named-probe"
    }
  ],
  "both_states": {
    "known_good": {
      "fired": false,
      "fixture_id": "known-good-preserved-dissent",
      "preserved_ids": [
        "d-rollback-required"
      ],
      "silent": true,
      "verbatim": "known-good id=known-good-preserved-dissent fired=False silent=True preserved_ids=['d-rollback-required']"
    },
    "planted_bad": {
      "fired": true,
      "fixture_id": "planted-bad-dropped-dissent",
      "lost_ids": [
        "d-rollback-required"
      ],
      "verbatim": "planted-bad id=planted-bad-dropped-dissent fired=True lost_ids=['d-rollback-required'] lost_count=1 self_attestation_claimed_healthy=True ignored=True"
    }
  },
  "detector": {
    "coverage_threshold": 0.8,
    "does_not_trust": "synthesizer self-attestation or generic 'dissent noted' prose",
    "id": "cnl-0097-transcript-synthesis-dissent-diff",
    "ignores_synthesizer_self_attestation": true,
    "mechanism": "Harvest dissent solely from the transcript (kind/stance-tagged turns, against votes with reasons, minority_reports). Tokenize each dissent body after stopword removal. Tokenize the synthesis body, including minority_reports attached to the synthesis. A dissent is preserved only when content-token coverage >= 0.8 (or exact normalized substring when the body has fewer than 5 content tokens). Otherwise it is lost. Self-attestation is not an input. An id listed without the body does not count as preservation.",
    "min_content_tokens": 5,
    "signals": [
      "planted-bad run (known-present lost dissent must FIRE)",
      "known-good run (preserved dissent must be SILENT)"
    ]
  },
  "detector_control": {
    "known_present_fired": true,
    "known_present_run_before_absence": true,
    "verbatim": "detector-control: planted-bad was evaluated first in this process and FIRED (lost_ids=['d-rollback-required']) before known-good silence was reported."
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:39155",
      "claim": "Unit question requires a computed transcript-vs-synthesis diff, not synthesizer judgement.",
      "line": 39155,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "Which dissent present in the transcript failed to appear in the synthesis"
    },
    {
      "anchor": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:327",
      "claim": "Seeded failure class FC-11340 is dropped dissent, the pathology this detector names.",
      "line": 327,
      "path": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py",
      "snippet": "dissent/minority report is dropped"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0097/detector.py:279",
      "claim": "Detector implementation ignores synthesizer self-attestation by construction.",
      "line": 279,
      "path": "command-center/p2-wave/probes/CNL-0097/detector.py",
      "snippet": "Never consults synthesizer self-attestation"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0097/scenario.py:20",
      "claim": "Planted dissent body is a fixed transcript string used as the diff operand.",
      "line": 20,
      "path": "command-center/p2-wave/probes/CNL-0097/scenario.py",
      "snippet": "Shipping without a tested rollback plan is an irreversible production"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0097/detector.py:305",
      "claim": "Lost dissent is a set-difference on content tokens, not a boolean the synthesizer emits.",
      "line": 305,
      "path": "command-center/p2-wave/probes/CNL-0097/detector.py",
      "snippet": "transcript dissent content-token set is not covered by the"
    }
  ],
  "false_positive_rate": {
    "denominator": 4,
    "fixture_ids": [
      "known-good-preserved-dissent",
      "clean-two-dissents-preserved",
      "clean-dedicated-minority-section",
      "clean-faithful-restatement"
    ],
    "numerator": 0,
    "value": 0.0
  },
  "negative_control": {
    "state_rejected": "transcript dissent whose content tokens are absent from synthesis, including id-only and generic-mention evasions",
    "verbatim": "negative control (state the check is meant to reject): a transcript that contains dissent d-rollback-required whose content tokens are absent from the synthesis. Result: fired=True lost_ids=['d-rollback-required']. Synthesizer self-attestation all_dissent_preserved=true did not suppress the fire. id-only void fixture fired=True; generic-mention fired=True."
  },
  "pathology": "lost-dissent",
  "question": "Which dissent present in the transcript failed to appear in the synthesis \u2014 computed as a diff, not judged by the synthesizer who dropped it?",
  "report": {
    "control_ids": [
      "planted-bad-dropped-dissent",
      "known-good-preserved-dissent",
      "planted-void-id-only",
      "planted-generic-mention"
    ],
    "kind": "council-detector-spec",
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
        "measured": true,
        "method": "detector.detect planted-bad-dropped-dissent",
        "name": "planted_bad_fired"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
        "measured": true,
        "method": "detector.detect known-good-preserved-dissent",
        "name": "known_good_silent"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0097/scenario.py",
        "measured": 0.0,
        "method": "clean-fixture false-positive rate",
        "name": "false_positive_rate"
      }
    ]
  },
  "reviewer": {
    "executed_both_states_control": true,
    "independent": true,
    "reviewer_id": "CNL-0097-probe2-independent-both-states",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "seeded_failure_class": {
    "anchor": "command-center/p2-wave/probes/ARC-0005/seeded_classes.py:327",
    "id": "FC-11340",
    "name": "dissent/minority report is dropped"
  },
  "sentinel": "SUCCESS:CNL-0097",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0097/probe1_planted_fire.py",
      "id": "T1-planted-fire-and-detector-control",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0097/probe2_both_states.py",
      "id": "T2-both-states-and-false-positive-rate",
      "result": "PASS"
    }
  ],
  "ts": "2026-08-25T00:55:26Z",
  "unit_id": "CNL-0097"
}
