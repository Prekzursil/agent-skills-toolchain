{
  "answer": "A council output, judged as a workflow-type artifact on the single control plane, can satisfy conditions 1-8, 10 and 11 of the shared 12-condition predicate. It cannot satisfy condition 9 (independent reviewer status is PASS) from its own ballots: seated consensus is circular as review of the council unit. Discharge: a disjoint-roster external reviewer of the council artifact; a council that reviews another unit discharges that unit's C9 only. It cannot satisfy condition 12 (downstream consumers can read it) by transcript readability or schema-valid existence. Discharge: a named parent fan-in consumer must open, parse, and extract sentinel, recommendation, lineage_root, and dissent. Neither C9 nor C12 is NOT-APPLICABLE. Exit 0 is never success; a digest is not a receipt; a path in text is not existence. SUCCESS:CNL-0125. Independent recount: n_can=10 n_cannot=2 cannot=[9, 12].",
  "anti_patterns": "Exit code zero alone is never success. A plausible digest is not a receipt. A file path in text is not proof the file exists.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0125-council-result-against-the-shared-12-condition-completion-.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "supporting"
    }
  ],
  "both_states": {
    "known_good": {
      "complete": true,
      "exit_code": 0,
      "id": "good",
      "unsatisfied": []
    },
    "planted_bad": {
      "complete": false,
      "exit_code": 0,
      "id": "missing-sentinel",
      "unsatisfied": [
        5
      ]
    }
  },
  "catalog_path_is_md_bytes_are_json": true,
  "claims": [
    {
      "claim": "Council output can satisfy C1-C8, C10, C11.",
      "id": "C-CAN",
      "verdict": "CONFIRMED"
    },
    {
      "claim": "Council output cannot satisfy C9 or C12 from its internals.",
      "id": "C-CANNOT",
      "verdict": "CONFIRMED"
    }
  ],
  "completion_sentinel": "SUCCESS:CNL-0125",
  "condition_table": [
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "Same reducer as every other unit: state in {SUCCESS} SATISFIES; other terminals UNSATISFY C1 rather than converting to PASS.",
      "how_or_why_not": "Council-as-workflow (CNL-0124) records envelope.state. SUCCESS is the only completion terminal. BLOCKED/FAILED/TIMEOUT/SEVERED are terminal but not complete. Process exit 0 with state missing or RUNNING does not satisfy C1.",
      "n": 1,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 1",
      "spec_verbatim": "process/task reached a valid terminal state"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "stat the declared path; missing file => C2 UNSATISFIED.",
      "how_or_why_not": "The council result file must exist on disk at output_path. A path printed in the transcript is not existence (anti-pattern 3).",
      "n": 2,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 2",
      "spec_verbatim": "expected artifact exists"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "re-measure bytes; empty or undersize => C3 UNSATISFIED.",
      "how_or_why_not": "Council JSON must exceed a meaningful floor (128 B here) and the declared byte count must match bytes on disk.",
      "n": 3,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 3",
      "spec_verbatim": "artifact is non-empty and exceeds a meaningful minimum size"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "json.loads + schema validate; parse error => C4 UNSATISFIED.",
      "how_or_why_not": "Council result must parse as JSON against the declared council result / design-note schema. Markdown-only transcript fails C4.",
      "n": 4,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 4",
      "spec_verbatim": "artifact parses against its schema"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "Strip sentinel, keep exit 0 / existing file / schema-valid: predicate.complete must be false with C5 UNSATISFIED.",
      "how_or_why_not": "The catalog sentinel (SUCCESS:<id> or the council unit sentinel) must be present in the result. Missing sentinel MUST fail even when exit_code is 0 \u2014 that is the live-wiring proof.",
      "n": 5,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 5",
      "spec_verbatim": "required sentinel is present"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "require >=2 evidence_anchors pointing at ledger ids.",
      "how_or_why_not": "CNL-0075 lineage: idea -> option card -> claim -> argument -> vote -> decision -> action plan. A recommendation with no anchors fails C6.",
      "n": 6,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 6",
      "spec_verbatim": "required evidence anchors exist"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "non-empty tests[] all PASS; empty or FAIL => C7 UNSATISFIED.",
      "how_or_why_not": "tests_required on the council *unit* must have run and passed. Seated votes are not tests. simulate.py exit 0 is not C7.",
      "n": 7,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 7",
      "spec_verbatim": "required tests ran and passed"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "at least one control with fired_on_bad and silent_on_good.",
      "how_or_why_not": "Council anti-failure controls must FIRE on a planted-bad fixture and stay SILENT on known-good. A control that is always-red or always-green measures nothing.",
      "n": 8,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 8",
      "spec_verbatim": "negative controls or mutations fail as expected"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": false,
      "discharge": "Council-specific: attach an external_reviewer whose reviewer_id is not in seated_participants and whose verdict is PASS. When this council is the review of a *different* unit, its verdict discharges C9 of that reviewed unit only \u2014 never C9 of itself. Not NOT-APPLICABLE: an N/A here would let a council complete without independent review.",
      "how_or_why_not": "A council output cannot satisfy C9 from its own internals. The council is the producing body. Treating 'the council voted PASS' as independent review of the council unit is circular (CNL-0026: judge/juror fusion is the named SPOF). Internal judge/juror separation is C8-class protocol hygiene, not C9 of the council unit.",
      "n": 9,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 9",
      "spec_verbatim": "independent reviewer status is PASS"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "zero open P0/P1 on the council run record.",
      "how_or_why_not": "Open P0/P1 defects attached to the council run block completion the same way they block any other unit.",
      "n": 10,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 10",
      "spec_verbatim": "no unresolved P0/P1 defect is attached"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": true,
      "discharge": "manifest.registered and sha256_matches against disk bytes.",
      "how_or_why_not": "The council result must be a row in the unit artifact manifest with sha256 matching bytes on disk. A plausible digest with no file is not a receipt (anti-pattern 2).",
      "n": 11,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 11",
      "spec_verbatim": "output was registered in the artifact manifest"
    },
    {
      "applicability": "APPLICABLE",
      "can_satisfy": false,
      "discharge": "Council-specific: a named downstream consumer \u2014 the parent workflow fan-in / synthesis reader \u2014 must open, parse, and extract sentinel, recommendation, lineage_root, and dissent. Schema-valid JSON missing a consumer field => C12 UNSATISFIED. Not NOT-APPLICABLE: N/A would make C12 decorative.",
      "how_or_why_not": "A council output cannot satisfy C12 by 'participants can read the transcript' or by schema-valid existence. ADV-0001: a passing-but-unusable artifact is the named attack. Existence is not readability (CC-0009).",
      "n": 12,
      "spec_cite": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648 condition 12",
      "spec_verbatim": "downstream consumers can read it"
    }
  ],
  "counts": {
    "can_satisfy": [
      1,
      2,
      3,
      4,
      5,
      6,
      7,
      8,
      10,
      11
    ],
    "cannot_satisfy": [
      9,
      12
    ],
    "n_can": 10,
    "n_cannot": 2
  },
  "distinction": "Council internals (votes, judge/juror split, transcript) are evidence for C1-C8/C10-C11 of the council unit, or for C9 of a *reviewed* unit. They are not evidence for C9 or C12 of the council unit itself.",
  "enumeration": {
    "agreement": true,
    "expected_n": 12,
    "measured_n": 12,
    "signals": [
      "module table.counts() over ROWS",
      "probe1 recount of artifact condition_table"
    ]
  },
  "evidence": [
    {
      "anchor": "command-center/COMPLETION-GATES.json:32",
      "claim": "The 12 conditions are the shared predicate at 10631-10644.",
      "second_anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json#gate_a_unit_completion_predicate.conditions",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:CNL-0125",
      "claim": "CNL-0125 names C9 and C12 as the cannots.",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0125/predicate.py",
      "claim": "Missing sentinel fails C5 at exit_code 0.",
      "verdict": "CONFIRMED"
    }
  ],
  "family": "completion-predicate",
  "irreducible_verdict_requirements": [
    "Score all 12 conditions; do not fold N/A into PASS.",
    "C5 missing sentinel => UNSATISFIED even when exit_code==0.",
    "C9 requires reviewer_id not in seated_participants.",
    "C12 requires a named consumer extracting sentinel, recommendation, lineage_root, dissent.",
    "Exit code zero alone is never success. A plausible digest is not a receipt. A file path in text is not proof the file exists."
  ],
  "kind": "council-design-note",
  "negative_control": {
    "check": "evaluate(missing_sentinel) => complete=false and 5 in unsatisfied",
    "rejected_state": "exit-0 schema-valid council result with sentinel stripped",
    "verbatim": "A council result with process exit 0, a path on disk, schema-valid JSON, and participant-unanimous PASS, but with the completion sentinel stripped, must return complete=false with condition 5 UNSATISFIED. The check rejects that state; it does not treat exit 0 as success."
  },
  "negative_controls": [
    {
      "check": "evaluate(missing_sentinel) => complete=false and C5 UNSATISFIED",
      "rejected_state": "exit-0 schema-valid council result with sentinel stripped",
      "verbatim": "A council result with process exit 0, a path on disk, schema-valid JSON, and participant-unanimous PASS, but with the completion sentinel stripped, must return complete=false with condition 5 UNSATISFIED. The check rejects that state; it does not treat exit 0 as success."
    }
  ],
  "output_schema": "command-center/schema/council-design-note.schema.json",
  "question": "Which of the 12 completion conditions can a council output actually satisfy, and for each one it cannot (independent reviewer PASS, downstream consumers can read it), what is the council-specific discharge?",
  "reviewer": {
    "independent": true,
    "method": "re-tabulate condition_table; disagreement in n_cannot blocks",
    "reviewer_id": "CNL-0125-probe1-independent-recount",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0125",
  "spec_capture": "command-center/p2-wave/probes/WFA-0042/_validate_out.json#gate_a_unit_completion_predicate.conditions",
  "spec_locus": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:10627-10648",
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0125/probe1_condition_table.py",
      "id": "probe1-independent-recount",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0125/probe2_missing_sentinel.py",
      "id": "probe2-missing-sentinel",
      "result": "PASS"
    }
  ],
  "title": "Council result against the shared 12-condition completion predicate",
  "ts": "2026-08-25T00:54:01Z",
  "unit_id": "CNL-0125"
}
