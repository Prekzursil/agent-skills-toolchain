{
  "unit_id": "CNL-0034",
  "kind": "council-design-note",
  "report_kind": "council-design-note",
  "state": "SUCCESS",
  "schema_version": 1,
  "title": "Jury topology: deciders who did not argue",
  "question": "What must a jury see and NOT see, who controls what evidence reaches it, and what stops the evidence-presenter from becoming the real decision-maker?",
  "sentinel": "SUCCESS:CNL-0034",
  "completion_sentinel": "SUCCESS:CNL-0034",
  "answer": "A jury is a set of deciders who did not argue. They must see the charge (question plus standard of proof), the decision rule (majority here; hung is representable), party claims labeled as advocacy, and the complete sealed admitted-evidence packet. They must not see excluded items, the presenter's recommended verdict, presenter-private withheld admitted items, the judge's merits view, or other jurors' unrecorded first-pass ballots. The presenter proposes; a counterparty may object; a gatekeeper who does not vote admits and seals. The presenter does not vote. Presenter capture is diagnosed by holding pool and juror functions fixed and varying only the forwarded subset: without the seal, one-sided forwarding flips majority CLAIMANT->RESPONDENT with L1=5 and unequal packet digests (the presenter decides). With the completeness seal, the same variation yields L1=0, equal digests, and completeness against the admitted set (the jury decides on the admitted packet). Signal 1 is the majority tally; signal 2 is sha256 of packet membership ids. Windows harness files and dependency artifacts CNL-0006/CNL-0026 are absent on this tree; the executable model is the live contract. SUCCESS:CNL-0034",
  "claim_under_test": "If the presenter can choose a proper subset of admitted evidence as the jury packet, the verdict tracks the presenter, not the admitted record. A completeness seal plus presenter-out-of-vote removes that capture.",
  "topology": {
    "name": "jury-deciders-who-did-not-argue",
    "roles": [
      {
        "id": "presenter",
        "argues": true,
        "votes": false,
        "controls_seal": false,
        "may": "propose a packet and argue from it"
      },
      {
        "id": "counterparty",
        "argues": true,
        "votes": false,
        "controls_seal": false,
        "may": "object to proposed items"
      },
      {
        "id": "gatekeeper",
        "argues": false,
        "votes": false,
        "controls_seal": true,
        "may": "admit or exclude under a rule, then seal the packet"
      },
      {
        "id": "judge",
        "argues": false,
        "votes": false,
        "controls_seal": false,
        "may": "charge the jury and rule procedure; not a merits vote (CNL-0026)"
      },
      {
        "id": "juror",
        "argues": false,
        "votes": true,
        "controls_seal": false,
        "may": "see the sealed packet and the charge; vote independently first"
      }
    ],
    "must_see": [
      "charge: question plus standard of proof",
      "complete sealed admitted-evidence packet",
      "party claims labeled as advocacy, not as facts",
      "decision rule, including that hung is representable"
    ],
    "must_not_see": [
      "excluded evidence",
      "presenter's recommended verdict",
      "admitted items the presenter withheld (illegal; the seal forbids it)",
      "judge or gatekeeper merits opinion",
      "other jurors' unrecorded first-pass ballots"
    ],
    "evidence_control": {
      "proposes": "presenter",
      "objects": "counterparty",
      "admits_and_seals": "gatekeeper",
      "consumes": "jury",
      "invariant": "sealed packet equals every admitted item; presenter cannot drop or add"
    },
    "presenter_capture_resistance": {
      "completeness_seal": "sha256(sealed ids) == sha256(admitted ids); presenter subset is not an input to seal_admitted_packet",
      "presenter_out_of_vote": "presenter.votes is false",
      "gatekeeper_probe": "vary only forwarded subset; large movement without seal is capture; zero movement with seal is the required topology"
    }
  },
  "mechanism": {
    "signals": [
      {
        "id": "signal-1-majority-tally",
        "reads": "categorical majority of five juror votes"
      },
      {
        "id": "signal-2-packet-digest",
        "reads": "sha256 of sorted evidence ids (not the vote vector)"
      }
    ],
    "large_movement": "majority_flipped OR L1 >= 3 (ceil(n_jurors/2)); planted-bad measures majority_flipped=true and L1=5",
    "seal": "seal_admitted_packet ignores proposed and emits every admitted item"
  },
  "both_states": {
    "fired_on_bad": true,
    "silent_on_good": true,
    "good_verbatim": "{\"completeness_a\": true, \"completeness_b\": true, \"digest_equal\": true, \"fired\": false, \"l1\": 0, \"majority_flipped\": false, \"silent\": true}",
    "bad_verbatim": "{\"completeness_a\": false, \"completeness_b\": false, \"digest_equal\": false, \"fired\": true, \"l1\": 5, \"majority_flipped\": true, \"silent\": false}"
  },
  "negative_control": {
    "id": "NC-PRESENTER-CAPTURE-ONE-SIDED-FORWARD",
    "on_state": "planted-bad: gatekeeper off; presenter A forwards E1-E3 (claimant-only); presenter B forwards E4-E6 (respondent-only); same pool and same five jurors",
    "rejects": "a jury that receives only the presenter's forwarded subset so that swapping presenters swaps the verdict",
    "observed": "fired=True majority_flipped=True l1=5 digest_equal=False on planted-bad; silent=True l1=0 digest_equal=True on known-good",
    "verbatim": "{\"digest_equal\": false, \"fired\": true, \"fixture\": \"planted-bad-presenter-capture\", \"l1\": 5, \"majority_a\": \"CLAIMANT\", \"majority_b\": \"RESPONDENT\", \"majority_flipped\": true, \"presenter_capture\": true, \"silent\": false}",
    "does_on_reject_state": "The check FIRES; majority flips; L1=5; packet digests differ; presenter_capture=true. It does not return silent."
  },
  "negative_controls": [
    {
      "id": "NC-PRESENTER-CAPTURE-ONE-SIDED-FORWARD",
      "on_state": "planted-bad: gatekeeper off; presenter A forwards E1-E3 (claimant-only); presenter B forwards E4-E6 (respondent-only); same pool and same five jurors",
      "rejects": "a jury that receives only the presenter's forwarded subset so that swapping presenters swaps the verdict",
      "observed": "fired=True majority_flipped=True l1=5 digest_equal=False on planted-bad; silent=True l1=0 digest_equal=True on known-good",
      "verbatim": "{\"digest_equal\": false, \"fired\": true, \"fixture\": \"planted-bad-presenter-capture\", \"l1\": 5, \"majority_a\": \"CLAIMANT\", \"majority_b\": \"RESPONDENT\", \"majority_flipped\": true, \"presenter_capture\": true, \"silent\": false}",
      "does_on_reject_state": "The check FIRES; majority flips; L1=5; packet digests differ; presenter_capture=true. It does not return silent."
    }
  ],
  "tests": [
    {
      "id": "gatekeeper-probe",
      "name": "vary only what the presenter forwards; measure verdict movement",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0034/probe1_gatekeeper.py",
      "result": "PASS",
      "verbatim": "bad_flip=True bad_l1=5 bad_digest_equal=False capture=True good_l1=0 good_digest_equal=True good_silent=True\nSUCCESS:CNL-0034-probe1 gatekeeper: large movement without seal, zero with seal"
    },
    {
      "id": "both-states",
      "name": "check FIRES on planted-bad and is SILENT on known-good",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0034/probe2_negative_control.py",
      "result": "PASS",
      "verbatim": "BOTH-STATES-GOOD {\"completeness_a\": true, \"completeness_b\": true, \"digest_equal\": true, \"fired\": false, \"l1\": 0, \"majority_flipped\": false, \"silent\": true}\nBOTH-STATES-BAD {\"completeness_a\": false, \"completeness_b\": false, \"digest_equal\": false, \"fired\": true, \"l1\": 5, \"majority_flipped\": true, \"silent\": false}\nNEGATIVE-CONTROL {\"digest_equal\": false, \"fired\": true, \"fixture\": \"planted-bad-presenter-capture\", \"l1\": 5, \"majority_a\": \"CLAIMANT\", \"majority_b\": \"RESPONDENT\", \"majority_flipped\": true, \"presenter_capture\": true, \"silent\": false}\nfired_on_bad=True silent_on_good=True\nSUCCESS:CNL-0034-probe2 both-states and negative control"
    },
    {
      "id": "negative-control",
      "name": "recorded verbatim: what the check does on the reject state",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0034/probe2_negative_control.py",
      "result": "PASS",
      "verbatim": "{\"digest_equal\": false, \"fired\": true, \"fixture\": \"planted-bad-presenter-capture\", \"l1\": 5, \"majority_a\": \"CLAIMANT\", \"majority_b\": \"RESPONDENT\", \"majority_flipped\": true, \"presenter_capture\": true, \"silent\": false}"
    }
  ],
  "evidence": [
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35982,
      "snippet": "\"question_or_target\": \"What must a jury see and NOT see, who controls what evidence reaches it, and what stops the evidence-presenter from becoming the real decision-maker?\",",
      "kind": "catalog-question",
      "claim": "CNL-0034 question_or_target is the jury see/not-see and presenter-capture question.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35982",
      "mechanism": "file:line snippet match on this worktree"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35986,
      "snippet": "\"a gatekeeper probe: vary only what the presenter forwards and measure how much the verdict moves; a large movement means the presenter, not the jury, decides\",",
      "kind": "catalog-gatekeeper-test",
      "claim": "Catalog tests_required names the gatekeeper probe that this unit executes.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35986",
      "mechanism": "file:line snippet match on this worktree"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0034/jury_model.py",
      "line": 30,
      "snippet": "SEAL_INVARIANT = \"sealed packet equals every admitted item; presenter cannot drop or add\"",
      "kind": "live-seal-invariant",
      "claim": "The completeness seal ignores the presenter's subset and emits every admitted item.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0034/jury_model.py:30",
      "mechanism": "file:line snippet match on this worktree"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0034/jury_model.py",
      "line": 167,
      "snippet": "\"\"\"Vary only what the presenter forwards. Measure verdict movement.\"\"\"",
      "kind": "live-gatekeeper-probe",
      "claim": "The model varies only forwarded membership; pool and juror functions stay fixed.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0034/jury_model.py:167",
      "mechanism": "file:line snippet match on this worktree"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35600,
      "snippet": "\"title\": \"Judge and juror separation to remove the single epistemic point of failure\",",
      "kind": "dependency-CNL-0026-title",
      "claim": "Catalog names CNL-0026 as judge/juror separation; this topology keeps judge and presenter out of the vote.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35600",
      "mechanism": "file:line snippet match on this worktree"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 34607,
      "snippet": "\"title\": \"Information-partition lattice: who may see what, when\",",
      "kind": "dependency-CNL-0006-title",
      "claim": "Catalog names CNL-0006 as the partition lattice; jury-see vs jury-must-not-see are two cells of that lattice.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:34607",
      "mechanism": "file:line snippet match on this worktree"
    }
  ],
  "regression_anchor": {
    "catalog_question": "What must a jury see and NOT see, who controls what evidence reaches it, and what stops the evidence-presenter from becoming the real decision-maker?",
    "harness_inputs_absent": {
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": true,
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": true,
      "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": true,
      "_USER-PROMPTS.md@repo-root": true,
      "CNL-0006-artifact": true,
      "CNL-0026-artifact": true
    },
    "note": "Catalog inputs point at Windows harness-restore paths that are not on this Linux worktree. Design is grounded in the catalog question plus the executable gatekeeper probe, not in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json records."
  },
  "scope": {
    "executable_on": "in-probe jury_model.py with a 6-item pool and 5 jurors; not a live council runtime (tools/council absent)",
    "does_not_claim": [
      "cloud ok=true is delivery",
      "global unit_manifest.py --write was run",
      "Windows harness-restore files were read on this host",
      "CNL-0006 or CNL-0026 artifacts are delivered on this tree",
      "P14-P19 protocol records were enumerated from 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "ADV rebuild of an architecture dossier"
    ]
  },
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "linux-local"
  },
  "reviewer": {
    "reviewer_id": "CNL-0034-probe2-both-states",
    "verdict": "PASS",
    "independent": true,
    "both_states_rerun": true,
    "control_executed": true,
    "notes": "Named probe2 re-executes planted-bad and known-good from jury_model.py before signing. Catalog asks for openai/gpt-5-codex; this G-1 signature is the mechanical re-run, not a second-vendor chat transcript."
  },
  "named_probes": [
    {
      "id": "probe1",
      "role": "gatekeeper",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0034/probe1_gatekeeper.py"
    },
    {
      "id": "probe2",
      "role": "both-states-and-negative-control",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0034/probe2_negative_control.py"
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0034-jury-topology-deciders-who-did-not-argue.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0034/jury_model.py",
      "exists": true,
      "role": "supporting"
    }
  ],
  "cloud_ok": false,
  "min_bytes_threshold": 4096,
  "ts": "2026-08-25T00:54:03Z"
}
