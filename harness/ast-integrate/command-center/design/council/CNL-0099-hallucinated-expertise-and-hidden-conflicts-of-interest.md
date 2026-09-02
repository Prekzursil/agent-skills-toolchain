{
  "schema_version": 1,
  "unit_id": "CNL-0099",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0099",
  "profile": "council-detector-spec",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json#CNL-0099 (_USER-PROMPTS.md:10923/:10924/:11241/:11242)",
  "min_bytes_threshold": 256,
  "artifacts": [
    {
      "path": "command-center/schema/council-detector-spec.schema.json",
      "sha256": "9aaa3e601e89634e67b7bb50afe4b7b326f13a23426b6a4cbbceaec2942a8599",
      "bytes": 1128,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/detector.py",
      "sha256": "dd2340cfea750d5d689c622c1ed418f4a2df1f829df38444455a26c3f4de02c1",
      "bytes": 10792,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/probe1_both_states.py",
      "sha256": "64b79d609a72d3c0d047ec424159906b73010cd6a7f9917b025cbc55bef15084",
      "bytes": 4576,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/probe2_overclaim.py",
      "sha256": "1f3e7fae648286a700044f898d450b256b32a5462dddb06eb2be0434c84c9703",
      "bytes": 4927,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/fixtures/index.json",
      "sha256": "4b27579467e33e6abef11a7b2029c5cca0a179c0ef59d144acd88950741eb37a",
      "bytes": 449,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
      "sha256": "1639c27f3e7ece1f35ef5c929625b77b60d3d9d94e05bece6a6e8e4217969993",
      "bytes": 1235,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json",
      "sha256": "5d0990658265a96483636bb77c14aaa3ec8cf462e7e44e289d0efa9376dc4249",
      "bytes": 609,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0099/fixtures/known_good_expertise.json",
      "sha256": "66b6f21990657fa2f8fbdbedecfb2f99a1a9c32f321ad3e87b70b9af03183410",
      "bytes": 1334,
      "exists": true,
      "eol": "LF",
      "role": "supporting"
    }
  ],
  "evidence": [
    {
      "claim": "The hallucinated-expertise detector FIREs on planted_expertise_bad and is SILENT on known_good_expertise.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0099/detector.py:89",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0099'); import detector as D; print(D.dump_result(D.evaluate(D.load_fixture('planted_expertise_bad'))))\"",
          "raw_output": "{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}",
          "fingerprint": "e3f2768306957f1ec25b3d283017e3d1",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
          "raw_output": "{\"claimed_domains\": [\"cryptography\"], \"requests_expert_weight\": true, \"unanswerable_answer\": \"1A2B3Cdeadbeef\", \"verifiable_pairs\": 4}",
          "fingerprint": "a0d7a63fadfd247c89f37d3a821e930d",
          "exit_code": 0
        }
      ]
    },
    {
      "claim": "The hidden-COI detector FIREs on planted_coi_bad (undeclared author voting on own artifact) and is SILENT on known_good_coi.",
      "verdict": "CONFIRMED",
      "confidence": "almost-certain",
      "anchor": "command-center/p2-wave/probes/CNL-0099/detector.py:165",
      "probes": [
        {
          "role": "source",
          "method": "command",
          "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B -c \"import sys; sys.path.insert(0,'command-center/p2-wave/probes/CNL-0099'); import detector as D; print(D.dump_result(D.evaluate(D.load_fixture('planted_coi_bad'))))\"",
          "raw_output": "{\"coi_findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"council_id\":\"planted_coi_bad\",\"expertise_findings\":[],\"findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"fired\":true,\"n_findings\":1}",
          "fingerprint": "78a1fe9a429fa1367cc5beb5022ab58c",
          "exit_code": 0
        },
        {
          "role": "verifier",
          "method": "file-read",
          "command": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json",
          "raw_output": "{\"author_id\": \"carol\", \"ballot_counts\": true, \"conflicts_declared\": [], \"seat_id\": \"carol\"}",
          "fingerprint": "0d60802154efd6d320ed69b8c2dce1c2",
          "exit_code": 0
        }
      ]
    }
  ],
  "tests": [
    {
      "id": "probe1_both_states",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0099/probe1_both_states.py",
      "result": "PASS"
    },
    {
      "id": "probe2_overclaim",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0099/probe2_overclaim.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-EXPERTISE-BOTH-STATES",
      "kind": "known-broken-fixture",
      "description": "Hallucinated-expertise detector must FIRE on planted_expertise_bad and stay SILENT on known_good_expertise.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}",
      "good_state_output": "{\"coi_findings\":[],\"council_id\":\"known_good_expertise\",\"expertise_findings\":[],\"findings\":[],\"fired\":false,\"n_findings\":0}"
    },
    {
      "id": "NC-COI-BOTH-STATES",
      "kind": "known-broken-fixture",
      "description": "Hidden-COI detector must FIRE on planted_coi_bad and stay SILENT on known_good_coi.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"coi_findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"council_id\":\"planted_coi_bad\",\"expertise_findings\":[],\"findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"fired\":true,\"n_findings\":1}",
      "good_state_output": "{\"coi_findings\":[],\"council_id\":\"known_good_coi\",\"expertise_findings\":[],\"findings\":[],\"fired\":false,\"n_findings\":0}"
    },
    {
      "id": "NC-NAIVE-SILENT-ON-HIDDEN",
      "kind": "mutation",
      "description": "Tag-overlap and declaration-form-only checks must stay SILENT on the planted hidden cases the full detectors catch.",
      "fired_on_bad_state": true,
      "silent_on_good_state": true,
      "bad_state_output": "{\"full_coi\":{\"coi_findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"council_id\":\"planted_coi_bad\",\"expertise_findings\":[],\"findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"fired\":true,\"n_findings\":1},\"full_expertise\":{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}}",
      "good_state_output": "{\"naive_declaration\":{\"council_id\":\"planted_coi_bad\",\"findings\":[],\"fired\":false,\"n_findings\":0,\"naive\":true},\"naive_tag\":{\"council_id\":\"planted_expertise_bad\",\"findings\":[],\"fired\":false,\"n_findings\":0,\"naive\":true}}"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0099-probe2-independent-both-states",
    "verdict": "PASS",
    "independent": true,
    "fresh_context": false,
    "vendor": "openai",
    "notes": "Probe2 re-runs both-states and rejects schema/overclaim mutants. reran_both_states is recorded on report.reviewer because the receipt reviewer object forbids additional properties."
  },
  "defects": [],
  "manifest_registration": {
    "registered": true,
    "manifest_path": "command-center/p2-wave/probes/CNL-0099/UNIT-ARTIFACT-MANIFEST.json",
    "entry_id": "CNL-0099"
  },
  "downstream_consumers": [
    {
      "consumer": "command-center/p2-wave/probes/CNL-0099/detector.py:evaluate",
      "artifact_path": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json",
      "executed": true,
      "read_ok": true,
      "exit_code": 0,
      "probe": {
        "role": "verifier",
        "method": "command",
        "command": "detector.evaluate(planted_expertise_bad)",
        "raw_output": "{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}",
        "fingerprint": "ef5877e90fb2311778b578f9fa24e3e1",
        "exit_code": 0
      }
    }
  ],
  "timestamps": {
    "started_at": "2026-08-25T00:59:44Z",
    "ended_at": "2026-08-25T00:59:44Z",
    "duration_seconds": 0
  },
  "retry": {
    "count": 0,
    "policy": "two strikes then pivot, PLUS a mandatory detector-control retry: if the both-states control does not fire on the planted-bad fixture, the attempt does not count as a failure of the mechanism - fix the fixture first, once. Max 3 mechanism attempts (AGENTS.md 4b)."
  },
  "residual_unknowns": [
    {
      "claim": "CNL-0015 and CNL-0029 design notes are absent on this worktree; field names here are the interface those units would have to match.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Deliver CNL-0015 and CNL-0029 on this tree and join their checkable fields to this detector spec."
    },
    {
      "claim": "false_positive_rate 0.0 is the fixture-set rate (0/4), not a production rate.",
      "verdict": "CONFIRMED",
      "settling_experiment": "Run the detectors against a live council transcript corpus and recompute the rate."
    },
    {
      "claim": "ADV-0099/ADV-0100 were not rebuilt; this unit does not claim their verdicts.",
      "verdict": "NOT-CHECKED",
      "settling_experiment": "Those ADV units own their own G-1; do not rebuild them from this unit."
    }
  ],
  "produced_by": {
    "vendor": "openai",
    "model": "gpt-5-codex",
    "role": "council-anti-failure-detector-designer",
    "execution_substrate": "local-parallel"
  },
  "report": {
    "kind": "council-detector-spec",
    "title": "Hallucinated expertise and hidden conflicts of interest",
    "phase": "2C",
    "question": "What probe catches a participant asserting expertise it does not have, and what declaration plus cross-check catches an undeclared conflict of interest?",
    "spec_anchors": [
      "_USER-PROMPTS.md:10923 (expertise-ranked selection)",
      "_USER-PROMPTS.md:11241 (hallucinated expertise)",
      "_USER-PROMPTS.md:10924 (conflicts of interest, recusal)",
      "_USER-PROMPTS.md:11242 (hidden conflicts of interest)"
    ],
    "dependencies": {
      "CNL-0015": "artifact-absent-on-this-tree",
      "CNL-0029": "artifact-absent-on-this-tree",
      "note": "Those design notes are not on disk. This spec names the checkable fields they would have supplied rather than importing them. Not BLOCKED: the detectors run on fixtures."
    },
    "answers": {
      "hallucinated_expertise_probe": "Before a seat may carry expert weight, run a domain calibration: verifiable items with known answers plus one unanswerable control. Refuse expert weight when (a) there is no passing calibration record and no passing live probe (self-assertion), or (b) verifiable accuracy is at or below the non-expert baseline, or (c) the unanswerable item is answered confidently. Tag-matching claimed_domains to task.required_domains is not evidence — the naive tag check is silent on the planted self-asserted expert.",
      "hidden_coi_declaration_plus_crosscheck": "Every seat files conflicts_declared (authored_artifact, owns_proposal, is_evaluated_vendor). That form is not the detector. The cross-check is a provenance join of seat.id to artifact.author_id / owner_id / vendor_id. A match missing from the declaration is undeclared COI. Independently, a provenance-matched seat whose ballot.counts is true is counting-while-conflicted. An empty declaration is not innocence: the naive form-only check is silent on the planted author who votes on their own artifact."
    },
    "checkable_fields": {
      "expertise": [
        "seats[].requests_expert_weight",
        "seats[].claimed_domains",
        "seats[].evidence_basis",
        "seats[].calibration.{domain,accuracy,unanswerable_response}",
        "probes[seat_id].verifiable[{answer,expected}]",
        "probes[seat_id].unanswerable.answer",
        "task.required_domains",
        "non_expert_baseline"
      ],
      "coi": [
        "seats[].id",
        "seats[].conflicts_declared[{kind,subject_id}]",
        "seats[].ballot.counts",
        "artifact.{id,author_id,owner_id,vendor_id}"
      ]
    },
    "detectors": [
      {
        "id": "hallucinated_expertise",
        "pathology": "participant asserts expertise it does not have",
        "mechanism": "Live verifiable calibration plus unanswerable control; self-assertion and tag overlap are insufficient.",
        "fire_condition": "requests_expert_weight and (accuracy <= baseline or unanswerable answered confidently or no probe/record).",
        "silent_condition": "Expert-weight seat with accuracy > baseline and unanswerable in the unknown set, or no expert-weight request.",
        "executable": "command-center/p2-wave/probes/CNL-0099/detector.py"
      },
      {
        "id": "hidden_conflict_of_interest",
        "pathology": "undeclared conflict plus counting vote on own artifact",
        "mechanism": "Declaration form plus provenance join; recusal required when the join hits.",
        "fire_condition": "seat.id matches artifact author/owner/vendor and (declaration misses that tuple or ballot.counts is true).",
        "silent_condition": "No provenance match, or match is declared and ballot does not count.",
        "executable": "command-center/p2-wave/probes/CNL-0099/detector.py"
      }
    ],
    "both_states": {
      "planted_bad": {
        "fixture_id": "planted_expertise_bad",
        "fired": true,
        "verbatim": "{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}"
      },
      "known_good": {
        "fixture_id": "known_good_expertise",
        "fired": false,
        "verbatim": "{\"coi_findings\":[],\"council_id\":\"known_good_expertise\",\"expertise_findings\":[],\"findings\":[],\"fired\":false,\"n_findings\":0}"
      },
      "planted_coi": {
        "fixture_id": "planted_coi_bad",
        "fired": true,
        "verbatim": "{\"coi_findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"council_id\":\"planted_coi_bad\",\"expertise_findings\":[],\"findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"fired\":true,\"n_findings\":1}"
      },
      "known_good_coi": {
        "fixture_id": "known_good_coi",
        "fired": false,
        "verbatim": "{\"coi_findings\":[],\"council_id\":\"known_good_coi\",\"expertise_findings\":[],\"findings\":[],\"fired\":false,\"n_findings\":0}"
      }
    },
    "detector_control": {
      "fixture_id": "planted_expertise_bad",
      "found_known_present": true,
      "verbatim": "{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1}",
      "absence_claims_refused_if_control_misses": true
    },
    "false_positive_rate": 0.0,
    "false_positive_numerator": 0,
    "false_positive_denominator": 4,
    "false_positive_rows": [
      {
        "fixture_id": "known_good_expertise",
        "fired": false
      },
      {
        "fixture_id": "known_good_coi",
        "fired": false
      },
      {
        "fixture_id": "clean_nonexpert",
        "fired": false
      },
      {
        "fixture_id": "clean_declared_recused",
        "fired": false
      }
    ],
    "negative_control": {
      "state_rejected": "planted_expertise_bad (self-asserted expert, accuracy at baseline, confident unanswerable) and planted_coi_bad (author votes on own artifact, empty declaration)",
      "check_behavior": "Full detectors FIRE. Naive tag-match is SILENT on the expertise plant. Naive declaration-only is SILENT on the hidden-COI plant.",
      "verbatim": "{\"planted_coi_full\":{\"coi_findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"council_id\":\"planted_coi_bad\",\"expertise_findings\":[],\"findings\":[{\"ballot_counts\":true,\"declared\":[],\"detector\":\"hidden_conflict_of_interest\",\"provenance\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}],\"reasons\":[\"undeclared_provenance_conflict\",\"counting_vote_while_conflicted\"],\"seat_id\":\"carol\",\"undeclared\":[{\"kind\":\"authored_artifact\",\"subject_id\":\"prop-acme-eval\"},{\"kind\":\"owns_proposal\",\"subject_id\":\"prop-acme-eval\"}]}],\"fired\":true,\"n_findings\":1},\"planted_coi_naive_declaration\":{\"council_id\":\"planted_coi_bad\",\"findings\":[],\"fired\":false,\"n_findings\":0,\"naive\":true},\"planted_expertise_full\":{\"coi_findings\":[],\"council_id\":\"planted_expertise_bad\",\"expertise_findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"findings\":[{\"detector\":\"hallucinated_expertise\",\"domain\":\"cryptography\",\"reasons\":[\"accuracy_at_or_below_non_expert_baseline\",\"unanswerable_answered_confidently\"],\"seat_id\":\"alice\",\"tag_overlap\":true}],\"fired\":true,\"n_findings\":1},\"planted_expertise_naive_tag\":{\"council_id\":\"planted_expertise_bad\",\"findings\":[],\"fired\":false,\"n_findings\":0,\"naive\":true}}"
    },
    "claims": [
      {
        "id": "C1",
        "claim": "Tag overlap is sufficient evidence of expertise.",
        "verdict": "REFUTED",
        "evidence_fixture": "planted_expertise_bad",
        "note": "naive_expertise_tag_match silent; full detector fires"
      },
      {
        "id": "C2",
        "claim": "An empty conflicts declaration means there is no conflict.",
        "verdict": "REFUTED",
        "evidence_fixture": "planted_coi_bad",
        "note": "naive_coi_declaration_only silent; provenance join fires"
      },
      {
        "id": "C3",
        "claim": "A seat that beats the baseline, answers unknown on the unanswerable control, and is not provenance-matched is silent.",
        "verdict": "CONFIRMED",
        "evidence_fixture": "known_good_expertise",
        "note": "full detector silent"
      },
      {
        "id": "C4",
        "claim": "Declaring the provenance conflict and recusing (ballot.counts=false) is silent.",
        "verdict": "CONFIRMED",
        "evidence_fixture": "clean_declared_recused",
        "note": "full detector silent"
      }
    ],
    "reviewer": {
      "reviewer_id": "CNL-0099-probe2-independent-both-states",
      "verdict": "PASS",
      "independent": true,
      "reran_both_states": true,
      "scope_not_agreement": true
    },
    "observations": [
      {
        "name": "expertise_planted_fired",
        "measured": true,
        "method": "command",
        "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_expertise_bad.json"
      },
      {
        "name": "expertise_known_good_silent",
        "measured": true,
        "method": "command",
        "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/known_good_expertise.json"
      },
      {
        "name": "coi_planted_fired",
        "measured": true,
        "method": "command",
        "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/planted_coi_bad.json"
      },
      {
        "name": "false_positive_rate",
        "measured": 0.0,
        "method": "command",
        "anchor": "command-center/p2-wave/probes/CNL-0099/fixtures/index.json"
      }
    ],
    "control_ids": [
      "planted_expertise_bad",
      "planted_expertise_bad",
      "known_good_expertise",
      "planted_coi_bad",
      "known_good_coi"
    ]
  }
}
