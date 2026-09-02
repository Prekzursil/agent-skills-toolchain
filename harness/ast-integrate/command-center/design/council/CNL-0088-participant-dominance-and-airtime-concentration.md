{
  "answer": "On four-seat scripted fixtures the detector first fires at token_share>=0.5 or surviving_claim_share>=0.5 (tau=0.5). A 0.40-token prolific seat with even claims stays silent. False-positive rate on 12 jittered balanced councils is 0/12 = 0.0. Throttling the token-leader to 1/n improved quality when that seat was wrong (score 0->1) and degraded quality when that seat was the sole correct expert (score 1->0). Throttling is therefore not quality-monotonic: the detector must FLAG concentration and must not auto-mute. Surviving-claim share is not interchangeable with turn share. SUCCESS:CNL-0088",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0088-participant-dominance-and-airtime-concentration.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-detector-spec.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0088/detector.py",
      "role": "detector"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0088/fixtures.py",
      "role": "fixtures"
    }
  ],
  "both_states": {
    "known_good": {
      "fired": false,
      "fixture_id": "known-good-balanced",
      "silent": true,
      "verbatim": "{\"dominant_seat\":null,\"fired\":false,\"fixture_id\":\"known-good-balanced\",\"ignored_synthesizer_self_attestation\":true,\"max_surviving_claim_share\":0.25,\"max_token_share\":0.25,\"reasons\":[],\"silent\":true,\"synthesizer_claimed_balanced\":true,\"tau\":0.5}"
    },
    "planted_bad": {
      "fired": true,
      "fixture_id": "planted-bad-airtime",
      "verbatim": "{\"dominant_seat\":\"loud\",\"fired\":true,\"fixture_id\":\"planted-bad-airtime\",\"ignored_synthesizer_self_attestation\":true,\"max_surviving_claim_share\":0.8,\"max_token_share\":0.7,\"reasons\":[{\"metric\":\"token_share\",\"rule\":\"max(token_share, surviving_claim_share) >= tau\",\"seat\":\"loud\",\"share\":0.7},{\"metric\":\"surviving_claim_share\",\"rule\":\"max(token_share, surviving_claim_share) >= tau\",\"seat\":\"loud\",\"share\":0.8}],\"silent\":false,\"synthesizer_claimed_balanced\":true,\"tau\":0.5}"
    }
  },
  "concentration_sweep": {
    "first_fire_surviving_claim_share": 0.5,
    "first_fire_token_share": 0.5,
    "surviving_claim": [
      {
        "fired": false,
        "fixture_id": "sweep-claims-loud-2-of-8",
        "k_loud": 2,
        "max_surviving_claim_share": 0.25,
        "max_token_share": 0.25,
        "n_claims": 8
      },
      {
        "fired": false,
        "fixture_id": "sweep-claims-loud-3-of-8",
        "k_loud": 3,
        "max_surviving_claim_share": 0.375,
        "max_token_share": 0.25,
        "n_claims": 8
      },
      {
        "fired": true,
        "fixture_id": "sweep-claims-loud-4-of-8",
        "k_loud": 4,
        "max_surviving_claim_share": 0.5,
        "max_token_share": 0.25,
        "n_claims": 8
      },
      {
        "fired": true,
        "fixture_id": "sweep-claims-loud-5-of-8",
        "k_loud": 5,
        "max_surviving_claim_share": 0.625,
        "max_token_share": 0.25,
        "n_claims": 8
      },
      {
        "fired": true,
        "fixture_id": "sweep-claims-loud-6-of-8",
        "k_loud": 6,
        "max_surviving_claim_share": 0.75,
        "max_token_share": 0.25,
        "n_claims": 8
      }
    ],
    "token": [
      {
        "fired": false,
        "fixture_id": "sweep-token-5-of-20",
        "max_token_share": 0.25,
        "target_share": 0.25
      },
      {
        "fired": false,
        "fixture_id": "sweep-token-6-of-20",
        "max_token_share": 0.3,
        "target_share": 0.3
      },
      {
        "fired": false,
        "fixture_id": "sweep-token-7-of-20",
        "max_token_share": 0.35,
        "target_share": 0.35
      },
      {
        "fired": false,
        "fixture_id": "sweep-token-8-of-20",
        "max_token_share": 0.4,
        "target_share": 0.4
      },
      {
        "fired": false,
        "fixture_id": "sweep-token-9-of-20",
        "max_token_share": 0.45,
        "target_share": 0.45
      },
      {
        "fired": true,
        "fixture_id": "sweep-token-10-of-20",
        "max_token_share": 0.5,
        "target_share": 0.5
      },
      {
        "fired": true,
        "fixture_id": "sweep-token-11-of-20",
        "max_token_share": 0.55,
        "target_share": 0.55
      },
      {
        "fired": true,
        "fixture_id": "sweep-token-12-of-20",
        "max_token_share": 0.6,
        "target_share": 0.6
      },
      {
        "fired": true,
        "fixture_id": "sweep-token-14-of-20",
        "max_token_share": 0.7,
        "target_share": 0.7
      },
      {
        "fired": true,
        "fixture_id": "sweep-token-16-of-20",
        "max_token_share": 0.8,
        "target_share": 0.8
      }
    ]
  },
  "detector": {
    "fire_rule": "max(token_share, surviving_claim_share) >= tau",
    "id": "participant-dominance-airtime-concentration",
    "ignores_synthesizer_self_attestation": true,
    "mechanism": "Compute per-seat token_share and surviving_claim_share from the transcript. Claim ownership is first utterance, not synthesizer attribution. FIRE iff max(token_share, surviving_claim_share) >= 0.5. Turn share and evidence-cite share are diagnostics only. Synthesis.self_attestation is ignored.",
    "signals": [
      "token_share from transcript tokens",
      "surviving_claim_share from first-utterance ownership of accepted claims",
      "turn_share diagnostic (not a fire channel)",
      "evidence_cite_share diagnostic (not a fire channel)"
    ],
    "tau": 0.5
  },
  "detector_control": {
    "fixture_id": "known-present-airtime-control",
    "known_present_fired": true,
    "known_present_run_before_absence": true,
    "verbatim": "{\"dominant_seat\":\"loud\",\"fired\":true,\"fixture_id\":\"known-present-airtime-control\",\"ignored_synthesizer_self_attestation\":true,\"max_surviving_claim_share\":0.8,\"max_token_share\":0.7,\"reasons\":[{\"metric\":\"token_share\",\"rule\":\"max(token_share, surviving_claim_share) >= tau\",\"seat\":\"loud\",\"share\":0.7},{\"metric\":\"surviving_claim_share\",\"rule\":\"max(token_share, surviving_claim_share) >= tau\",\"seat\":\"loud\",\"share\":0.8}],\"silent\":false,\"synthesizer_claimed_balanced\":true,\"tau\":0.5}"
  },
  "evidence": [
    {
      "claim": "Fire rule is majority share on tokens OR surviving claims.",
      "line": 19,
      "path": "command-center/p2-wave/probes/CNL-0088/detector.py",
      "snippet": "FIRE_RULE = \"max(token_share, surviving_claim_share) >= tau\""
    },
    {
      "claim": "Synthesizer self-attestation is ignored when deciding fire.",
      "line": 197,
      "path": "command-center/p2-wave/probes/CNL-0088/detector.py",
      "snippet": "\"ignored_synthesizer_self_attestation\": True"
    },
    {
      "claim": "Planted-bad airtime fixture exists for both-states.",
      "line": 65,
      "path": "command-center/p2-wave/probes/CNL-0088/fixtures.py",
      "snippet": "def planted_bad_airtime() -> dict:"
    },
    {
      "claim": "Outcome-dominance fixture concentrates claims without token majority.",
      "line": 117,
      "path": "command-center/p2-wave/probes/CNL-0088/fixtures.py",
      "snippet": "def planted_bad_claims_only() -> dict:"
    }
  ],
  "false_positive_rate": {
    "denominator": 12,
    "fixture_ids": [
      "fp-balanced-5-5-5-5",
      "fp-balanced-6-5-5-4",
      "fp-balanced-6-6-4-4",
      "fp-balanced-7-5-4-4",
      "fp-balanced-6-6-5-3",
      "fp-balanced-7-6-4-3",
      "fp-balanced-7-5-5-3",
      "fp-balanced-6-5-6-3",
      "fp-balanced-8-4-4-4",
      "fp-balanced-7-7-3-3",
      "fp-balanced-6-6-6-2",
      "fp-balanced-8-5-4-3"
    ],
    "numerator": 0,
    "value": 0.0
  },
  "kind": "council-detector-spec",
  "negative_control": {
    "state_rejected": "balanced-transcript-with-synthesizer-attesting-dominance",
    "verbatim": "{\"dominant_seat\":null,\"fired\":false,\"fixture_id\":\"attestation-cries-wolf\",\"ignored_synthesizer_self_attestation\":true,\"max_surviving_claim_share\":0.25,\"max_token_share\":0.25,\"reasons\":[],\"silent\":true,\"synthesizer_claimed_balanced\":false,\"tau\":0.5}"
  },
  "pathology": "One participant captures airtime (token share) or accepted-idea share (surviving claims first-uttered by that seat) at or above majority (tau=0.50) on a four-seat council.",
  "question": "At what concentration of airtime or accepted-idea share does one participant dominate, and does throttling the dominant seat improve or degrade decision quality on fixtures?",
  "residual_unknowns": [
    "CNL-0047 speaking-order engine is not delivered; throttle here is a fixture-level cap, not the production scheduler.",
    "Cross-vendor LLM review was not executed; probe 2 is a mechanical independent re-run.",
    "Live multi-model councils were not measured; numbers are from scripted four-seat fixtures."
  ],
  "reviewer": {
    "executed_both_states_control": true,
    "independent": true,
    "note": "Probe 2 re-runs both-states and the throttle experiment in a separate process and recomputes shares from raw turns.",
    "reviewer_id": "CNL-0088-probe2-independent-both-states",
    "verdict": "PASS"
  },
  "schema_path": "command-center/schema/council-detector-spec.schema.json",
  "sentinel": "SUCCESS:CNL-0088",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0088/probe1_both_states.py",
      "id": "probe1-both-states",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0088/probe2_throttle_quality.py",
      "id": "probe2-throttle-quality",
      "result": "PASS"
    }
  ],
  "throttle_experiment": {
    "cap": "1/n token share of remaining transcript",
    "expert_dominant": {
      "after": {
        "correct": false,
        "gold": "CORRECT",
        "got": "WRONG",
        "score": 0
      },
      "before": {
        "correct": true,
        "gold": "CORRECT",
        "got": "CORRECT",
        "score": 1
      },
      "degraded": true,
      "throttle": {
        "applied": true,
        "cap_share": 0.25,
        "capped_seat": "loud",
        "pre_token_share": 0.7,
        "turns_dropped": 6
      }
    },
    "quality_monotonic": false,
    "recommendation": "FLAG dominance; do not auto-throttle. Throttle helps when the dominant seat is wrong and hurts when that seat is the sole expert.",
    "wrong_dominant": {
      "after": {
        "correct": true,
        "gold": "CORRECT",
        "got": "CORRECT",
        "score": 1
      },
      "before": {
        "correct": false,
        "gold": "CORRECT",
        "got": "WRONG",
        "score": 0
      },
      "improved": true
    }
  },
  "unit_id": "CNL-0088"
}
