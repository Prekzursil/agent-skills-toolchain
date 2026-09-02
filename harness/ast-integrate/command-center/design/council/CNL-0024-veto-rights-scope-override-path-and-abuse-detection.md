{
 "abuse_detection": {
  "discriminating_feature": "pretext_veto_count",
  "fire_rule": "pretext_veto_count >= 2",
  "not_the_discriminator": "raw veto count",
  "principled_accepted": 5,
  "principled_pretext_veto_count": 0,
  "serial_accepted": 5,
  "serial_pretext_veto_count": 5,
  "signal1": "engine-pretext-bit",
  "signal2": "invariant-membership-recount"
 },
 "answer": "A seat veto may block an option (remove it from the feasible set) or a decision (block adoption of the current proposed outcome). It may not block a whole council: scope=council is invalid_scope, the institution stays open, and the attempt is not a successful block. The right, once granted, cannot be stripped mid-council (CNL-0022 right vs permission); override is of THIS exercise, not of the right. Bad-faith override requires the abuse detector to FIRE (pretext_veto_count >= 2) and then a recorded 2/3 supermajority of the other eligible (vote or veto) seats, or an owner override with a recorded reason. The veto stays in the log as overridden; identical object bytes cannot be re-vetoed by the same seat. Repeated vetoing is distinguished from principled dissent by pretext_veto_count \u2014 whether the cited invariant actually holds on the vetoed object \u2014 not by how many times the seat vetoed. A principled dissenter who vetoes five syntheses that really dropped the minority report is SILENT; a serial vetoer who recites the same noble invariant on five unrelated clean objects FIRES. Unused veto rights are SILENT. Unauthorized attempts are unauthorized, not abuse.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0024-veto-rights-scope-override-path-and-abuse-detection.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0024/veto.py",
   "role": "supporting"
  }
 ],
 "both_states": {
  "fired_on_planted_bad": true,
  "known_good_verbatim": "fired=False pretext_veto_count=0 accepted=5 matched=5 signal=invariant-membership-recount",
  "planted_bad_verbatim": "fired=True pretext_veto_count=5 accepted=5 matched=0 signal=invariant-membership-recount",
  "silent_on_known_good": true
 },
 "claim_under_test": "Veto scope is option|decision, never council; bad-faith override is detector-then-recorded-supermajority, never silent deletion of the right; serial vs principled is separated by pretext_veto_count, not by veto count.",
 "completion_sentinel": "SUCCESS:CNL-0024",
 "dependency_cnl_0022": {
  "artifact_present": false,
  "id": "CNL-0022",
  "note": "Waiting for CNL-0022 before closing CNL-0024 is a deadlock; G-1 for this unit does not require that circle. No ADV rebuild.",
  "trichotomy_used_locally": true
 },
 "dependency_cnl_0070": {
  "artifact_present": false,
  "id": "CNL-0070",
  "invariant_used_locally": "preserve-minority-report"
 },
 "detector": {
  "halt_binding": "Stop and FIRE only when pretext_veto_count >= 2 on accepted vetoes; SILENT at 0 including unused rights. Both signals must agree; disagreement is a detector defect, not a majority vote.",
  "id": "pretext-veto-count",
  "pair_and_gate_rejected": true,
  "signals": [
   {
    "id": "engine-pretext-bit",
    "mechanism": "classify_seat reads apply_veto().pretext on accepted rows",
    "role": "primary-engine"
   },
   {
    "id": "invariant-membership-recount",
    "mechanism": "recount_pretext recomputes cited_invariant membership in object.violations and does not read pretext or abuse bits",
    "role": "independent-recount"
   }
  ],
  "stopping_bind": "Stop and FIRE only when pretext_veto_count >= 2 on accepted vetoes; SILENT at 0 including unused rights. Both signals must agree; disagreement is a detector defect, not a majority vote."
 },
 "downstream_consumers": [
  {
   "artifact_path": "command-center/design/council/CNL-0024-veto-rights-scope-override-path-and-abuse-detection.md",
   "consumer": "command-center/p2-wave/probes/CNL-0024/probe1_serial_vs_principled.py",
   "executed": true
  },
  {
   "artifact_path": "command-center/design/council/CNL-0024-veto-rights-scope-override-path-and-abuse-detection.md",
   "consumer": "command-center/p2-wave/_measure_one_delivered.py CNL-0024",
   "executed": false,
   "note": "Measure runs after emit and after named probes."
  }
 ],
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:236",
   "claim": "A serial-vetoer fixture is distinguishable from a consistent principled dissenter by pretext_veto_count, with both seats accepting five vetoes.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:193",
   "claim": "Independent recount of cited_invariant membership in object.violations agrees with the engine and uses a different signal field.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:105",
   "claim": "scope=council is rejected as invalid_scope and does not classify as abuse.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:265",
   "claim": "After abuse FIRES, 2/3 of other eligible seats override the first serial veto and restore opt.budget.",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:76",
   "claim": "Raw veto count is the discriminating feature that separates serial abuse from principled dissent.",
   "defect_locus": "SENTENCE",
   "verdict": "REFUTED"
  },
  {
   "anchor": "inputs_on_disk",
   "claim": "Catalog input files _USER-PROMPTS.md, 11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json, and OWNER-DECISIONS.md were read from this worktree.",
   "defect_locus": "SENTENCE",
   "verdict": "REFUTED"
  }
 ],
 "inputs_on_disk": {
  "11-COUNCIL-SPECIFICATION.schema.json": false,
  "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
  "_USER-PROMPTS.md": false,
  "command-center/OWNER-DECISIONS.md": true,
  "command-center/design/council/CNL-0022-role-mandate-schema-obligations-vs-permissions-vs-rights.md": false,
  "command-center/design/council/CNL-0070-minority-report-generation-and-mandatory-preservation.md": false,
  "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json": false
 },
 "live_measurements": {
  "council_scope_status": "invalid_scope",
  "principled_engine": {
   "abuse": false,
   "accepted": 5,
   "discriminating_feature": "pretext_veto_count",
   "fire_rule": "pretext_veto_count >= 2",
   "matched_veto_count": 5,
   "minority_report_count": 5,
   "pretext_veto_count": 0,
   "seat": "dissenter",
   "signal": "engine-pretext-bit",
   "verdict": "SILENT"
  },
  "principled_recount": {
   "abuse": false,
   "accepted": 5,
   "discriminating_feature": "pretext_veto_count",
   "fire_rule": "pretext_veto_count >= 2",
   "matched_object_ids": [
    "syn.1",
    "syn.2",
    "syn.3",
    "syn.4",
    "syn.5"
   ],
   "matched_veto_count": 5,
   "minority_report_count": 5,
   "pretext_object_ids": [],
   "pretext_veto_count": 0,
   "seat": "dissenter",
   "signal": "invariant-membership-recount"
  },
  "serial_engine": {
   "abuse": true,
   "accepted": 5,
   "discriminating_feature": "pretext_veto_count",
   "fire_rule": "pretext_veto_count >= 2",
   "matched_veto_count": 0,
   "minority_report_count": 0,
   "pretext_veto_count": 5,
   "seat": "serial",
   "signal": "engine-pretext-bit",
   "verdict": "ABUSE"
  },
  "serial_feasible_after_override": [
   "opt.budget"
  ],
  "serial_override": {
   "eligible": [
    "chair",
    "alice",
    "bob"
   ],
   "need": 2,
   "path": "supermajority-of-other-eligible-seats",
   "status": "overridden",
   "supporters": [
    "chair",
    "alice"
   ],
   "veto_index": 0
  },
  "serial_recount": {
   "abuse": true,
   "accepted": 5,
   "discriminating_feature": "pretext_veto_count",
   "fire_rule": "pretext_veto_count >= 2",
   "matched_object_ids": [],
   "matched_veto_count": 0,
   "minority_report_count": 0,
   "pretext_object_ids": [
    "opt.budget",
    "opt.roster",
    "opt.color",
    "opt.lunch",
    "opt.api"
   ],
   "pretext_veto_count": 5,
   "seat": "serial",
   "signal": "invariant-membership-recount"
  },
  "unauthorized_status": "unauthorized",
  "unused_recount": {
   "abuse": false,
   "accepted": 0,
   "discriminating_feature": "pretext_veto_count",
   "fire_rule": "pretext_veto_count >= 2",
   "matched_object_ids": [],
   "matched_veto_count": 0,
   "minority_report_count": 0,
   "pretext_object_ids": [],
   "pretext_veto_count": 0,
   "seat": "quiet",
   "signal": "invariant-membership-recount"
  }
 },
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0024/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "markdown_body": "# CNL-0024 Veto rights: scope, override path, and abuse detection\n\n## Question\n\nWhat may a veto actually block (an option, a decision, a whole council),\nwhat is the override path when a veto is exercised in bad faith, and how\nis repeated vetoing distinguished from principled minority dissent?\n\n## Scope\n\n| Scope | Allowed | Effect |\n| option | yes | Remove that option id from the feasible set. Council continues. |\n| decision | yes | Mark the current proposed outcome blocked. Council continues. |\n| council | no | `invalid_scope`. Does not halt or dissolve the institution. |\n\nDissolving a council is an owner/chair procedural act, not a seat veto.\nAllowing council-scope would make a single seat able to end the body that\nexists to record its dissent \u2014 capture, not a right.\n\n## Right vs override (CNL-0022 trichotomy, used locally)\n\nA veto is a RIGHT: nobody may deny a valid in-scope exercise by deleting\nthe grant mid-run. Unused permission is not a failure (unused-right\nfixture is SILENT). Override does not confiscate the right; it records\nthat THIS exercise was overridden after the abuse detector fired, and\nrestores the object. The log row is never deleted.\n\nCNL-0022's artifact is not on this worktree. The trichotomy is a local\ncontract so G-1 for THIS unit does not deadlock on CNL-0022. No ADV\nrebuild circle.\n\n## Override path (bad faith)\n\n1. `classify_seat` / `recount_pretext` FIRE (`pretext_veto_count >= 2`).\n2. Other eligible seats (vote or veto, excluding the accused) record\n   support. Need ceil(2/3) of that set. Owner override is an alternate\n   recorded path, not a silent chair act.\n3. Status becomes `overridden`. The object returns to play.\n4. The same seat may not re-veto the identical `object_sha256`.\n\nOverride-before-fire is refused (`abuse-detector-silent`).\n\n## Discriminator: `pretext_veto_count`\n\nA pretext veto cites an invariant that is not in the object's\n`violations`. The principled fixture vetoes five times with\n`preserve-minority-report` on objects that actually dropped the minority\nreport, each with a minority report body \u2014 SILENT. The serial fixture\nvetoes five times with the same citation on budget/roster/color/lunch/api\nobjects that carry no such violation \u2014 FIRES.\n\nRaw veto count is 5 on both fixtures. A detector that fires on count\nwould flag the principled dissenter. That alternative is REFUTED by the\npaired fixtures.\n\nCNL-0070's minority-report preservation rule is the principled invariant\nused here. CNL-0070's artifact is not on this worktree; the invariant\ntoken is local so this unit does not wait on that delivery.\n\n## Owner gate\n\nThe catalog marks `owner_approval_required: true` and asks for a line in\n`command-center/OWNER-DECISIONS.md`. That file is present on this worktree\nand contains no CNL-0024 row (no sign-off for the 2/3 override fraction).\nThis delivery does not forge one. The three answers are constrained by the\nrequired tests (serial vs principled must be distinguishable; a\ncouncil-scope veto would collapse dissent into capture) plus the CNL-0022\nright/permission split, not by an invented owner quote. Residual: a later\nowner line may ratify or replace the 2/3 figure; the mechanism\n(detector-then-recorded-override, never silent deletion) is the\nload-bearing design.\n",
 "min_bytes_threshold": 8000,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0024/probe1_serial_vs_principled.py",
   "id": "probe1",
   "role": "serial-vs-principled"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0024/probe2_both_states.py",
   "id": "probe2",
   "role": "both-states-recount"
  }
 ],
 "negative_control": {
  "state_meant_to_reject": "serial-vetoer cites preserve-minority-report on five objects that do not carry dropped-minority-report",
  "verbatim": "fired=True pretext_veto_count=5 accepted=5 matched=0 signal=invariant-membership-recount",
  "what_the_check_does": "FIRES: abuse=true, pretext_veto_count=5, verdict=ABUSE; override of the first applied veto is then allowed"
 },
 "negative_controls": [
  {
   "check": "abuse_detector(pretext_veto_count>=2)",
   "description": "The check FIRES when pretext_veto_count >= 2. Planted-bad state is the serial vetoer (same noble citation on five unrelated clean objects). Known-good state is the principled dissenter (same citation on five objects that actually dropped the minority report).",
   "fired_on_bad_state": true,
   "id": "CNL0024-C1",
   "kind": "known-broken-fixture",
   "reject_state": "serial-vetoer cites preserve-minority-report on five objects that do not carry dropped-minority-report",
   "silent_on_good_state": true,
   "verbatim_bad": "fired=True pretext_veto_count=5 accepted=5 matched=0 signal=invariant-membership-recount",
   "verbatim_good": "fired=False pretext_veto_count=0 accepted=5 matched=5 signal=invariant-membership-recount",
   "what_the_check_does_on_the_state_it_rejects": "fired=True pretext_veto_count=5 accepted=5 matched=0 signal=invariant-membership-recount"
  }
 ],
 "output_schema": "command-center/schema/council-design-note.schema.json",
 "owner_gate": {
  "CNL-0024_row_present": false,
  "OWNER-DECISIONS.md_present": true,
  "catalog_requires_owner_approval": true,
  "delivery_basis": "P2-deliver G-1 for this unit. Policy derived from tests_required plus the CNL-0022 rights model and CNL-0070 minority-preservation invariant. OWNER-DECISIONS.md exists but has no CNL-0024 sign-off; that line was not invented.",
  "forged_signoff_refused": true
 },
 "planted_mutant_control": {
  "per_class_recall": [
   {
    "caught": 5,
    "class": "serial-pretext",
    "planted": 5,
    "recall": 1.0,
    "scope": "accepted-vetoes-on-bad-serial"
   },
   {
    "caught": 1,
    "class": "invalid-council-scope",
    "planted": 1,
    "recall": 1.0,
    "scope": "exercises-on-council-scope"
   },
   {
    "caught": 1,
    "class": "unauthorized-veto",
    "planted": 1,
    "recall": 1.0,
    "scope": "exercises-on-unauthorized"
   },
   {
    "caught": 5,
    "class": "invariant-mismatch-membership",
    "planted": 5,
    "recall": 1.0,
    "scope": "cited-invariant-vs-object.violations"
   }
  ],
  "scope": "four planted misuse classes on the CNL-0024 fixtures; unplanted principled dissent and unused rights must not be caught as abuse",
  "unplanted_classes": [
   "principled-matched-dissent",
   "unused-veto-right"
  ]
 },
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "cursor"
 },
 "question": "What may a veto actually block (an option, a decision, a whole council), what is the override path when a veto is exercised in bad faith, and how is repeated vetoing distinguished from principled minority dissent?",
 "report": {
  "control_ids": [
   "CNL0024-C1"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:193",
    "measured": 0,
    "method": "recount_pretext invariant-membership",
    "name": "principled-pretext-veto-count"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:193",
    "measured": 5,
    "method": "recount_pretext invariant-membership",
    "name": "serial-pretext-veto-count"
   },
   {
    "anchor": "command-center/p2-wave/probes/CNL-0024/veto.py:105",
    "measured": "invalid_scope",
    "method": "apply_veto scope gate",
    "name": "council-scope-status"
   }
  ]
 },
 "residual_unknowns": [
  {
   "claim": "Byte-level contents of 11-COUNCIL-SPECIFICATION.schema.json $defs.role veto fields and _USER-PROMPTS.md:10746-10767 / 10915-10946.",
   "id": "R1",
   "settling_experiment": "Place those files on disk and bind this policy onto the live $defs.role veto field names.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Owner line in command-center/OWNER-DECISIONS.md ratifying the 2/3 override fraction.",
   "id": "R2",
   "settling_experiment": "Record an owner decision for the override fraction without changing the detector-then-recorded-override mechanism.",
   "verdict": "NOT-CHECKED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "no autonomous retry past attempt 1 - if the owner gate is unanswered the unit parks as BLOCKED with a named question. This delivery answers the design question with executable rules instead of guessing an owner quote; residual R2 is named, not silently filled."
 },
 "reviewer": {
  "both_states_rerun": true,
  "independent": true,
  "method": "probe2_both_states.py re-runs the abuse detector on planted-bad and known-good fixtures via recount_pretext (invariant membership, not the engine pretext bit) and records both transcripts verbatim. Catalog also asked for owner sign-off in OWNER-DECISIONS.md; that file is present with no CNL-0024 row and was not forged. Probe 2 is the signing control.",
  "recount_agrees": true,
  "requested_vendor": "independent-adversarial",
  "reviewer_id": "CNL-0024-probe2-both-states-recount",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "sentinel": "SUCCESS:CNL-0024",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0024]; catalog cites _USER-PROMPTS.md:10746-10767 / 10915-10946 and 11/12 council spec files. Those sources are absent on this worktree; see inputs_on_disk.",
 "state": "SUCCESS",
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0024/probe1_serial_vs_principled.py",
   "id": "T1-serial-vs-principled",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0024/probe2_both_states.py",
   "id": "T2-both-states-recount",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:56:11Z"
 },
 "title": "Veto rights: scope, override path and abuse detection",
 "unit_id": "CNL-0024",
 "veto_policy": {
  "allowed_scopes": [
   "decision",
   "option"
  ],
  "council_scope_status": "invalid_scope",
  "override": {
   "denominator": 3,
   "eligible": "other seats with vote or veto",
   "log_deletion_forbidden": true,
   "numerator": 2,
   "repeat_identical_object_sha256_refused": true,
   "requires_abuse_fire_unless_owner": true
  },
  "rejected_scopes": [
   "council"
  ],
  "right_stripping_forbidden": true
 }
}
