{
  "artifacts": [
    {
      "bytes": 11216,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0086/detector.py",
      "role": "primary",
      "sha256": "66236ed8c514e6056f5a440c45f19f127fa3f2629371a540f5b69c252f1ffc80"
    },
    {
      "bytes": 13422,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0086/fixtures.py",
      "role": "fixture",
      "sha256": "2c173f3ea62d0b433c603bb95ab80f2e2b0de76ec1fb4e8c236661b693768977"
    },
    {
      "bytes": 1611,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0086/reviewer.py",
      "role": "supporting",
      "sha256": "d33f88d9f0bd5b8df09ab711d938f746149203b54c3da6d6a8be01e6e1433857"
    }
  ],
  "defects": [],
  "downstream_consumers": [
    {
      "artifact_path": "command-center/design/council/CNL-0086-echo-chamber-measuring-independence-loss.md",
      "consumer": "platform/lib/schema_resolver.py (validate_artifact)",
      "executed": true,
      "exit_code": 0,
      "probe": {
        "command": "python3 -c \"import sys; sys.path.insert(0,'platform/lib'); import json,schema_resolver as s; p='command-center/design/council/CNL-0086-echo-chamber-measuring-independence-loss.md'; d=json.load(open(p,encoding='utf-8')); e=s.validate_artifact(d,'command-center/schema/council-detector-spec.schema.json'); print(e or 'ok')\"",
        "exit_code": 0,
        "fingerprint": "resolver:council-detector-spec",
        "method": "schema-validate",
        "raw_output": "ok",
        "role": "verifier"
      },
      "read_ok": true
    }
  ],
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0086/detector.py",
      "claim": "Detector FIREs on independently generated briefs that share one private retrieved source and the same warrants, and is SILENT when the same conclusion is reached from disjoint private sources and disjoint warrants.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/detector.py --fixture planted-bad-shared-source",
          "exit_code": 0,
          "fingerprint": "detector:s1-shared-source",
          "method": "test-run",
          "raw_output": "fixture=planted-bad-shared-source status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5",
          "role": "source"
        },
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe1_both_states.py",
          "exit_code": 0,
          "fingerprint": "probe1:both-states",
          "method": "command",
          "raw_output": "fixture=planted-bad-shared-source status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5 | fixture=known-good-genuine-convergence status=SILENT fired=False absence_claimed=True src_j=0.0 w_j=0.0 agree=1.0 s1=False s2=False residue_applicable=False residue_rate=None reason=no echo: source Jaccard 0.000<0.5 or warrant Jaccard 0.000<0.5; residue applicable=False rate=None agreement=1.000",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0086/probe2_schema_decoy.py",
      "claim": "A generation-independence decoy is SILENT on the shared-source planted-bad; a vote-agreement decoy FIREs on the known-good. Neither is this unit's signal.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/detector.py --fixture planted-bad-shared-source --decoy generation",
          "exit_code": 0,
          "fingerprint": "decoy:generation-vs-vote",
          "method": "static-analysis",
          "raw_output": "gen_decoy_fired=False vote_decoy_fired=True real_bad_fired=True real_good_fired=False",
          "role": "source"
        },
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe2_schema_decoy.py",
          "exit_code": 0,
          "fingerprint": "probe2:schema-decoy",
          "method": "command",
          "raw_output": "gen_decoy_fired=False vote_decoy_fired=True real_bad_fired=True real_good_fired=False",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    }
  ],
  "manifest_registration": {
    "entry_id": "CNL-0086",
    "manifest_path": "command-center/p2-wave/probes/CNL-0086/UNIT-ARTIFACT-MANIFEST.json",
    "registered": true
  },
  "min_bytes_threshold": 2048,
  "negative_controls": [
    {
      "bad_state_output": "fixture=planted-bad-shared-source status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5",
      "description": "Planted shared-source briefs must FIRE; genuine convergence on disjoint sources and warrants must be SILENT.",
      "fired_on_bad_state": true,
      "good_state_output": "fixture=known-good-genuine-convergence status=SILENT fired=False absence_claimed=True src_j=0.0 w_j=0.0 agree=1.0 s1=False s2=False residue_applicable=False residue_rate=None reason=no echo: source Jaccard 0.000<0.5 or warrant Jaccard 0.000<0.5; residue applicable=False rate=None agreement=1.000",
      "id": "NC-shared-source-vs-genuine-convergence",
      "kind": "known-broken-fixture",
      "silent_on_good_state": true
    }
  ],
  "produced_by": {
    "execution_substrate": "local-parallel",
    "model": "gpt-5-codex",
    "role": "council-anti-failure-detector-designer",
    "vendor": "openai"
  },
  "report": {
    "both_states": {
      "known_good": {
        "fired": false,
        "fixture": "known-good-genuine-convergence",
        "verbatim": "fixture=known-good-genuine-convergence status=SILENT fired=False absence_claimed=True src_j=0.0 w_j=0.0 agree=1.0 s1=False s2=False residue_applicable=False residue_rate=None reason=no echo: source Jaccard 0.000<0.5 or warrant Jaccard 0.000<0.5; residue applicable=False rate=None agreement=1.000"
      },
      "planted_bad": {
        "fired": true,
        "fixture": "planted-bad-shared-source",
        "verbatim": "fixture=planted-bad-shared-source status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5"
      }
    },
    "clean_fixture_ids": [
      "known-good-genuine-convergence",
      "clean-late-agreement",
      "clean-public-premises-only",
      "clean-easy-distinct-paths"
    ],
    "clean_n": 4,
    "completion": "SUCCESS:CNL-0086",
    "control_ids": [
      "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe1_both_states.py",
      "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe2_schema_decoy.py"
    ],
    "decoy_contrast": {
      "generation_independence_on_shared_source_fired": false,
      "vote_agreement_on_known_good_fired": true
    },
    "detector": {
      "fire_rule": "S1 (source Jaccard>=0.50 AND warrant Jaccard>=0.50) OR S2 (residue<0.25 AND agreement>=0.80 with later turns)",
      "id": "CNL-0086-independence-loss",
      "implementation": "command-center/p2-wave/probes/CNL-0086/detector.py",
      "not_a_signal": "generated_independently bits (decoy SILENT on planted-bad shared-source) and unanimous votes (decoy FIRE on known-good agreement=1.0).",
      "signal": "S1 shared-retrieval: first-pass private-source Jaccard and first-pass warrant Jaccard. S2 sequential-copy: post-exposure new-warrant residue collapsing while conclusions agree."
    },
    "detector_control": {
      "evaluated_before_absence": true,
      "found": true,
      "known_present_fixture": "known-present",
      "raw_output": "fixture=known-present status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5",
      "verbatim": "fixture=known-present status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5"
    },
    "detector_implementation": "command-center/p2-wave/probes/CNL-0086/detector.py",
    "false_negative_rate": 0.0,
    "false_positive_rate": 0.0,
    "false_positives": 0,
    "kind": "council-detector-spec",
    "negative_control": {
      "does": "FIRE on S1 (private-source Jaccard and warrant Jaccard both >= 0.50). Does not consult generated_independently or votes.",
      "reject_state": "planted-bad-shared-source: three independently GENERATED first-pass briefs that share one private retrieved source and the same warrant ids",
      "verbatim": "fixture=planted-bad-shared-source status=FIRE fired=True absence_claimed=False src_j=1.0 w_j=1.0 agree=1.0 s1=True s2=False residue_applicable=False residue_rate=None reason=S1 shared-retrieval: private-source Jaccard 1.000>=0.5 and warrant Jaccard 1.000>=0.5"
    },
    "no_first_pass_control": {
      "absence_claimed": false,
      "fixture": "no-first-pass",
      "status": "INSUFFICIENT",
      "verbatim": "fixture=no-first-pass status=INSUFFICIENT fired=False absence_claimed=False src_j=0.0 w_j=0.0 agree=1.0 s1=False s2=False residue_applicable=False residue_rate=None reason=fewer than two first-pass briefs; not reported as clean silence"
    },
    "observations": [
      {
        "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe1_both_states.py",
        "measured": 0.0,
        "method": "clean-fixture-fire-count / clean_n",
        "name": "false_positive_rate"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0086/detector.py",
        "measured": true,
        "method": "detector.detect on planted-bad-shared-source",
        "name": "planted_bad_s1_fired"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0086/detector.py",
        "measured": true,
        "method": "detector.detect on known-good-genuine-convergence",
        "name": "known_good_silent"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0086/detector.py",
        "measured": true,
        "method": "detector.detect on planted-bad-sequential-anchor",
        "name": "sequential_s2_fired"
      }
    ],
    "pathology": "Participants stop producing independent warrants and private sources even when conclusions agree. Independently GENERATED briefs that share one retrieved private source and the same warrants are echo. Sequential copy after exposure is echo even if first passes were disjoint. Unanimous votes are not the pathology.",
    "predicate": {
      "fire_when": "(mean private-source Jaccard >= 0.50 AND mean first-pass warrant Jaccard >= 0.50) OR (later turns exist AND mean new-warrant residue < 0.25 AND final conclusion agreement >= 0.80)",
      "ignores": [
        "generated_independently",
        "vote agreement alone",
        "converge.round",
        "suspicion_max_round",
        "chair_echo_jaccard_min",
        "min_brief_chars",
        "declared role labels"
      ],
      "silent_when": "at least two first-pass briefs exist AND neither S1 nor S2 holds, including genuine same-conclusion runs with disjoint private sources and disjoint warrants"
    },
    "question": "What measurement shows that participants stopped reasoning independently - and can it distinguish genuine convergence on a correct answer from mutual anchoring?",
    "reviewer_execution": {
      "detail": {
        "known_good_fired": false,
        "known_present_fired": true,
        "planted_bad_fired": true,
        "planted_bad_s1": true,
        "sequential_fired": true,
        "sequential_s2": true
      },
      "executed_both_states": true,
      "independent": true,
      "reviewer_id": "CNL-0086-both-states-rerun",
      "verdict": "PASS"
    },
    "sequential_control": {
      "fired": true,
      "fixture": "planted-bad-sequential-anchor",
      "s1": false,
      "s2": true,
      "verbatim": "fixture=planted-bad-sequential-anchor status=FIRE fired=True absence_claimed=False src_j=0.0 w_j=0.0 agree=1.0 s1=False s2=True residue_applicable=True residue_rate=0.0 reason=S2 sequential-copy: mean new-warrant rate 0.000<0.25 and conclusion agreement 1.000>=0.8"
    },
    "spec_anchors": [
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0086",
        "claim": "What measurement shows that participants stopped reasoning independently - and can it distinguish genuine convergence on a correct answer from mutual anchoring?",
        "id": "CNL-0086-question",
        "status": "MANDATED"
      },
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:ADV-0135",
        "claim": "Independently GENERATED first-pass briefs that share one retrieved source must still count as echo; a check that only measures generation independence is defeated.",
        "id": "ADV-0135-shared-retrieval",
        "status": "RESTATED-IN-CATALOG"
      }
    ],
    "threshold": {
      "collapse_signals": [
        "mean private-source Jaccard >= 0.50 AND mean first-pass warrant Jaccard >= 0.50",
        "post-exposure mean new-warrant rate < 0.25 AND final conclusion agreement >= 0.80"
      ],
      "numeric": {
        "T_AGREE": 0.8,
        "T_RESIDUE": 0.25,
        "T_SRC": 0.5,
        "T_WARRANT": 0.5,
        "chair_echo_jaccard_min": 1.0,
        "min_brief_chars": 1,
        "pairwise_jaccard_min": 0.5,
        "suspicion_max_round": 999
      },
      "primary_unit": "Mean pairwise Jaccard of first-pass PRIVATE sources and of first-pass warrant ids, or post-exposure new-warrant residue while final conclusions agree",
      "rejected_units": [
        "unanimous final votes",
        "generated_independently bits",
        "lexical paraphrase distance on brief text",
        "declared role diversity",
        "suspicion_max_round / chair_echo_jaccard_min / min_brief_chars"
      ],
      "suspicion_window": "S1 uses only first-pass briefs. S2 uses later turns after those first passes. Public premises listed on the run are subtracted from source sets before Jaccard."
    },
    "title": "Echo chamber: measuring independence loss"
  },
  "residual_unknowns": [
    {
      "claim": "CNL-0006 information-partition lattice is not on this tree; public_premises is a fixture field standing in for the question packet.",
      "settling_experiment": "Re-run S1 after CNL-0006 ships and substitute its public packet ids for fixture public_premises.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "CNL-0021 duplicate-seat / same-base-model detection is not on this tree; this detector does not read model identity and may FIRE when two seats are the same model producing identical private sources.",
      "settling_experiment": "After CNL-0021 exists, run a same-model independent-source fixture and confirm this detector stays SILENT.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "Warrant ids are fixture-supplied. Independently discovered identical arguments that do not share ids would be SILENT on S1; S2 still fires if later turns copy a peer after exposure.",
      "settling_experiment": "Add a live-model fixture that paraphrases the same argument without shared warrant ids and measure S1/S2.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "Fresh-vendor gpt-5-codex signature is not on this tree; reviewer.py is an independent both-states re-execution of the same detector.",
      "settling_experiment": "Dispatch a gpt-5-codex reviewer to re-run probe1 without this emit's prose.",
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
    "notes": "Re-ran known-present, planted-bad, known-good, and sequential fixtures through detector.detect without reading emit prose. executed_both_states=True.",
    "reviewed_at": "2026-08-25T00:57:45Z",
    "reviewer_id": "CNL-0086-both-states-rerun",
    "vendor": "openai",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0086",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0086",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe1_both_states.py",
      "id": "T1-detector-control-both-states-fpr",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0086/probe2_schema_decoy.py",
      "id": "T2-schema-decoy-s1-s2",
      "result": "PASS"
    }
  ],
  "timestamps": {
    "duration_seconds": 90,
    "ended_at": "2026-08-25T00:57:45Z",
    "started_at": "2026-08-25T00:56:15Z"
  },
  "unit_id": "CNL-0086"
}
