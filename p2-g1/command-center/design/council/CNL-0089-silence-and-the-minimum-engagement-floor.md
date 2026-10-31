{
  "schema_version": 1,
  "unit_id": "CNL-0089",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0089",
  "spec_anchor": "_USER-PROMPTS.md:10746-10767",
  "min_bytes_threshold": 512,
  "profile": "council-detector-spec",
  "artifacts": [
    {
      "path": "command-center/p2-wave/probes/CNL-0089/detector.py",
      "bytes": 7736,
      "sha256": "e359475bc01e977b49de3d1b461e3d928ed4e57eca3c81e03e9831ae9e0c6286",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0089/fixtures/planted-filler-consent.json",
      "bytes": 1963,
      "sha256": "4235c8f0364d5a6d42901487a79e81e43214d517d4cd15d9d56387e600c7ae39",
      "exists": true,
      "eol": "LF",
      "role": "fixture"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0089/fixtures/clean-yield-only-nothing-to-add.json",
      "bytes": 1902,
      "sha256": "b5c8253241508bce423912439c566d2d6aba5efb87c026e8eb20edb0f4dfccf3",
      "exists": true,
      "eol": "LF",
      "role": "fixture"
    },
    {
      "path": "command-center/schema/council-detector-spec.schema.json",
      "bytes": 1128,
      "sha256": "9aaa3e601e89634e67b7bb50afe4b7b326f13a23426b6a4cbbceaec2942a8599",
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    }
  ],
  "evidence": [
    {
      "claim": "Planted filler-consent (three empty ACKs counted as aye) FIREs on filler-masquerade and consent-by-silence for seat D.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0089/detector.py:163",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0089/probe1_both_states.py",
          "raw_output": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false}",
          "fingerprint": "cnl0089-src-probe1-planted",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "static-analysis",
          "command": "command-center/p2-wave/probes/CNL-0089/detector.py:163",
          "raw_output": "filler>=3 and speech==0 appends filler-masquerade",
          "fingerprint": "cnl0089-ver-filler-line",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "A structured nothing-to-add YIELD is SILENT; false-positive rate on 4 clean fixtures is 0.0.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0089/detector.py:68",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "python3 -c import-and-battery command-center/p2-wave/probes/CNL-0089/detector.py",
          "raw_output": "{\"clean_all_silent\": true, \"clean_count\": 4, \"false_positive_rate\": 0.0}",
          "fingerprint": "cnl0089-src-battery-fp",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0089/fixtures/clean-yield-only-nothing-to-add.json",
          "raw_output": "{\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-yield-only-nothing-to-add\", \"reasons\": {}, \"silent\": true}",
          "fingerprint": "cnl0089-ver-clean-yield-read",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0089/probe1_both_states.py",
      "result": "PASS"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0089/probe2_negative_fp.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-planted-filler-consent",
      "kind": "known-broken-fixture",
      "description": "Three ACK bodies (+1/agreed/ok) with D in agreeing must FIRE; a structured already-stated-by-peer yield must be SILENT.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false}",
      "good_state_output": "{\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-yield-only-nothing-to-add\", \"reasons\": {}, \"silent\": true}"
    },
    {
      "id": "NC-clean-all-engaged",
      "kind": "known-broken-fixture",
      "description": "Negative control: the check must stay silent on an engaged council (the state it is meant to reject firing on).",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false}",
      "good_state_output": "{\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-all-engaged\", \"silent\": true}"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0089-probe2-negative-fp-schema",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": true,
    "vendor": "openai",
    "notes": "Probe 2 re-runs the planted/clean battery, demands a numeric false-positive rate, schema-validates this artifact offline, and records the negative control verbatim. Re-reading this file is not the review."
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0089/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0089"
  },
  "downstream_consumers": [
    {
      "consumer": "command-center/p2-wave/probes/CNL-0089/probe1_both_states.py",
      "artifact_path": "command-center/p2-wave/probes/CNL-0089/detector.py",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "command",
        "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0089/probe1_both_states.py",
        "raw_output": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false} | {\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-yield-only-nothing-to-add\", \"reasons\": {}, \"silent\": true}",
        "fingerprint": "cnl0089-consumer-probe1",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-25T00:58:13Z",
    "ended_at": "2026-08-25T00:58:13Z",
    "duration_seconds": 0
  },
  "retry": {
    "count": 1,
    "policy": "two strikes then pivot, PLUS a mandatory detector-control retry: if the both-states control does not fire on the planted-bad fixture, the attempt does not count as a failure of the mechanism - fix the fixture first, once. Max 3 mechanism attempts.",
    "attempts": [
      {
        "attempt": 1,
        "error_fingerprint": "jsonschema-RefResolutionError-ast-integrate.invalid",
        "outcome": "FAILED"
      },
      {
        "attempt": 2,
        "error_fingerprint": "offline-resolver-receipt-core",
        "outcome": "SUCCESS"
      }
    ],
    "pivot_alternatives": [
      "offline RefResolver store over platform/schema files",
      "reshape catalog artifact to receipt_core + report.kind"
    ]
  },
  "residual_unknowns": [
    {
      "claim": "max_inactivity=2 is the fixture default, not a measured production SLA",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Measure live council inactivity windows once CNL-0047's speaking-order engine is on this tree and record the trip."
    },
    {
      "claim": "open-ended natural-language filler outside the closed ACK lexicon is classified FILLER only when it lacks structured fields; a future IMP unit owns a trained filler model",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Hand a labeled filler corpus to an IMP unit; this detector keeps the closed ACK lexicon until then."
    }
  ],
  "produced_by": {
    "vendor": "anthropic",
    "model": "opus",
    "role": "council-anti-failure-detector-designer",
    "execution_substrate": "local-parallel"
  },
  "report": {
    "kind": "council-detector-spec",
    "observations": [
      {
        "name": "false_positive_rate",
        "measured": 0.0,
        "method": "detector.battery over four clean fixtures",
        "anchor": "command-center/p2-wave/probes/CNL-0089/detector.py:232"
      },
      {
        "name": "planted_filler_consent_fired",
        "measured": true,
        "method": "scan planted-filler-consent before any absence claim",
        "anchor": "command-center/p2-wave/probes/CNL-0089/detector.py:163"
      },
      {
        "name": "clean_structured_yield_silent",
        "measured": true,
        "method": "scan clean-yield-only-nothing-to-add",
        "anchor": "command-center/p2-wave/probes/CNL-0089/detector.py:68"
      }
    ],
    "control_ids": [
      "NC-planted-filler-consent",
      "NC-clean-all-engaged"
    ],
    "title": "Silence and the minimum-engagement floor",
    "question": "What is the difference between a participant with nothing to add and one that has disengaged, and what does the runtime do about each?",
    "pathology": "Consent-by-silence and filler-masquerade: a seat that never produces a substantive speech-act or a structured yield is folded into the agreeing set, or a seat that contributes once then ghosts without yielding is treated as still present.",
    "path_note": "Catalog output_path ends in .md; G-1 parses this file with json.loads. This document is a council-detector-spec receipt.",
    "distinction": {
      "nothing_to_add": "A structured YIELD/PASS with a closed reason_code (no-new-information | already-stated-by-peer | outside-competence | awaiting-evidence) and a referent_id pointing at an existing claim. It is an explicit speech-act. It credits the engagement floor. It is not a vote and must not enter the agreeing set.",
      "disengaged": "Zero structured speech-acts (including three empty acknowledgements), or a contribution followed by max_inactivity silent rounds without a structured yield, or a seat listed in consensus.agreeing without an explicit AYE/NAY/ABSTAIN vote.",
      "operational_test": "classify() returns STRUCTURED_YIELD only when reason_code is in the closed set AND referent_id is present; otherwise a YIELD token is FILLER. Filler and silence never credit the floor. Three ACK turns with empty bodies fail the floor (IMP-0299)."
    },
    "detector": {
      "id": "min-engagement-floor",
      "implementation": "command-center/p2-wave/probes/CNL-0089/detector.py",
      "fires_when": [
        "speech_acts < min_speech_acts (default 1)",
        "filler_count >= 3 and speech_acts == 0 (filler-masquerade)",
        "seat in consensus.agreeing without an explicit vote (consent-by-silence)",
        "after at least one speech-act, inactivity_streak >= max_inactivity without a structured yield"
      ],
      "silent_when": [
        "every seat has >=1 SUBSTANTIVE or STRUCTURED_YIELD speech-act",
        "no agreeing seat lacks an explicit vote",
        "no post-contribution ghosting past max_inactivity"
      ]
    },
    "runtime_actions": {
      "on_nothing_to_add": "Accept the structured yield, credit the speech floor, skip remaining speaking quota for that seat, do not treat the yield as a vote, do not escalate.",
      "on_disengaged": "FIRE. Mark the seat ABSENT. Exclude it from the consenting set. Keep it in the roster so quorum/denominator cannot shrink. Escalate or replace the seat. Never count silence as aye.",
      "consent_rule": "Only an explicit VOTE with AYE/NAY/ABSTAIN and a rationale of at least four tokens may affect the agreeing set. Yield is not consent. Silence is not consent. ACK is not consent.",
      "budget_dial": "Minimum-engagement exhaustion HARD-STOPS the seat (escalate/replace), it does not DEGRADE the council by treating quiet as agreement. Degrading here would silently corrupt the stopping rule (CNL-0008)."
    },
    "detector_control": {
      "known_present_run_first": true,
      "fired_before_absence_reported": true,
      "known_present_fixture": "planted-filler-consent.json",
      "known_present_fired": true,
      "known_present_verbatim": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false}"
    },
    "both_states": {
      "planted": {
        "fixture_id": "planted-filler-consent",
        "file": "planted-filler-consent.json",
        "fired": true,
        "silent": false,
        "fired_seats": [
          "D"
        ],
        "reasons": {
          "D": [
            "no-speech-act",
            "filler-masquerade",
            "consent-by-silence"
          ]
        },
        "speech": {
          "A": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "B": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "C": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "D": {
            "substantive": 0,
            "structured_yield": 0,
            "filler": 3,
            "explicit_vote": null
          }
        },
        "runtime": {
          "escalate_or_mark_absent": [
            "D"
          ],
          "accept_structured_yield": [],
          "exclude_from_consenting_set": [
            "D"
          ],
          "consenting_must_have_explicit_vote": true,
          "disengaged_remain_in_roster_for_quorum": true
        },
        "verbatim": "{\"fired\": true, \"fired_seats\": [\"D\"], \"fixture_id\": \"planted-filler-consent\", \"reasons\": {\"D\": [\"no-speech-act\", \"filler-masquerade\", \"consent-by-silence\"]}, \"silent\": false}"
      },
      "clean": {
        "fixture_id": "clean-yield-only-nothing-to-add",
        "file": "clean-yield-only-nothing-to-add.json",
        "fired": false,
        "silent": true,
        "fired_seats": [],
        "reasons": {},
        "speech": {
          "A": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "B": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "C": {
            "substantive": 2,
            "structured_yield": 0,
            "filler": 0,
            "explicit_vote": "AYE"
          },
          "D": {
            "substantive": 0,
            "structured_yield": 1,
            "filler": 0,
            "explicit_vote": null
          }
        },
        "runtime": {
          "escalate_or_mark_absent": [],
          "accept_structured_yield": [
            "D"
          ],
          "exclude_from_consenting_set": [],
          "consenting_must_have_explicit_vote": true,
          "disengaged_remain_in_roster_for_quorum": true
        },
        "verbatim": "{\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-yield-only-nothing-to-add\", \"reasons\": {}, \"silent\": true}"
      }
    },
    "false_positive_rate": 0.0,
    "false_positive_count": 0,
    "clean_count": 4,
    "planted_count": 4,
    "fixture_battery": {
      "planted": [
        {
          "file": "planted-fake-yield.json",
          "fired": true,
          "fired_seats": [
            "D"
          ],
          "reasons": {
            "D": [
              "no-speech-act",
              "consent-by-silence"
            ]
          }
        },
        {
          "file": "planted-filler-consent.json",
          "fired": true,
          "fired_seats": [
            "D"
          ],
          "reasons": {
            "D": [
              "no-speech-act",
              "filler-masquerade",
              "consent-by-silence"
            ]
          }
        },
        {
          "file": "planted-ghost-after-claim.json",
          "fired": true,
          "fired_seats": [
            "D"
          ],
          "reasons": {
            "D": [
              "inactivity-without-yield"
            ]
          }
        },
        {
          "file": "planted-never-speaks.json",
          "fired": true,
          "fired_seats": [
            "D"
          ],
          "reasons": {
            "D": [
              "no-speech-act",
              "consent-by-silence"
            ]
          }
        }
      ],
      "clean": [
        {
          "file": "clean-all-engaged.json",
          "fired": false,
          "silent": true
        },
        {
          "file": "clean-substance-one-filler-then-vote.json",
          "fired": false,
          "silent": true
        },
        {
          "file": "clean-substance-then-yield.json",
          "fired": false,
          "silent": true
        },
        {
          "file": "clean-yield-only-nothing-to-add.json",
          "fired": false,
          "silent": true
        }
      ]
    },
    "negative_control": {
      "state_meant_to_reject": "firing on an engaged council (clean-all-engaged) or on a structured nothing-to-add yield",
      "what_the_check_did": "SILENT on clean-all-engaged and on clean-yield-only-nothing-to-add; fired=false, fired_seats=[]",
      "verbatim": "{\"fired\": false, \"fired_seats\": [], \"fixture_id\": \"clean-all-engaged\", \"silent\": true}"
    },
    "three_empty_acknowledgements_satisfy_floor": false,
    "answer": "Nothing-to-add is a structured yield: a YIELD/PASS speech-act with a closed reason_code and a referent_id. The runtime credits the engagement floor, skips leftover quota, and must not treat the yield as consent. Disengagement is the absence of that speech-act: filler-only turns (three empty acknowledgements fail the floor), never speaking, being folded into consensus.agreeing without a vote, or ghosting for max_inactivity rounds after a contribution without yielding. The runtime FIRES, marks the seat ABSENT, excludes it from the consenting set, keeps it in the roster so quorum cannot shrink, and escalates or replaces. False-positive rate on the four clean fixtures is 0.0. SUCCESS:CNL-0089",
    "live_tree_anchors": [
      {
        "path": "command-center/p2-wave/probes/CNL-0089/detector.py",
        "line": 68,
        "claim": "structured yield requires closed reason_code and referent_id"
      },
      {
        "path": "command-center/p2-wave/probes/CNL-0089/detector.py",
        "line": 163,
        "claim": "three filler turns with zero speech-acts trip filler-masquerade"
      },
      {
        "path": "command-center/p2-wave/probes/CNL-0089/detector.py",
        "line": 165,
        "claim": "agreeing without an explicit vote is consent-by-silence"
      },
      {
        "path": "command-center/p2-wave/probes/CNL-0089/detector.py",
        "line": 180,
        "claim": "post-claim silence without yield is inactivity disengagement"
      }
    ]
  },
  "extensions": {
    "cloud_ok": false,
    "produced_at": "2026-08-25T00:58:13Z"
  }
}
