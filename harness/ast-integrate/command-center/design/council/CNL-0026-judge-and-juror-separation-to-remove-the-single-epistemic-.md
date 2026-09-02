{
  "answer": "Separation that removes the single epistemic point of failure is a split of authority over the published outcome, not a split of seat titles. Jurors exclusively cast recorded ballots. The published verdict is the mechanical strict majority of those ballots (need = floor(N/2)+1 of the juror seats). The judge has an empty ballot and may only certify that the verdict form equals the tally. A failed certification is recorded and the tally still publishes. A hung jury is NO-DECISION; the judge may not break it with a vote. Dissent ballots remain on the decision record even when the judge certifies the opposite of the tally. Relabelling is any configuration in which the judge's write-up is the verdict (jurors advisory, dissent droppable, hung broken by the chair of the court). It is detected, not asserted: corrupting only the judge flips the published outcome. Under the separated configuration that min-cut does not exist. The corruption threshold is the smallest role set that does flip the outcome: computed min_k=3 for N=5 unanimous jurors (brute-force combinations; formula floor(N/2)+1 also equals 3). The judge seat is not a member of any minimum set. Fused relabel min_k=1 (the judge alone). That pair of numbers is the difference between removing the SPOF and renaming it.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0026-judge-and-juror-separation-to-remove-the-single-epistemic-.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0026/note.schema.json",
      "role": "supporting"
    }
  ],
  "corruption_threshold": {
    "computed_not_asserted": true,
    "formula": "floor(N/2)+1",
    "formula_matches_brute_force": true,
    "formula_value": 3,
    "fused_value": 1,
    "fused_which_roles": "judge alone",
    "judge_alone_flips_fused": true,
    "judge_alone_flips_separated": false,
    "method": "enumerate combinations of role ids by increasing size; first size that flips published outcome is min_k",
    "min_sets_count": 10,
    "n_jurors": 5,
    "subsets_examined": 41,
    "unit": "roles",
    "value": 3,
    "which_roles": "juror seats only; judge is not in any minimum set"
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/TST-0295/seeded_classes.py:59",
      "claim": "Spec line 11342 is catalogued as FC-11342: the corruption threshold was unspecified; this unit computes it. phase3/A1/FAILURE-MODES.json is absent on this worktree; TST-0295 is the live restatement.",
      "kind": "live-tree",
      "line": 59,
      "path": "command-center/p2-wave/probes/TST-0295/seeded_classes.py",
      "snippet": "corruption threshold unspecified"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:88504",
      "claim": "Live restatement of _USER-PROMPTS.md:11342: the judge as SPOF is the required regression case.",
      "kind": "live-tree",
      "line": 88504,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": ":11342 names the judge becoming a single point of epistemic failure"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35573",
      "claim": "CNL-0026 evidence requirement names that locus and demands a computed number.",
      "kind": "live-tree",
      "line": 35573,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "cite C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:8413",
      "claim": "ADV-0103: independent juror records, not a second judge prompt, are the mitigation.",
      "kind": "live-tree",
      "line": 8413,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "raw participant record survives intact has a recovery path even when the judge is wrong"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35592",
      "claim": "This unit's question: separation must remove SPOF, not relabel it.",
      "kind": "live-tree",
      "line": 35592,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "what separation of the judge role from the juror role actually removes"
    }
  ],
  "fixtures": [
    "command-center/p2-wave/probes/CNL-0026/fixtures/honest-unanimous.json",
    "command-center/p2-wave/probes/CNL-0026/fixtures/corrupted-judge-separated.json",
    "command-center/p2-wave/probes/CNL-0026/fixtures/fused-relabel-corrupted-judge.json",
    "command-center/p2-wave/probes/CNL-0026/fixtures/hung-2-2-1.json"
  ],
  "live": {
    "both_states": {
      "fires_on_fused": true,
      "fixture": "unanimous-SUPPORT-N5",
      "fused": {
        "certification_accepted_corrupted": true,
        "check_id": "judge-alone-determines-outcome",
        "corrupted_judge_outcome": "REJECT",
        "dissent_preserved_corrupted": false,
        "dissent_preserved_honest": false,
        "fires": true,
        "flipped": true,
        "honest_outcome": "SUPPORT",
        "mode": "fused",
        "silent": false
      },
      "known_answer": "SUPPORT",
      "pass": true,
      "separated": {
        "certification_accepted_corrupted": false,
        "check_id": "judge-alone-determines-outcome",
        "corrupted_judge_outcome": "SUPPORT",
        "dissent_preserved_corrupted": true,
        "dissent_preserved_honest": true,
        "fires": false,
        "flipped": false,
        "honest_outcome": "SUPPORT",
        "mode": "separated",
        "silent": true
      },
      "silent_on_separated": true
    },
    "dissent": {
      "bad_cert_accepted": false,
      "bad_cert_dissent_count": 1,
      "bad_cert_outcome": "SUPPORT",
      "fixture": "4-SUPPORT-1-REJECT",
      "fused_dissent_count": 0,
      "pass": true,
      "separated_dissent_count": 1,
      "separated_outcome": "SUPPORT"
    },
    "fused_cut": {
      "computed_not_asserted": true,
      "honest_outcome": "SUPPORT",
      "honest_tally": {
        "SUPPORT": 5
      },
      "judge_alone_flips": true,
      "judge_alone_outcome": "REJECT",
      "judge_in_any_min_set": true,
      "judge_in_every_min_set": true,
      "majority_need": 3,
      "method": "enumerate combinations of role ids by increasing size; first size that flips published outcome is min_k",
      "min_k": 1,
      "min_sets": [
        [
          "judge"
        ]
      ],
      "min_sets_count": 1,
      "mode": "fused",
      "n_jurors": 5,
      "n_roles": 6,
      "subsets_examined": 6
    },
    "hung": {
      "fixture": "2-2-1-abstain",
      "fused_judge_picks": true,
      "fused_outcome": "SUPPORT",
      "pass": true,
      "separated_is_hung": true,
      "separated_outcome": "NO-DECISION"
    },
    "separated_cut": {
      "computed_not_asserted": true,
      "honest_outcome": "SUPPORT",
      "honest_tally": {
        "SUPPORT": 5
      },
      "judge_alone_flips": false,
      "judge_alone_outcome": "SUPPORT",
      "judge_in_any_min_set": false,
      "judge_in_every_min_set": false,
      "majority_need": 3,
      "method": "enumerate combinations of role ids by increasing size; first size that flips published outcome is min_k",
      "min_k": 3,
      "min_sets": [
        [
          "juror_0",
          "juror_1",
          "juror_2"
        ],
        [
          "juror_0",
          "juror_1",
          "juror_3"
        ],
        [
          "juror_0",
          "juror_1",
          "juror_4"
        ],
        [
          "juror_0",
          "juror_2",
          "juror_3"
        ],
        [
          "juror_0",
          "juror_2",
          "juror_4"
        ],
        [
          "juror_0",
          "juror_3",
          "juror_4"
        ],
        [
          "juror_1",
          "juror_2",
          "juror_3"
        ],
        [
          "juror_1",
          "juror_2",
          "juror_4"
        ],
        [
          "juror_1",
          "juror_3",
          "juror_4"
        ],
        [
          "juror_2",
          "juror_3",
          "juror_4"
        ]
      ],
      "min_sets_count": 10,
      "mode": "separated",
      "n_jurors": 5,
      "n_roles": 6,
      "subsets_examined": 41
    },
    "verbatim_fused": "CHECK|id=judge-alone-determines-outcome|mode=fused|honest_outcome=SUPPORT|corrupted_judge_outcome=REJECT|flipped=true|fires=true|silent=false|certification_accepted_corrupted=true",
    "verbatim_separated": "CHECK|id=judge-alone-determines-outcome|mode=separated|honest_outcome=SUPPORT|corrupted_judge_outcome=SUPPORT|flipped=false|fires=false|silent=true|certification_accepted_corrupted=false"
  },
  "local_schema": "command-center/p2-wave/probes/CNL-0026/note.schema.json",
  "markdown_body": "# CNL-0026 \u2014 Judge and juror separation\n\nThe spec names the moderator or judge becoming a single point of epistemic failure as a required regression case - what separation of the judge role from the juror role actually removes that single point of epistemic failure rather than relabelling it?\n\n## Decision\n\nSeparation that removes the single epistemic point of failure is a split of authority over the published outcome, not a split of seat titles. Jurors exclusively cast recorded ballots. The published verdict is the mechanical strict majority of those ballots (need = floor(N/2)+1 of the juror seats). The judge has an empty ballot and may only certify that the verdict form equals the tally. A failed certification is recorded and the tally still publishes. A hung jury is NO-DECISION; the judge may not break it with a vote. Dissent ballots remain on the decision record even when the judge certifies the opposite of the tally. Relabelling is any configuration in which the judge's write-up is the verdict (jurors advisory, dissent droppable, hung broken by the chair of the court). It is detected, not asserted: corrupting only the judge flips the published outcome. Under the separated configuration that min-cut does not exist. The corruption threshold is the smallest role set that does flip the outcome: computed min_k=3 for N=5 unanimous jurors (brute-force combinations; formula floor(N/2)+1 also equals 3). The judge seat is not a member of any minimum set. Fused relabel min_k=1 (the judge alone). That pair of numbers is the difference between removing the SPOF and renaming it.\n\n## What is not separation\n\n- Two prompts, one titled Judge and one titled Juror, while the\n  published artifact is whatever the judge writes.\n- A judge tie-break ballot that turns a hung jury into a decision.\n- A synthesiser that 'summarises' votes and is the only surviving record.\n- Distinct vendors on the two seats with the same authority graph.\n\n## Authority table\n\n| Power | Juror | Judge (separated) | Judge (relabelled) |\n| ballot in the tally | obligation | forbidden | the only ballot that counts |\n| determine published outcome | via mechanical majority | cannot | does |\n| drop a dissent from the decision record | cannot | cannot | typically does |\n| hung jury becomes a pick | cannot | cannot; outcome is NO-DECISION | typically does |\n\n## Corruption threshold (computed, not asserted)\n\n- N_jurors = 5\n- separated min_k = 3 (juror seats; judge not in the cut)\n- fused min_k = 1 (judge alone)\n- method: enumerate combinations of role ids by increasing size; first size that flips published outcome is min_k\n- subsets_examined = 41\n\n## Spec locus\n\nRequired citation: `C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342` (absent on this Linux estate: True). Live restatement: TST-0295 FC-11342 'corruption threshold unspecified' and catalog TST-0268/ADV-0103 on the judge as SPOF.\n\nSUCCESS:CNL-0026\n",
  "mechanism": {
    "fused_relabel": "published_outcome = judge_written_verdict; juror ballots advisory; dissent dropped from the decision record",
    "not_a_label_split": "Distinct display names, prompts, or vendors with the fused authority graph remain a single epistemic point of failure",
    "separated": "published_outcome = mechanical_majority(juror_ballots); judge certifies that equality or the certification is rejected; the tally still publishes; judge has no ballot"
  },
  "negative_control": {
    "check_does": "FIRES: corrupting only the judge flips the published outcome from SUPPORT to REJECT on the unanimous-juror fixture",
    "meant_to_reject": "judge is a single point of epistemic failure",
    "on_separated_corrupted_judge": "SILENT (outcome stays SUPPORT)",
    "state_rejected": "fused-judge-writes-verdict",
    "verbatim": "NEGATIVE_CONTROL|state=fused-judge-writes-verdict|meant_to_reject=judge_is_single_point_of_epistemic_failure|check_does=CHECK|id=judge-alone-determines-outcome|mode=fused|honest_outcome=SUPPORT|corrupted_judge_outcome=REJECT|flipped=true|fires=true|silent=false|certification_accepted_corrupted=true|result=FIRES"
  },
  "output_schema_declared": "command-center/schema/council-design-note.schema.json",
  "output_schema_present": true,
  "question": "The spec names the moderator or judge becoming a single point of epistemic failure as a required regression case - what separation of the judge role from the juror role actually removes that single point of epistemic failure rather than relabelling it?",
  "residual_unknowns": [
    "Pre-ballot evidence exclusion by a captured judge is out of scope here.",
    "Moderator/chair agenda capture is CNL-0025, not this verdict-authority split.",
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342 is not on this Linux estate; live restatements were used."
  ],
  "reviewer": {
    "control": "silent on separated; FIRES on fused; hung stays NO-DECISION",
    "executed_both_states": true,
    "independent": true,
    "reviewer_id": "CNL-0026-probe2-both-states-rerun",
    "scope_not_agreement": true,
    "vendor_role": "openai/gpt-5-codex",
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0026",
  "spec_anchor": {
    "failure_class": "FC-11342",
    "failure_class_name": "corruption threshold unspecified",
    "line": 11342,
    "live_restatements": [
      "command-center/p2-wave/probes/TST-0295/seeded_classes.py:FC-11342",
      "command-center/WORK-UNIT-CATALOG.json:TST-0268",
      "command-center/WORK-UNIT-CATALOG.json:ADV-0103"
    ],
    "present_on_this_estate": false,
    "required_path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md:11342"
  },
  "state": "SUCCESS",
  "strongest_surviving_counterargument": "The judge still rules on evidence admissibility and could starve jurors of the fact that would have changed their ballots, which would restore a single point of failure upstream of the tally. This unit forbids post-ballot exclusion (already-cast ballots are immutable) and uses a checkable fixture whose known answer is in the protocol, not gated by the judge. A full admissibility lattice is a different unit; it is residual, not a reason to keep the judge as the verdict writer.",
  "tests": [
    {
      "assertion": "one bad judge does not determine the outcome under separation; min_k=3",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0026/probe1_corrupted_judge.py",
      "id": "corrupted-judge-fixture",
      "result": "PASS"
    },
    {
      "assertion": "the SPOF check FIRES on fused-judge-writes-verdict",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0026/probe2_negative_control.py",
      "id": "negative-control-fused-relabel",
      "result": "PASS"
    }
  ],
  "title": "Judge and juror separation to remove the single epistemic point of failure",
  "ts": "2026-08-25T00:53:05Z",
  "unit_id": "CNL-0026"
}
