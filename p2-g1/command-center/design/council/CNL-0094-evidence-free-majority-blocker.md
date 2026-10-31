{
  "answers": {
    "evidence_free_majority_fate": "Votes that fail the attachment test are non-counting and do not enter the deciding tally. If a strict raw majority exists and every ballot in that majority is non-counting, the detector FIRE and the raw majority does not bind. The unique plurality of remaining counting ballots is the outcome (so an evidenced minority can win). If counting ballots are empty or tied, the outcome is NOT-BINDING. Recording an objection while still counting the unbacked votes is not this mechanism.",
    "minimum_evidence_attachment": "A vote counts if and only if it binds at least one evidence node that (1) is named in the council evidence_registry, (2) resolves to a file under the fixture root whose SHA-256 matches the registry digest, and (3) whose declared supports equals the ballot position. Empty evidence lists, unknown ids, missing files, digest mismatches, and support/position mismatches are non-counting. A citation string with no resolvable node is not an attachment."
  },
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0094-evidence-free-majority-blocker.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-detector-spec.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0094/artifact.schema.json",
      "role": "schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0094/detector.py",
      "role": "mechanism"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
      "role": "named-probe"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
      "role": "named-probe"
    }
  ],
  "both_states": {
    "bad_verbatim": {
      "council_id": "CNL-0094-planted-empty",
      "counting_tally": {
        "REJECT": 2
      },
      "fired": true,
      "n_counting": 2,
      "outcome": "REJECT",
      "pathology": "EVIDENCE-FREE-MAJORITY",
      "raw_tally": {
        "ADOPT": 7,
        "REJECT": 2
      },
      "silent": false
    },
    "clean_fixtures": [
      "known-good-majority",
      "known-good-unanimous",
      "known-good-mixed",
      "known-good-close"
    ],
    "fired_on_bad": true,
    "good_verbatim": {
      "council_id": "CNL-0094-known-good-majority",
      "counting_tally": {
        "ADOPT": 5,
        "REJECT": 2
      },
      "fired": false,
      "n_counting": 7,
      "outcome": "ADOPT",
      "pathology": null,
      "raw_tally": {
        "ADOPT": 5,
        "REJECT": 2
      },
      "silent": true
    },
    "known_good_id": "known-good-majority",
    "planted_bad_id": "planted-empty",
    "planted_variants_fired": [
      "CNL-0094-planted-empty",
      "CNL-0094-planted-fabricated",
      "CNL-0094-planted-digest",
      "CNL-0094-planted-support-mismatch"
    ],
    "silent_on_good": true
  },
  "catalog_dependency_note": "Catalog lists CNL-0068 as a dependency (evidence outranks popularity). This unit operationalizes the gate with executable fixtures; it does not wait on CNL-0068's missing design-note file.",
  "completion_sentinel": "SUCCESS:CNL-0094",
  "detector": {
    "fire_rule": "FIRE when unique raw majority has zero counting ballots; outcome is unique plurality of counting ballots else NOT-BINDING.",
    "id": "evidence-free-majority-blocker",
    "module_path": "command-center/p2-wave/probes/CNL-0094/detector.py",
    "signals": [
      {
        "id": "S1-resolvable-digest",
        "mechanism": "sha256(file) == evidence_registry[id].sha256",
        "what_it_measures": "Whether a cited evidence node actually exists and matches the registered bytes."
      },
      {
        "id": "S2-support-matches-position",
        "mechanism": "evidence_registry[id].supports == ballot.position",
        "what_it_measures": "Whether the resolved node actually supports the side the ballot voted for."
      }
    ]
  },
  "detector_control": {
    "known_present_found_before_absence": true,
    "order": [
      "planted-empty",
      "known-good-majority"
    ],
    "verbatim": "Ran planted-empty FIRST (fired=True pathology=EVIDENCE-FREE-MAJORITY outcome=REJECT) and only then known-good-majority (silent=True outcome=ADOPT). Known-present instance was found before any absence was reported."
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0094/detector.py:16",
      "claim": "Counting requires a resolvable digest-matched evidence node.",
      "mechanism": "live detect() on planted and clean fixtures",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:38996",
      "claim": "CNL-0094 asks for minimum attachment and evidence-free majority fate.",
      "mechanism": "catalog question_or_target exact substring",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:9908",
      "claim": "Spec 11198: agreement is not proof; evidence gates outrank popularity.",
      "mechanism": "catalog evidence_requirement citation",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0094/fixtures.py:planted_empty",
      "claim": "Unbacked 7-2 majority does not bind; backed REJECT plurality wins.",
      "mechanism": "planted-empty detect() outcome=REJECT fired=true",
      "verdict": "CONFIRMED"
    }
  ],
  "false_positive_rate": 0.0,
  "false_positive_rate_definition": "fires on clean fixtures / n_clean; measured 0/4 = 0.0",
  "fixtures": {
    "bad": {
      "expected_fired": true,
      "id": "planted-empty",
      "path": "command-center/p2-wave/probes/CNL-0094/fixtures/planted-empty"
    },
    "good": {
      "expected_fired": false,
      "id": "known-good-majority",
      "path": "command-center/p2-wave/probes/CNL-0094/fixtures/known-good-majority"
    }
  },
  "machine_checkable_property": "On a council snapshot, FIRE if and only if a unique strict raw majority position exists and the number of counting ballots for that position is zero. A ballot is counting iff at least one evidence_registry id resolves to an on-disk file whose SHA-256 matches the registry and whose supports equals the ballot position. False-positive rate on four clean fixtures is 0.0.",
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
      "id": "probe1"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
      "id": "probe2"
    }
  ],
  "negative_control": {
    "observed": "SILENT on known-good-majority evidenced 5-2 ADOPT; fired=False outcome=ADOPT",
    "rejects": "evidence-free majority (raw majority, zero counting ballots)",
    "verbatim": {
      "applied_to": "known-good-majority",
      "counting_tally": {
        "ADOPT": 5,
        "REJECT": 2
      },
      "fired": false,
      "id": "NC-EVIDENCED-MAJORITY",
      "note": "The check is meant to reject an evidence-free majority. On an evidenced 5-2 ADOPT majority it is SILENT and does not invert ordinary voting.",
      "outcome": "ADOPT",
      "raw_tally": {
        "ADOPT": 5,
        "REJECT": 2
      },
      "result": "SILENT",
      "silent": true
    }
  },
  "produced_at": "2026-08-25T00:44:16Z",
  "produced_by": {
    "role": "council-anti-failure-detector-designer",
    "unit_id": "CNL-0094"
  },
  "question": "What is the minimum evidence attachment for a vote to count, and what happens to a majority assembled entirely from votes that cite nothing?",
  "rejected_measures": [
    {
      "measure": "majority-headcount-only",
      "why_rejected": "Counts unbacked ballots as deciding votes, which is the pathology this detector exists to block."
    },
    {
      "measure": "citation-string-present",
      "why_rejected": "A fabricated or stale citation looks non-empty but does not resolve; treating it as evidence would pass ADV-0104."
    },
    {
      "measure": "record-objection-then-count-anyway",
      "why_rejected": "Annotating an evidence-free majority while still binding it implements nothing; the unbacked majority must not win."
    }
  ],
  "related_units": {
    "ADV-0104": "Adversarial sim: live engines currently CARRY an evidence-free majority. This unit specifies the blocker; it does not rebuild ADV-0104.",
    "CNL-0068": "Catalog dependency. Design-note file is absent on this worktree.",
    "IMP-0307": "Implementation receipt already blocks evidence-free majority and preserves a well-anchored minority. This detector spec matches that policy (FIRE + retally counting ballots)."
  },
  "reviewer": {
    "independent": true,
    "method": "probe2 recounts counting ballots via file sha256 vs registry without calling detector.detect, then re-runs planted and clean fixtures before signing",
    "reran_both_states": true,
    "reviewer_id": "CNL-0094-probe2-independent-recount",
    "verdict": "PASS"
  },
  "schema_notes": {
    "catalog_output_schema": "command-center/schema/council-detector-spec.schema.json",
    "discriminating_schema": "command-center/p2-wave/probes/CNL-0094/artifact.schema.json",
    "why_not_compile_catalog_shim": "The catalog schema is a generated $ref shim to https://ast-integrate.invalid/platform/schema/artifact-class-profiles.schema.json. Stock jsonschema 4.10.3 Draft7Validator fetches that URL (RefResolutionError). G-1 parses the artifact as JSON and does not require a receipt_core additionalProperties pass. Discrimination is the unit-local schema: garbage rejected, fired_on_bad=false rejected, machine_checkable_property required, false_positive_rate typed as a number."
  },
  "sentinel": "SUCCESS:CNL-0094",
  "spec_kind": "council-detector-spec",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
      "id": "T-PLANTED-EMPTY-FIRES",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
      "id": "T-KNOWN-GOOD-SILENT",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
      "id": "T-FABRICATED-AND-DIGEST-AND-SUPPORT",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
      "id": "T-INDEPENDENT-RECOUNT-AGREES",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe1_planted_bad.py",
      "id": "T-DETECTOR-CONTROL-KNOWN-PRESENT-FIRST",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0094/probe2_known_good.py",
      "id": "T-NEGATIVE-CONTROL-EVIDENCED-MAJORITY",
      "result": "PASS"
    }
  ],
  "title": "Evidence-free majority blocker",
  "unit_id": "CNL-0094"
}
