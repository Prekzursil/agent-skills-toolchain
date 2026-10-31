{
  "unit_id": "CNL-0032",
  "id": "CNL-0032",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0032",
  "completion_sentinel": "SUCCESS:CNL-0032",
  "title": "Proposer-critic-judge pipeline topology",
  "question": "In a strict pipeline where each stage sees only the previous stage's output, what information is structurally lost by the time the judge decides, and is that loss the point or a defect?",
  "answer": "In a strict proposer-critic-judge pipeline the judge's input is exactly the critic output body. Relative to a full-transcript judge on the same fixture that drops every token the critic did not copy forward. The loss is not uniformly a point or a defect: identity, rhetoric, and discarded alternatives are the isolation the topology buys (point-class); load-bearing question, claim, evidence, and constraint tokens that are omitted rather than explicitly rejected are uncontrolled silence (defect-class). On fixture pcj-run-drop the two signals agree that defect_lost is {CL-DROP, E1, Q1} and the mechanical rulings diverge (pipeline ACCEPT vs full-transcript REFUSE-INCOMPLETE). A faithful critic on the same proposal yields defect_lost empty, so pipeline structure does not force defect-class loss.",
  "claim_under_test": "Strict pipeline judge input structurally drops tokens absent from critic.output; point-class drop is isolation, defect-class omission is a defect unless the critic records an explicit rejection.",
  "topology": {
    "id": "proposer-critic-judge-strict-pipeline",
    "stages": [
      "proposer",
      "critic",
      "judge"
    ],
    "visibility_rule": "Each stage receives only the previous stage's output object, not the actor envelope and not earlier stages.",
    "judge_input_in_pipeline": "critic.output body only",
    "judge_input_full_transcript": "question + proposer envelope + critic envelope",
    "handoff_strips": [
      "actor identity",
      "unforwarded tokens"
    ]
  },
  "point_vs_defect": {
    "point_class": [
      "discarded_alternative",
      "identity",
      "rhetoric"
    ],
    "defect_class": [
      "claim",
      "constraint",
      "evidence",
      "question"
    ],
    "rule": "A strict pipeline MAY strip identity, rhetoric, and discarded alternatives at the critic->judge handoff; that loss is the point of isolation. A strict pipeline MUST NOT omit a load-bearing question, claim, evidence, or constraint token: omission is uncontrolled silence. Explicit rejection (token present with status=rejected) is the critic doing its job; silence is not."
  },
  "information_loss": {
    "fixture_id": "pcj-run-drop",
    "fixture_path": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json",
    "comparison": "pipeline_judge_input vs full_transcript_judge_input on the same fixture",
    "defect_lost_ids": [
      "CL-DROP",
      "E1",
      "Q1"
    ],
    "point_lost_ids": [
      "ALT-1",
      "CL-RHET",
      "critic-B",
      "proposer-A"
    ],
    "lost_ids": [
      "ALT-1",
      "CL-DROP",
      "CL-RHET",
      "E1",
      "Q1",
      "critic-B",
      "proposer-A"
    ],
    "full_ids": [
      "ALT-1",
      "CL-DROP",
      "CL-KEEP",
      "CL-RHET",
      "E1",
      "Q1",
      "critic-B",
      "proposer-A"
    ],
    "pipeline_ids": [
      "CL-KEEP"
    ],
    "signal1_token_sets": {
      "full_ids": [
        "ALT-1",
        "CL-DROP",
        "CL-KEEP",
        "CL-RHET",
        "E1",
        "Q1",
        "critic-B",
        "proposer-A"
      ],
      "pipeline_ids": [
        "CL-KEEP"
      ],
      "lost_ids": [
        "ALT-1",
        "CL-DROP",
        "CL-RHET",
        "E1",
        "Q1",
        "critic-B",
        "proposer-A"
      ],
      "defect_lost_ids": [
        "CL-DROP",
        "E1",
        "Q1"
      ],
      "point_lost_ids": [
        "ALT-1",
        "CL-RHET",
        "critic-B",
        "proposer-A"
      ]
    },
    "signal2_canonical_bytes": {
      "pipeline_sha256": "7ae005a3639f54c06c7f31e72cef776a13a7fa41b2ee85cc235f20b7b69f4872",
      "pipeline_bytes": 443,
      "full_sha256": "fd2437828a6d832b87624e5f48e1451fcfb57e8693a6d430a9ab185122d66d3c",
      "full_bytes": 1652,
      "sha256_match": false,
      "byte_delta": 1209
    },
    "rulings": {
      "required_defect_ids": [
        "CL-DROP",
        "CL-KEEP",
        "E1",
        "Q1"
      ],
      "pipeline_visible_defect_ids": [
        "CL-KEEP"
      ],
      "critic_present_ids": [
        "CL-KEEP",
        "KP-1"
      ],
      "unaddressed_required_ids": [
        "CL-DROP",
        "E1",
        "Q1"
      ],
      "pipeline_verdict": "ACCEPT",
      "full_transcript_verdict": "REFUSE-INCOMPLETE",
      "verdicts_diverge": true
    },
    "faithful_pipeline": {
      "defect_lost_ids": [],
      "point_lost_ids": [
        "ALT-1",
        "CL-RHET",
        "critic-B",
        "proposer-A"
      ],
      "verdicts_diverge": false
    },
    "explicit_reject_pipeline": {
      "defect_lost_ids": [],
      "point_lost_ids": [
        "ALT-1",
        "CL-RHET",
        "critic-B",
        "proposer-A"
      ],
      "verdicts_diverge": false
    }
  },
  "claims": [
    {
      "id": "C1",
      "claim": "Pipeline judge input is a proper subset of full-transcript tokens on pcj-run-drop.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:measure"
    },
    {
      "id": "C2",
      "claim": "Lost load-bearing tokens are CL-DROP, E1, and Q1 (defect-class omission).",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json"
    },
    {
      "id": "C3",
      "claim": "Identity/rhetoric/workshop tokens are also lost; that class is the point of isolation.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:partition_rule"
    },
    {
      "id": "C4",
      "claim": "All pipeline information loss is the point of the topology.",
      "verdict": "REFUTED",
      "anchor": "defect_lost_ids on planted-drop plus ruling divergence"
    },
    {
      "id": "C5",
      "claim": "All pipeline information loss is a defect.",
      "verdict": "REFUTED",
      "anchor": "faithful critic: defect_lost empty while point_lost remains"
    }
  ],
  "evidence": [
    {
      "claim": "Token-id set algebra (signal 1) reports non-empty defect_lost on the drop fixture.",
      "verdict": "CONFIRMED",
      "mechanism": "python set difference on walked token ids",
      "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:token_loss",
      "observed": {
        "full_ids": [
          "ALT-1",
          "CL-DROP",
          "CL-KEEP",
          "CL-RHET",
          "E1",
          "Q1",
          "critic-B",
          "proposer-A"
        ],
        "pipeline_ids": [
          "CL-KEEP"
        ],
        "lost_ids": [
          "ALT-1",
          "CL-DROP",
          "CL-RHET",
          "E1",
          "Q1",
          "critic-B",
          "proposer-A"
        ],
        "defect_lost_ids": [
          "CL-DROP",
          "E1",
          "Q1"
        ],
        "point_lost_ids": [
          "ALT-1",
          "CL-RHET",
          "critic-B",
          "proposer-A"
        ]
      }
    },
    {
      "claim": "Canonical JSON sha256 and byte-length (signal 2) differ for the two judge inputs.",
      "verdict": "CONFIRMED",
      "mechanism": "sha256 and len of sort_keys canonical JSON bytes",
      "anchor": "command-center/p2-wave/probes/CNL-0032/pipeline.py:digest_pair",
      "observed": {
        "pipeline_sha256": "7ae005a3639f54c06c7f31e72cef776a13a7fa41b2ee85cc235f20b7b69f4872",
        "pipeline_bytes": 443,
        "full_sha256": "fd2437828a6d832b87624e5f48e1451fcfb57e8693a6d430a9ab185122d66d3c",
        "full_bytes": 1652,
        "sha256_match": false,
        "byte_delta": 1209
      }
    }
  ],
  "tests": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0032/probe1_info_loss.py",
      "result": "NOT-RUN",
      "role": "information-loss measurement"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0032/probe2_negative_control.py",
      "result": "NOT-RUN",
      "role": "negative control both-states"
    }
  ],
  "negative_control": {
    "rejects": "a pipeline critic that omits a load-bearing token (CL-DROP, E1, Q1) without an explicit rejection record",
    "planted_bad": "pcj-run-drop",
    "known_good": [
      "faithful-forward critic",
      "explicit-reject critic",
      "full-transcript judge"
    ],
    "fired_on_drop": true,
    "silent_on_faithful": true,
    "silent_on_explicit_reject": true,
    "silent_on_full_context": true,
    "verbatim": "NEGATIVE CONTROL: the defect-omission check is meant to REJECT a pipeline critic that omits a load-bearing token (CL-DROP, E1, Q1) without an explicit rejection record. On that planted-drop state it FIRES. On a faithful-forward critic, on an explicit-reject critic, and on a full-transcript judge it is SILENT for defect-class loss."
  },
  "reviewer": {
    "reviewer_id": "CNL-0032-probe2-negative-control",
    "verdict": "PASS",
    "independent": true,
    "scope_not_agreement": true,
    "counterexample": "Faithful-forward critic on the same proposal: defect_lost=[], point_lost non-empty, verdicts_diverge=false. This instance refutes both 'all loss is the point' (drop fixture diverges) and 'all loss is a defect' (faithful keeps isolation)."
  },
  "inputs_on_this_tree": {
    "command-center/schema/council-design-note.schema.json": true,
    "command-center/design/council/CNL-0027-proposer-critic-and-synthesiser-triad-mandates.md": false,
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json": true
  },
  "schema_note": "Catalog output_schema command-center/schema/council-design-note.schema.json is absent on this worktree. This note is JSON-parseable with state=SUCCESS. No ADV rebuild of that schema was attempted.",
  "dependency_note": "CNL-0027 (proposer-critic-synthesiser triad mandates) artifact is absent; this unit measures pipeline topology on a local fixture rather than citing an unread dependency note.",
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0032-proposer-critic-judge-pipeline-topology.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0032/fixtures/pcj-run.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0032/pipeline.py",
      "exists": true,
      "role": "supporting"
    }
  ],
  "ts": "2026-08-25T00:52:38Z"
}
