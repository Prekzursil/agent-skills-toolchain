{
  "artifacts": [
    {
      "bytes": 9575,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/detector.py",
      "role": "primary",
      "sha256": "61ce21af77f0d3cf75521db2874e27f9c2616c69853d429b2204d4b391b0f97a"
    },
    {
      "bytes": 9311,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/fixtures.py",
      "role": "fixture",
      "sha256": "2006c499e0c7b967c590a5f32bf94c92ca895d3e9d603cd18f61df90db4878f6"
    },
    {
      "bytes": 2410,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/transcript.py",
      "role": "supporting",
      "sha256": "ab407706e09fc3c5e7bb206a5d4bee641749cb28362c8dbd36236b0b122277dd"
    },
    {
      "bytes": 1611,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/breadth.py",
      "role": "supporting",
      "sha256": "c25c951c5555a8da4805dec7c7e7a91da781d33dc180011ebd735f6632c9e7dc"
    },
    {
      "bytes": 5631,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
      "role": "control",
      "sha256": "a970cf7024c59472efbd26205dd333d6d8bdc6e6bcdac03744f1270111ec6750"
    },
    {
      "bytes": 4650,
      "eol": "LF",
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
      "role": "control",
      "sha256": "e964d2b65b9d24577fefceca01133330b9be5af44f35771c6ba5aa092eec9bf5"
    }
  ],
  "downstream_consumers": [
    {
      "artifact_path": "command-center/design/council/CNL-0095-premature-convergence-and-forced-re-divergence.md",
      "consumer": "jsonschema Draft202012Validator via disk-only $id store",
      "executed": true,
      "exit_code": 0,
      "probe": {
        "command": "python3 command-center/p2-wave/probes/CNL-0095/schema_validate.py",
        "exit_code": 0,
        "fingerprint": "cnl0095:schema-validate",
        "method": "schema-validate",
        "raw_output": "in-memory receipt validated before write",
        "role": "verifier"
      },
      "read_ok": true
    }
  ],
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
      "claim": "Detector FIREs on paraphrase-padded premature first converge.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:probe1:planted-bad",
          "method": "command",
          "raw_output": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
          "role": "source"
        },
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:probe2:theater-vs-complement",
          "method": "test-run",
          "raw_output": "theater coverage_delta=0.0 permitted=False complement coverage_delta=0.8333333333333334 permitted=True breadth_recovered=True",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
      "claim": "Detector is SILENT when both quotas are met with distinct clusters.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:probe1:known-good",
          "method": "command",
          "raw_output": "fixture=known-good status=SILENT fired=False absence_claimed=True idea_clusters=6 objection_clusters=4 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=6 covered=['correctness', 'cost', 'latency', 'operability', 'rollback', 'safety']",
          "role": "source"
        },
        {
          "command": "command-center/p2-wave/probes/CNL-0095/reviewer.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:reviewer:both-states",
          "method": "file-read",
          "raw_output": "reviewer_verdict=PASS known_good_fired=False",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
      "claim": "Known-present instance is found before any absence is reported.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:probe1:detector-control",
          "method": "command",
          "raw_output": "fixture=known-present status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
          "role": "source"
        },
        {
          "command": "command-center/p2-wave/probes/CNL-0095/reviewer.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:reviewer:known-present",
          "method": "test-run",
          "raw_output": "known_present_fired=True",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
      "claim": "Second-round theater does not raise category coverage or permit reconverge; complement re-divergence does both.",
      "confidence": "almost-certain",
      "probes": [
        {
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:probe2:coverage",
          "method": "command",
          "raw_output": "theater coverage_delta=0.0 permitted=False complement coverage_delta=0.8333333333333334 permitted=True breadth_recovered=True",
          "role": "source"
        },
        {
          "command": "command-center/p2-wave/probes/CNL-0095/breadth.py",
          "exit_code": 0,
          "fingerprint": "cnl0095:breadth:category-coverage",
          "method": "static-analysis",
          "raw_output": "theater_delta=0.0 complement_delta=0.8333333333333334",
          "role": "verifier"
        }
      ],
      "verdict": "CONFIRMED"
    }
  ],
  "manifest_registration": {
    "entry_id": "CNL-0095",
    "manifest_path": "command-center/p2-wave/probes/CNL-0095/UNIT-ARTIFACT-MANIFEST.json",
    "registered": true
  },
  "min_bytes_threshold": 512,
  "negative_controls": [
    {
      "bad_state_output": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
      "description": "planted-bad: first converge with paraphrase-padded idea and objection events whose Jaccard clusters are below declared quotas",
      "fired_on_bad_state": true,
      "good_state_output": "fixture=known-good status=SILENT fired=False absence_claimed=True idea_clusters=6 objection_clusters=4 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=6 covered=['correctness', 'cost', 'latency', 'operability', 'rollback', 'safety']",
      "id": "NC-PLANTED-BAD",
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
  "report": {
    "both_states": {
      "known_good": {
        "fired": false,
        "fixture": "known-good",
        "raw_output": "fixture=known-good status=SILENT fired=False absence_claimed=True idea_clusters=6 objection_clusters=4 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=6 covered=['correctness', 'cost', 'latency', 'operability', 'rollback', 'safety']",
        "verbatim": "fixture=known-good status=SILENT fired=False absence_claimed=True idea_clusters=6 objection_clusters=4 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=6 covered=['correctness', 'cost', 'latency', 'operability', 'rollback', 'safety']"
      },
      "planted_bad": {
        "fired": true,
        "fixture": "planted-bad",
        "raw_output": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
        "verbatim": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']"
      }
    },
    "clean_fixture_ids": [
      "known-good",
      "easy-met-quota",
      "clean-over-quota",
      "clean-late-round-met",
      "clean-exact-quota"
    ],
    "clean_n": 5,
    "completion": "SUCCESS:CNL-0095",
    "control_ids": [
      "known-present",
      "planted-bad",
      "known-good",
      "easy-met-quota",
      "round10-premature",
      "theater-second-round",
      "complement-rediverge"
    ],
    "dependencies_on_disk": {
      "CNL-0054": false,
      "CNL-0077": false
    },
    "detector": {
      "fire_rule": "first_converge exists AND (idea_clusters < idea_quota OR objection_clusters < objection_quota)",
      "id": "CNL-0095-quota-attainment",
      "implementation": "command-center/p2-wave/probes/CNL-0095/detector.py",
      "no_converge_is_not_silence": true,
      "not_a_signal": "converge.round, event counts, and question_class. Event-count decoy SILENT on planted-bad (6 idea events, 4 objection events). Round-count decoy FIREs on easy-met-quota and is SILENT on round10-premature.",
      "signal": "At the first converge event, count Jaccard-0.80 unique idea clusters and unique objection clusters in prior events. FIRE if either count is below the declared divergence quota."
    },
    "detector_control": {
      "evaluated_before_absence": true,
      "found": true,
      "known_present_fixture": "known-present",
      "raw_output": "fixture=known-present status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
      "verbatim": "fixture=known-present status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']"
    },
    "detector_implementation": "command-center/p2-wave/probes/CNL-0095/detector.py",
    "easy_question_control": {
      "fired": false,
      "fixture": "easy-met-quota",
      "raw_output": "fixture=easy-met-quota status=SILENT fired=False absence_claimed=True idea_clusters=2 objection_clusters=2 idea_quota=2 objection_quota=2 idea_events=2 objection_events=2 converge_round=1 covered=['latency', 'operability']"
    },
    "false_negative_rate": 0.0,
    "false_positive_rate": 0.0,
    "false_positives": 0,
    "intervention": {
      "complement_breadth_recovered": true,
      "complement_coverage_delta": 0.8333333333333334,
      "complement_covered_first": [
        "latency"
      ],
      "complement_covered_last": [
        "correctness",
        "cost",
        "latency",
        "operability",
        "rollback",
        "safety"
      ],
      "complement_permits_reconverge": true,
      "id": "forced-re-divergence-complement-quota",
      "independent_signal": "taxonomy category coverage from breadth.py, a different data field than the detector's Jaccard cluster counts",
      "mandate": {
        "freeze_converge_index": 10,
        "freeze_thesis": "Adopt the Redis session-store cache and stop.",
        "kind": "forced-re-divergence",
        "not": "second-round-of-same-protocol",
        "reconverge_blocked_until": "post-freeze new idea clusters in require_categories (or Jaccard-far if require_categories empty) meet the missing idea quota AND new objection clusters meet the missing objection quota",
        "require_categories": [
          "cost",
          "safety",
          "operability",
          "correctness",
          "rollback"
        ],
        "require_new_idea_clusters": 5,
        "require_new_objection_clusters": 3
      },
      "not": "a second round of the same protocol",
      "recovers_breadth_by": "Freeze the premature thesis. Require the missing idea-cluster quota as NEW clusters whose category is in the uncovered taxonomy complement (or Jaccard-far if the complement is empty), plus the missing objection-cluster quota against the frozen thesis. Reconverge is blocked until those post-freeze quotas are met.",
      "theater_coverage_delta": 0.0,
      "theater_covered_first": [
        "latency"
      ],
      "theater_covered_last": [
        "latency"
      ],
      "theater_permits_reconverge": false
    },
    "kind": "council-detector-spec",
    "negative_control": {
      "detector_action": "FIRE",
      "does": "FIRE with quota-shortfall reason; does not use round count",
      "raw_output": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']",
      "reject_state": "planted-bad: first converge with paraphrase-padded idea and objection events whose Jaccard clusters are below declared quotas",
      "state_rejected": "planted-bad: first converge with paraphrase-padded idea and objection events whose Jaccard clusters are below declared quotas",
      "verbatim": "fixture=planted-bad status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=1 covered=['latency']"
    },
    "no_converge_control": {
      "absence_claimed": false,
      "fixture": "no-converge",
      "raw_output": "fixture=no-converge status=NO-CONVERGE fired=False absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=6 objection_events=4 converge_round=None covered=['latency']",
      "status": "NO-CONVERGE"
    },
    "observations": [
      {
        "anchor": "command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
        "measured": 0.0,
        "method": "fired-count over clean_fixtures() / n",
        "name": "false_positive_rate"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
        "measured": 0.0,
        "method": "breadth.coverage_report category set size / taxonomy n",
        "name": "theater_coverage_delta"
      },
      {
        "anchor": "command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
        "measured": 0.8333333333333334,
        "method": "breadth.coverage_report category set size / taxonomy n",
        "name": "complement_coverage_delta"
      }
    ],
    "pathology": "Council emits converge before declared divergence idea and objection quotas are attained as unique Jaccard clusters. Round count is not the pathology: round-1 with quotas met is an easy question; round-10 with one paraphrase cluster is still premature.",
    "predicate": {
      "fire_when": "first converge exists AND (idea_clusters < idea_quota OR objection_clusters < objection_quota)",
      "ignores": [
        "converge.round",
        "question_class",
        "raw event counts",
        "suspicion_max_round",
        "chair_echo_jaccard_min"
      ],
      "silent_when": "first converge exists AND idea_clusters >= idea_quota AND objection_clusters >= objection_quota"
    },
    "question": "What signal shows a council converged before exploring the space, and what re-divergence intervention actually recovers the lost breadth rather than performing a second round?",
    "round_count_is_not_the_signal": {
      "decoy_round_easy_fired": true,
      "decoy_round_late_fired": false,
      "easy_round1_fired": false,
      "raw_output": "fixture=round10-premature status=FIRE fired=True absence_claimed=False idea_clusters=1 objection_clusters=1 idea_quota=6 objection_quota=4 idea_events=10 objection_events=10 converge_round=10 covered=['latency']",
      "round10_premature_fired": true
    },
    "spec_anchors": [
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0077",
        "claim": "Council must not stop before minimum deliberation conditions.",
        "id": "FC-11338",
        "status": "RESTATED-IN-CATALOG"
      },
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0095",
        "claim": "What signal shows a council converged before exploring the space, and what re-divergence intervention actually recovers the lost breadth rather than performing a second round?",
        "id": "CNL-0095-question",
        "status": "MANDATED"
      },
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0077",
        "claim": "Minimum deliberation floors outrank any early stop expression.",
        "id": "CNL-0077-floors",
        "status": "ABSENT-ON-WORKTREE"
      },
      {
        "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0051",
        "claim": "Lexical Jaccard merges paraphrases and misses full rewrites.",
        "id": "CNL-0051-jaccard",
        "status": "RESTATED-IN-CATALOG"
      }
    ],
    "threshold": {
      "collapse_signals": [
        "idea_clusters < idea_quota at first converge",
        "objection_clusters < objection_quota at first converge"
      ],
      "numeric": {
        "chair_echo_jaccard_min": 1.0,
        "min_brief_chars": 1,
        "pairwise_jaccard_min": 0.8,
        "suspicion_max_round": 999,
        "unused_schema_fields": [
          "suspicion_max_round",
          "chair_echo_jaccard_min",
          "min_brief_chars"
        ],
        "used_by_this_unit": [
          "pairwise_jaccard_min"
        ]
      },
      "primary_unit": "Jaccard-0.80 unique idea clusters and unique objection clusters versus declared divergence quotas at first converge",
      "rejected_units": [
        "converge.round as a stop/fire signal",
        "raw idea or objection event counts (paraphrase padding)",
        "question_class labels"
      ],
      "suspicion_window": "All events before the first converge event. converge.round is recorded and ignored; it is not a threshold."
    },
    "title": "Premature convergence and forced re-divergence"
  },
  "residual_unknowns": [
    {
      "claim": "Live CNL-0054 taxonomy is absent on this tree; coverage uses a planted six-category fixture taxonomy.",
      "settling_experiment": "Recompute coverage_report against the CNL-0054 taxonomy file once CNL-0054-category-taxonomy-coverage-and-diversity-as-one-measuremen.md exists.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "CNL-0051: lexical Jaccard merges renames/paraphrases and misses full rewrites of the same mechanism; a second semantic signal is not implemented here.",
      "settling_experiment": "Add a mechanism-key probe (CNL-0051) and report the rewrite class as NOT-CHECKED until that signal exists.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "CNL-0077 minimum-deliberation floors are not on disk as the catalog output_path; this detector is the runtime quota check those floors would outrank a stop expression with.",
      "settling_experiment": "When CNL-0077's catalog output_path exists, bind idea/objection quotas to its floors instead of fixture declared_divergence.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "Shared schema numeric fields suspicion_max_round, chair_echo_jaccard_min, and min_brief_chars are unused by this unit.",
      "settling_experiment": "Leave unused; they belong to other CNL detectors.",
      "verdict": "NOT-CHECKED"
    },
    {
      "claim": "Source slices cited as Windows harness-restore paths are not present on this Linux worktree.",
      "settling_experiment": "Fetch the restore tree or restated catalog quotes and re-anchor line-level spec cites.",
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
    "notes": "Mechanical both-states re-run of detector.detect on fixtures; planted_bad_fired=True known_good_fired=False known_present_fired=True easy_fired=False round10_premature_fired=True",
    "reviewer_id": "CNL-0095-both-states-rerun",
    "vendor": "openai",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0095",
  "spec_anchor": "_USER-PROMPTS.md:10746-10767",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe1_both_states.py",
      "id": "T1-detector-control-both-states-fpr",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0095/probe2_redivergence.py",
      "id": "T2-redivergence-vs-theater",
      "result": "PASS"
    }
  ],
  "timestamps": {
    "duration_seconds": 0,
    "ended_at": "2026-08-25T00:59:11Z",
    "started_at": "2026-08-25T00:59:11Z"
  },
  "unit_id": "CNL-0095"
}
