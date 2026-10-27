{
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0092-missing-expertise-detection-and-the-recruitment-trigger.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0092/detector.py",
      "role": "implementation"
    }
  ],
  "bad_fixture_ids": [
    "bad-uncovered-unanimous",
    "bad-declared-only",
    "bad-evidence-low-score",
    "bad-score-no-evidence",
    "bad-sharpen-law"
  ],
  "both_states": {
    "known_good_fixture_id": "good-split-cover",
    "known_good_silent": true,
    "planted_bad_fired": true,
    "planted_fixture_id": "bad-uncovered-unanimous",
    "verbatim_bad": "{\"baseline\": 0.5, \"behavioral_uncovered\": [\"crypto-protocol-design\", \"threat-modeling\"], \"confidence_clears_gap\": false, \"covered\": [\"frontend-engineering\", \"product-management\"], \"declared_only_uncovered\": [\"crypto-protocol-design\"], \"fired\": true, \"high_confidence_vote\": true, \"named_uncovered\": [\"crypto-protocol-design\", \"threat-modeling\"], \"required\": [\"crypto-protocol-design\", \"threat-modeling\"], \"seat_count\": 3, \"silent\": false, \"unanimous_vote\": true, \"unit\": \"CNL-0092\"}",
    "verbatim_good": "{\"baseline\": 0.5, \"behavioral_uncovered\": [], \"confidence_clears_gap\": false, \"covered\": [\"crypto-protocol-design\", \"product-management\", \"threat-modeling\"], \"declared_only_uncovered\": [], \"fired\": false, \"high_confidence_vote\": true, \"named_uncovered\": [], \"required\": [\"crypto-protocol-design\", \"threat-modeling\"], \"seat_count\": 3, \"silent\": true, \"unanimous_vote\": true, \"unit\": \"CNL-0092\"}"
  },
  "completion_sentinel": "SUCCESS:CNL-0092",
  "dependencies_consumed_as_interfaces": {
    "CNL-0015": "evidence_record_id required before a competency counts as cover or as a recruitable qualification",
    "CNL-0020": "catch-up briefing must not include the standing majority"
  },
  "detector": {
    "baseline": 0.5,
    "baseline_pre_registered": true,
    "fire_condition": "named_uncovered non-empty",
    "id": "CNL-0092-coverage-gap",
    "implementation": "command-center/p2-wave/probes/CNL-0092/detector.py",
    "rule": "covered(C) iff exists seat S with non-empty evidenced_competencies[C] AND probe_scores[C] > 0.5 (pre-registered). fire iff set(required_competencies) - covered is non-empty. Name the remainder.",
    "signals": [
      {
        "id": "S1-coverage-set-difference",
        "independent_of": "vote position, vote confidence, declared tags",
        "mechanism": "set difference of required competencies vs evidenced+scored cover"
      },
      {
        "id": "S2-known-answer-probe",
        "independent_of": "S1 declared-tag listing; a declared tag without evidence does not cover",
        "mechanism": "numeric score vs pre-registered baseline; evidence_id must be present"
      }
    ],
    "silence_condition": "every required competency is evidenced and scored above baseline by at least one seat"
  },
  "detector_control": {
    "absence_reported_only_after": true,
    "known_present_fired": true,
    "known_present_fixture": "bad-uncovered-unanimous",
    "known_present_ran_first": true
  },
  "evidence": [
    {
      "claim": "planted_bad fires and names crypto-protocol-design and threat-modeling",
      "path": "command-center/p2-wave/probes/CNL-0092/fixtures.py",
      "signal": "planted-bad"
    },
    {
      "claim": "known_good is silent with false_positive_rate computed over the good family",
      "path": "command-center/p2-wave/probes/CNL-0092/fixtures.py",
      "signal": "known-good"
    },
    {
      "claim": "{\"actions\": [{\"action\": \"RECRUIT\", \"briefing\": {\"includes_question\": true, \"includes_standing_majority\": false}, \"competency\": \"crypto-protocol-design\", \"novel_claims\": [\"ticket-binding-must-cover-0-rtt\", \"rotation-needs-epoch-mac\"], \"seat\": \"recruited-cryptographer\"}], \"confident_answer_allowed\": true, \"novel_claim_ids\": [\"ticket-binding-must-cover-0-rtt\", \"rotation-needs-epoch-mac\"], \"post_named_uncovered\": []}",
      "path": "command-center/p2-wave/probes/CNL-0092/detector.py",
      "signal": "recruitment-qualified"
    },
    {
      "claim": "{\"actions\": [{\"action\": \"PARK\", \"competency\": \"crypto-protocol-design\", \"reason\": \"no-evidenced-pool-candidate\"}, {\"action\": \"PARK\", \"competency\": \"threat-modeling\", \"reason\": \"no-evidenced-pool-candidate\"}], \"confident_answer_allowed\": false}",
      "path": "command-center/p2-wave/probes/CNL-0092/detector.py",
      "signal": "recruitment-park"
    }
  ],
  "false_positive_fires": 0,
  "false_positive_n_good": 7,
  "false_positive_rate": 0.0,
  "format_note": "Catalog output_path is .md; G-1 _measure_one_delivered.py requires json.loads of that path. This file is the detector spec as JSON.",
  "good_fixture_ids": [
    "good-split-cover",
    "good-exact",
    "good-overcover",
    "good-redundant",
    "good-barely-above-baseline",
    "good-declared-noise",
    "good-dissent-covered"
  ],
  "markdown": "# CNL-0092 Missing expertise detection and the recruitment trigger\n\nA council notices a coverage hole by set difference, not by reading the\nconfidence of its votes. Required competencies are an explicit input on the\nquestion. A competency is covered only when some seated participant has a\nnon-empty evidence_record_id for it (CNL-0015) and a known-answer probe score\nstrictly above the pre-registered non-expert baseline (0.5). Declared tags,\nunanimous APPROVE, and 0.97 confidence do not cover.\n\nFire when required minus covered is non-empty, and name the uncovered\ncompetencies. Silence when the difference is empty. Detector-control: the\nplanted uncovered panel must fire before any silence is treated as absence.\n\nRecruitment trigger: for each named uncovered competency, seat a pool\ncandidate who meets the same evidence+score bar. Catch-up briefing includes\nthe question and filed evidence ids and MUST omit the standing majority\n(CNL-0020). The recruit must introduce at least one claim_id absent from the\npre-recruitment transcript; otherwise recruitment is cosmetic and a confident\nanswer remains forbidden. If the pool has no qualifying candidate, park; do\nnot answer.\n\nFalse-positive rate is a measured fraction on the known-good fixture family,\nnot an adjective.\n",
  "negative_control": {
    "check_behavior_verbatim": "negative_control: on planted_bad (uncovered CRYPTO+THREAT, unanimous confidence=True) detector fired=True named_uncovered=['crypto-protocol-design', 'threat-modeling'] confidence_clears_gap=False",
    "state_rejected": "planted uncovered roster with unanimous APPROVE at confidence 0.97 and declared CRYPTO on a product seat"
  },
  "pathology": {
    "description": "The seated roster produces a confident answer while at least one competency the question requires is covered by nobody: no seat has both an evidence_record_id and a known-answer score above the non-expert baseline for that competency.",
    "id": "missing-expertise-confident-wrong-answer",
    "why_confidence_is_not_coverage": "Generalist seats converge on a fluent answer with high confidence precisely when domain coverage is missing. Using vote confidence or unanimity as a coverage proxy is the pathology, not a detector."
  },
  "phase": "2C",
  "question": "How does a council notice that nobody present can answer the question, rather than confidently answering it wrongly - and what triggers recruitment?",
  "recruitment_results": {
    "cosmetic": {
      "actions": [
        "RECRUIT-COSMETIC"
      ],
      "confident_answer_allowed": false,
      "recruitment_cosmetic": true
    },
    "empty_pool": {
      "actions": [
        "PARK",
        "PARK"
      ],
      "confident_answer_allowed": false,
      "parked": true
    },
    "mutants": {
      "confidence_as_coverage_fires": false,
      "declared_as_coverage_fires": false,
      "honest_declared_only_fires": true,
      "honest_planted_fires": true
    },
    "pass": true,
    "qualified": {
      "actions": [
        "RECRUIT"
      ],
      "briefing_ok": true,
      "confident_answer_allowed": true,
      "coverage_closed": true,
      "novel_claim_ids": [
        "ticket-binding-must-cover-0-rtt",
        "rotation-needs-epoch-mac"
      ]
    },
    "unqualified_pool": {
      "actions": [
        "PARK",
        "PARK"
      ],
      "parked": true
    },
    "verbatim_park": "{\"actions\": [{\"action\": \"PARK\", \"competency\": \"crypto-protocol-design\", \"reason\": \"no-evidenced-pool-candidate\"}, {\"action\": \"PARK\", \"competency\": \"threat-modeling\", \"reason\": \"no-evidenced-pool-candidate\"}], \"confident_answer_allowed\": false}",
    "verbatim_qualified": "{\"actions\": [{\"action\": \"RECRUIT\", \"briefing\": {\"includes_question\": true, \"includes_standing_majority\": false}, \"competency\": \"crypto-protocol-design\", \"novel_claims\": [\"ticket-binding-must-cover-0-rtt\", \"rotation-needs-epoch-mac\"], \"seat\": \"recruited-cryptographer\"}], \"confident_answer_allowed\": true, \"novel_claim_ids\": [\"ticket-binding-must-cover-0-rtt\", \"rotation-needs-epoch-mac\"], \"post_named_uncovered\": []}"
  },
  "recruitment_trigger": {
    "catch_up_briefing_forbids": [
      "standing_majority_position"
    ],
    "catch_up_briefing_includes": [
      "question",
      "filed_evidence_ids",
      "prior_claim_ids"
    ],
    "cnl_0015": "declared expertise without evidence_record_id is not cover and is not recruitable",
    "cnl_0020": "newcomer briefing omits standing majority so the recruit cannot rubber-stamp it",
    "confident_answer_while_uncovered": false,
    "cosmetic_recruitment_closes_gap": false,
    "no_candidate": "PARK the decision; do not emit a confident answer",
    "novel_claim_required": true,
    "select": "first pool candidate with evidenced_competencies[C] and probe_scores[C] > baseline",
    "when": "detector fired; named_uncovered is the recruitment key"
  },
  "residual_unknowns": [
    "Required competencies are an explicit field on the question; extracting them from unstructured prose is out of scope and can hide a hole if the field is under-specified.",
    "Known-answer items and evidence_record_id issuance live in CNL-0015/IMP-0271; this unit consumes those records, it does not mint them.",
    "Cross-vendor human signature of the both-states control is not on this worktree; probe2 re-ran the control mechanically."
  ],
  "reviewer": {
    "independent": true,
    "kind": "mechanical-re-execution",
    "note": "Catalog asks for a cross-vendor reviewer who re-runs both-states. This delivery records an independent mechanical re-run of the same control in probe2, plus mutants that would pass if declared tags or unanimous confidence were treated as coverage. A second-vendor model signature is residual.",
    "re_ran_both_states": true,
    "reviewer_id": "CNL-0092-probe2-independent-both-states",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0092",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0092/probe1_both_states.py",
      "id": "probe1-both-states",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0092/probe2_recruitment.py",
      "id": "probe2-recruitment",
      "result": "PASS"
    }
  ],
  "title": "Missing expertise detection and the recruitment trigger",
  "ts": "2026-08-25T00:28:00Z",
  "unit_id": "CNL-0092"
}
