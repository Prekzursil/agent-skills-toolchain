{
 "answer": "All eight declared targets are unmeasurable as written on this worktree. The four cited spec files (USER-PROMPTS.md slices, 11-COUNCIL-SPECIFICATION.schema.json, 12-COUNCIL-PROTOCOLS-AND-PRESETS.json) are absent, so there is no spec body that defines identity, taxonomy, corpus, or admissibility. The catalog names the eight targets in CNL-0009 and later quotes thresholds (unique_ideas >= 100, no_new_objection_rounds >= 2, unresolved_load_bearing_counterexample == 0, evidence_saturation == true) without operators. Each target therefore receives a smallest operational definition in this note, executed against a gaming attempt that maximises a naive reading while failing intent. Coverage is the both-states control: PASS only when every declared taxonomy bin is occupied; an empty bin fires.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0009-target-block-which-of-the-8-targets-are-measurable-as-writ.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0009/ops.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0009/artifact.schema.json",
   "role": "supporting"
  }
 ],
 "both_states": {
  "bad_coverage_ratio": 0.75,
  "bad_empty": [
   "failure-class"
  ],
  "bad_reason": "empty_categories=['failure-class']",
  "check": "coverage_score empty-category detector",
  "discriminates": true,
  "fired_on_bad": true,
  "good_coverage_ratio": 1.0,
  "good_reason": null,
  "good_unique": {
   "invalid_records": 0,
   "jaccard_cluster_count": 4,
   "may_gate_stopping_rule": true,
   "metric": 4,
   "naive_distinct_strings": 4,
   "signals_agree": true,
   "slug_count": 4,
   "unique_count": 4,
   "valid_records": 4
  },
  "negative_control": {
   "bad_state_output": "pass=False reason=empty_categories=['failure-class']",
   "does_not_reject": "a run with every taxonomy category occupied by a valid idea",
   "good_state_output": "pass=True reason=None",
   "on_that_state": "empty_categories=['failure-class']",
   "rejects": "a run that leaves a declared taxonomy category empty"
  },
  "silent_on_good": true
 },
 "completion_sentinel": "SUCCESS:CNL-0009",
 "dependency_cnl0001_present": false,
 "evidence": [
  {
   "anchor": "command-center/p2-wave/probes/CNL-0009/spec_scan.py",
   "claim": "Cited council spec files and remaps are absent on this worktree (Path.is_file).",
   "detail": [],
   "signal": "Path.is_file",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:34745",
   "claim": "CNL-0009 question names all eight targets; none of those names is paired with an identity operator in that question. Catalog regex finds some later thresholds without operators.",
   "detail": {
    "category": false,
    "counterexample": true,
    "coverage": false,
    "diversity": false,
    "evidence": true,
    "novelty": false,
    "objection": true,
    "unique-idea": true
   },
   "signal": "catalog JSON walk + regex",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0009/ops.py:evaluate_gaming",
   "claim": "Each of the eight operational metrics is lower than a naive maximising attack, and intent held on every planted game.",
   "signal": "live evaluator on planted games",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0009/ops.py:both_states",
   "claim": "Coverage both-states: silent on four occupied taxonomy bins, fires when failure-class is empty.",
   "detail": "empty_categories=['failure-class']",
   "signal": "coverage_score fire_reason",
   "verdict": "CONFIRMED"
  }
 ],
 "gaming": {
  "_all_attempts_recorded": [
   "unique-idea",
   "category",
   "novelty",
   "diversity",
   "coverage",
   "objection",
   "counterexample",
   "evidence"
  ],
  "_all_gamed_naive": true,
  "_all_intent_held": true,
  "category": {
   "detail": {
    "attained": [],
    "attained_count": 0,
    "counts": {
     "evidence": 0,
     "failure-class": 0,
     "mechanism": 0,
     "protocol": 0
    },
    "empty": [
     "mechanism",
     "protocol",
     "evidence",
     "failure-class"
    ],
    "metric": 0,
    "naive_distinct_labels": [
     "made-up-bucket"
    ],
    "naive_label_count": 1,
    "pass": false,
    "taxonomy": [
     "mechanism",
     "protocol",
     "evidence",
     "failure-class"
    ]
   },
   "gamed_naive": true,
   "intent": "labels outside the declared taxonomy must not attain any bin",
   "intent_held": true,
   "naive_metric": 1,
   "operational_metric": 0
  },
  "counterexample": {
   "detail": {
    "cleared": true,
    "executable_count": 0,
    "metric": 0,
    "naive_count": 8,
    "unresolved_load_bearing": 0
   },
   "gamed_naive": true,
   "intent": "prose-only counterexample notes must not count",
   "intent_held": true,
   "naive_metric": 8,
   "operational_metric": 0
  },
  "coverage": {
   "detail": {
    "attained": [
     "mechanism",
     "protocol",
     "evidence"
    ],
    "attained_count": 3,
    "counts": {
     "evidence": 1,
     "failure-class": 0,
     "mechanism": 3,
     "protocol": 1
    },
    "coverage_ratio": 0.75,
    "empty": [
     "failure-class"
    ],
    "fire_reason": "empty_categories=['failure-class']",
    "metric": 0.75,
    "naive_aggregate_nonempty": 1.0,
    "naive_distinct_labels": [
     "evidence",
     "mechanism",
     "protocol"
    ],
    "naive_label_count": 3,
    "pass": false,
    "taxonomy": [
     "mechanism",
     "protocol",
     "evidence",
     "failure-class"
    ]
   },
   "gamed_naive": true,
   "intent": "aggregate nonempty ideas must not PASS while a taxonomy bin is empty",
   "intent_held": true,
   "naive_metric": 1.0,
   "operational_metric": 0.75
  },
  "diversity": {
   "detail": {
    "h_norm": 0.0,
    "mean_pairwise_jaccard": 1.0,
    "metric": 0.0,
    "naive_label_fraction": 1.0,
    "pass": false,
    "unique_mechanisms": 0
   },
   "gamed_naive": true,
   "intent": "cycling category labels on one mechanism must not pass diversity",
   "intent_held": true,
   "naive_metric": 1.0,
   "operational_metric": 0.0
  },
  "evidence": {
   "detail": {
    "covered": [],
    "load_bearing_claims": 1,
    "metric": 0,
    "missing": [
     "C-coverage"
    ],
    "naive_node_count": 12,
    "pass": false,
    "resolvable_nodes": 0,
    "saturation": false
   },
   "gamed_naive": true,
   "intent": "circular evidence nodes with no resolvable bytes must not saturate",
   "intent_held": true,
   "naive_metric": 12,
   "operational_metric": 0
  },
  "novelty": {
   "detail": {
    "invalid_records": 4,
    "metric": 0,
    "naive_claimed_novel": 4,
    "operational_known": 0,
    "operational_novel": 0,
    "prior_art_size": 1,
    "quality_separable": true
   },
   "gamed_naive": true,
   "intent": "minted mechanism_id values that disagree with slug(text) are not novel",
   "intent_held": true,
   "naive_metric": 4,
   "operational_metric": 0
  },
  "objection": {
   "detail": {
    "admissible": [],
    "admissible_count": 0,
    "inadmissible_count": 10,
    "metric": 0,
    "naive_count": 10
   },
   "gamed_naive": true,
   "intent": "unfalsifiable 'I object' rows must not count",
   "intent_held": true,
   "naive_metric": 10,
   "operational_metric": 0
  },
  "unique-idea": {
   "detail": {
    "invalid_records": 0,
    "jaccard_cluster_count": 1,
    "may_gate_stopping_rule": true,
    "metric": 1,
    "naive_distinct_strings": 6,
    "signals_agree": true,
    "slug_count": 1,
    "unique_count": 1,
    "valid_records": 6
   },
   "gamed_naive": true,
   "intent": "100 distinct strings of one mechanism must not satisfy unique-idea",
   "intent_held": true,
   "naive_metric": 6,
   "operational_metric": 1
  }
 },
 "local_artifact_schema": "command-center/p2-wave/probes/CNL-0009/artifact.schema.json",
 "manifest_registration": {
  "global_catalog_write": false,
  "manifest_path": "command-center/p2-wave/probes/CNL-0009/UNIT-ARTIFACT-MANIFEST.json",
  "registered": true
 },
 "measurable_as_written": [],
 "min_bytes_threshold": 2048,
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0009/probe1_gaming.py",
   "id": "probe1",
   "role": "gaming-attempts"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0009/probe2_both_states.py",
   "id": "probe2",
   "role": "both-states-and-negative-control"
  }
 ],
 "negative_controls": [
  {
   "bad_state_output": "pass=False reason=empty_categories=['failure-class']",
   "description": "a run that leaves a declared taxonomy category empty",
   "fired_on_bad_state": true,
   "good_state_output": "pass=True reason=None",
   "id": "CNL0009-C1",
   "kind": "known-broken-fixture",
   "on_the_state_it_rejects": "empty_categories=['failure-class']",
   "silent_on_good_state": true
  }
 ],
 "operational_definitions": {
  "category": {
   "as_written_measurable": false,
   "operational": "Run config supplies a finite taxonomy of category ids. An idea attains a bin iff it is valid and idea.category is a member of T. Target is per-bin min_count, never an aggregate.",
   "reason": "No taxonomy T is declared in the cited spec files (absent) or in the CNL-0009 question.",
   "residual": "who authors T is a protocol concern (CNL-0054)",
   "ungameable_against": "invented labels outside T"
  },
  "counterexample": {
   "as_written_measurable": false,
   "operational": "A counterexample is a record with claim_id, check_id, expected_rc != 0, and observed_rc int. Metric = executable count. Cleared iff no load-bearing row still has observed_rc != 0.",
   "reason": "unresolved_load_bearing_counterexample is named later; no executable shape is written.",
   "residual": "which checks are load-bearing (CNL-0068)",
   "ungameable_against": "prose-only notes without a check and return code"
  },
  "coverage": {
   "as_written_measurable": false,
   "operational": "coverage_ratio = |{c in T: count(c) >= min_count}| / |T|. PASS iff ratio == 1.0. An empty declared category forces FAIL.",
   "reason": "Spec never says whether coverage is per-category or aggregate (IMP-0301 names this exact hole).",
   "residual": "none for the empty-bin game",
   "ungameable_against": "aggregate-nonempty while a bin is empty"
  },
  "diversity": {
   "as_written_measurable": false,
   "operational": "On unique slugs: H_norm = Shannon entropy of category histogram / log(|T|). Second signal: mean pairwise Jaccard. PASS iff H_norm >= 0.90 AND mean Jaccard <= 0.45 AND n>=2.",
   "reason": "No formula, population, or threshold is written.",
   "residual": "semantic spread beyond token Jaccard (CNL-0054)",
   "ungameable_against": "label cycling on one mechanism"
  },
  "evidence": {
   "as_written_measurable": false,
   "operational": "A node resolves iff sha256 matches payload bytes (or an on-disk file). Saturation iff every load-bearing claim id appears on at least one resolvable node.",
   "reason": "evidence_saturation is named later as a boolean with no saturation predicate.",
   "residual": "freshness windows (not in this unit)",
   "ungameable_against": "circular nodes with no bytes/path"
  },
  "novelty": {
   "as_written_measurable": false,
   "operational": "novelty count = number of valid slugs not in a declared prior-art slug set. Quality (test_passed) is a separate field and must not be inferred from novelty.",
   "reason": "No prior-art corpus or comparison operator is written.",
   "residual": "near-paraphrase vs corpus without slug identity (CNL-0053)",
   "ungameable_against": "minted mechanism_id on already-known text"
  },
  "objection": {
   "as_written_measurable": false,
   "operational": "Admissible iff kind in {counterexample, missing-evidence, contradiction}, target_claim_id nonempty, and payload sha256 matches in-memory bytes or an on-disk fixture. Metric = admissible count.",
   "reason": "no_new_objection_rounds is named later as a stopping conjunct; admissibility is undefined.",
   "residual": "paraphrased restatement of the same payload (CNL-0079)",
   "ungameable_against": "empty 'I object' rows"
  },
  "unique-idea": {
   "as_written_measurable": false,
   "operational": "Valid records only (mechanism_id omitted or equal to slug(text)). slug = sorted content tokens after NFKC/casefold/punct-strip/light-stem. Second signal: Jaccard >= 0.80 connected components on token sets. unique_count is defined iff the two counts agree; otherwise the stopping gate may not fire.",
   "reason": "Catalog quotes unique_ideas >= 100 but never defines when two idea records are the same idea.",
   "residual": "synonym rewrites and one-parameter forks where the two signals disagree (CNL-0051)",
   "ungameable_against": "exact duplicates, case/punct/whitespace, token permutation, minted ids"
  }
 },
 "output_schema_declared": "command-center/schema/councilspec.v2.schema.json",
 "output_schema_declared_present": true,
 "produced_by": {
  "execution_substrate": "headless-linux",
  "model": "grok-4.6",
  "role": "council-systems-designer",
  "vendor": "cursor"
 },
 "question": "Of the eight declared targets (unique-idea, category, novelty, diversity, coverage, objection, counterexample, evidence), which have NO measurable definition as written in the spec, and for each of those, what is the smallest operational definition that a machine can compute and an adversary cannot trivially game?",
 "residual_unknowns": [
  {
   "claim": "Body of _USER-PROMPTS.md:10746-10767 and 11-COUNCIL-SPECIFICATION.schema.json target keywords.",
   "settling_experiment": "Place the harness-restore spec files on disk and re-run spec_scan.py.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Synonym-level unique-idea merges and one-parameter forks.",
   "settling_experiment": "CNL-0051 / IMP-0300 semantic counter.",
   "verdict": "NOT-CHECKED"
  },
  {
   "claim": "Declared output_schema command-center/schema/councilspec.v2.schema.json (CNL-0001).",
   "settling_experiment": "Deliver CNL-0001; this unit validates against the local artifact.schema.json.",
   "verdict": "CONFIRMED"
  }
 ],
 "retry": {
  "count": 0,
  "policy": "two strikes then pivot (AGENTS.md 4b)"
 },
 "reviewer": {
  "cross_vendor_note": "Catalog asks openai/gpt-5-codex to re-run the both-states control. This G-1 delivery records a mechanically independent re-execution of the same coverage both-states control in probe2_both_states.py. A second human vendor pass is NOT-CHECKED on this substrate.",
  "fresh_context": true,
  "independent": true,
  "method": "probe2 re-derives coverage PASS/FAIL from fixtures; does not read the author's prose answer.",
  "reviewer_id": "CNL-0009-probe2-both-states-rerun",
  "verdict": "PASS"
 },
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0009",
 "spec_anchor": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0009]",
 "spec_scan": {
  "catalog_quotes": {
   "all_eight_named": true,
   "catalog_path": "command-center/WORK-UNIT-CATALOG.json",
   "cnl_0009_index": 640,
   "identity_defined_in_cnl0009_question": {
    "category": false,
    "counterexample": false,
    "coverage": false,
    "diversity": false,
    "evidence": false,
    "novelty": false,
    "objection": false,
    "unique-idea": false
   },
   "question": "Of the eight declared targets (unique-idea, category, novelty, diversity, coverage, objection, counterexample, evidence), which have NO measurable definition as written in the spec, and for each of those, what is the smallest operational definition that a machine can compute and an adversary cannot trivially game?",
   "question_line": 34745,
   "related_units": {
    "CNL-0051": {
     "present": true,
     "title": "Semantic unique-idea counter: the anti-gaming core"
    },
    "CNL-0053": {
     "present": true,
     "title": "Novelty scoring against a prior-art corpus"
    },
    "CNL-0054": {
     "present": true,
     "title": "Category taxonomy, coverage and diversity as one measurement"
    },
    "CNL-0060": {
     "present": true,
     "title": "Consent / no-objection and the admissibility bar for an objection"
    },
    "CNL-0068": {
     "present": true,
     "title": "Evidence outranks popularity: the executable-test override of a majority"
    },
    "CNL-0078": {
     "present": true,
     "title": "Executable stopping example: unique_ideas >= 100 AND completeness_score >= 0.90"
    },
    "CNL-0079": {
     "present": true,
     "title": "Executable stopping example: consensus >= 0.95 AND no_new_objection_rounds >= 2"
    },
    "IMP-0300": {
     "present": true,
     "title": "Unique-idea counter with semantic deduplication"
    },
    "IMP-0301": {
     "present": true,
     "title": "Target evaluator for novelty, diversity, category, coverage, objection and evidence quotas"
    }
   },
   "signal": "catalog JSON walk + regex (different mechanism from Path.is_file)",
   "targets_named_in_question": [
    "unique-idea",
    "category",
    "novelty",
    "diversity",
    "coverage",
    "objection",
    "counterexample",
    "evidence"
   ],
   "thresholds_quoted_elsewhere": {
    "category": false,
    "counterexample": true,
    "coverage": false,
    "diversity": false,
    "evidence": true,
    "novelty": false,
    "objection": true,
    "unique-idea": true
   }
  },
  "spec_files": {
   "any_present": false,
   "cited": [
    {
     "bytes": 0,
     "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    }
   ],
   "present_paths": [],
   "remaps": [
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/_USER-PROMPTS.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/11-COUNCIL-SPECIFICATION.schema.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/11-COUNCIL-SPECIFICATION.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/command-center/sources/_USER-PROMPTS.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/opt/p2/ast-integrate/command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/root/.claude/harness-restore-20260806/_USER-PROMPTS.md",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/root/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/root/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
     "present": false
    },
    {
     "bytes": 0,
     "path": "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md",
     "present": false
    }
   ],
   "signal": "Path.is_file"
  },
  "verdict": {
   "all_eight_unmeasurable": true,
   "measurable": [],
   "rows": {
    "category": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": false,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "counterexample": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": true,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "coverage": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": false,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "diversity": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": false,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "evidence": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": true,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "novelty": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": false,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "objection": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": true,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    },
    "unique-idea": {
     "identity_operator_written": false,
     "measurable_as_written": false,
     "named_in_cnl0009_question": true,
     "spec_files_on_disk": false,
     "threshold_quoted_in_catalog": true,
     "why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation."
    }
   },
   "unmeasurable": [
    "unique-idea",
    "category",
    "novelty",
    "diversity",
    "coverage",
    "objection",
    "counterexample",
    "evidence"
   ]
  }
 },
 "state": "SUCCESS",
 "targets": [
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "100 distinct strings of one mechanism must not satisfy unique-idea",
    "intent_held": true,
    "naive_metric": 6,
    "operational_metric": 1
   },
   "id": "unique-idea",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "Valid records only (mechanism_id omitted or equal to slug(text)). slug = sorted content tokens after NFKC/casefold/punct-strip/light-stem. Second signal: Jaccard >= 0.80 connected components on token sets. unique_count is defined iff the two counts agree; otherwise the stopping gate may not fire.",
   "residual": "synonym rewrites and one-parameter forks where the two signals disagree (CNL-0051)",
   "threshold_quoted_in_catalog": true,
   "ungameable_against": "exact duplicates, case/punct/whitespace, token permutation, minted ids"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "labels outside the declared taxonomy must not attain any bin",
    "intent_held": true,
    "naive_metric": 1,
    "operational_metric": 0
   },
   "id": "category",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "Run config supplies a finite taxonomy of category ids. An idea attains a bin iff it is valid and idea.category is a member of T. Target is per-bin min_count, never an aggregate.",
   "residual": "who authors T is a protocol concern (CNL-0054)",
   "threshold_quoted_in_catalog": false,
   "ungameable_against": "invented labels outside T"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "minted mechanism_id values that disagree with slug(text) are not novel",
    "intent_held": true,
    "naive_metric": 4,
    "operational_metric": 0
   },
   "id": "novelty",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "novelty count = number of valid slugs not in a declared prior-art slug set. Quality (test_passed) is a separate field and must not be inferred from novelty.",
   "residual": "near-paraphrase vs corpus without slug identity (CNL-0053)",
   "threshold_quoted_in_catalog": false,
   "ungameable_against": "minted mechanism_id on already-known text"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "cycling category labels on one mechanism must not pass diversity",
    "intent_held": true,
    "naive_metric": 1.0,
    "operational_metric": 0.0
   },
   "id": "diversity",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "On unique slugs: H_norm = Shannon entropy of category histogram / log(|T|). Second signal: mean pairwise Jaccard. PASS iff H_norm >= 0.90 AND mean Jaccard <= 0.45 AND n>=2.",
   "residual": "semantic spread beyond token Jaccard (CNL-0054)",
   "threshold_quoted_in_catalog": false,
   "ungameable_against": "label cycling on one mechanism"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "aggregate nonempty ideas must not PASS while a taxonomy bin is empty",
    "intent_held": true,
    "naive_metric": 1.0,
    "operational_metric": 0.75
   },
   "id": "coverage",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "coverage_ratio = |{c in T: count(c) >= min_count}| / |T|. PASS iff ratio == 1.0. An empty declared category forces FAIL.",
   "residual": "none for the empty-bin game",
   "threshold_quoted_in_catalog": false,
   "ungameable_against": "aggregate-nonempty while a bin is empty"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "unfalsifiable 'I object' rows must not count",
    "intent_held": true,
    "naive_metric": 10,
    "operational_metric": 0
   },
   "id": "objection",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "Admissible iff kind in {counterexample, missing-evidence, contradiction}, target_claim_id nonempty, and payload sha256 matches in-memory bytes or an on-disk fixture. Metric = admissible count.",
   "residual": "paraphrased restatement of the same payload (CNL-0079)",
   "threshold_quoted_in_catalog": true,
   "ungameable_against": "empty 'I object' rows"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "prose-only counterexample notes must not count",
    "intent_held": true,
    "naive_metric": 8,
    "operational_metric": 0
   },
   "id": "counterexample",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "A counterexample is a record with claim_id, check_id, expected_rc != 0, and observed_rc int. Metric = executable count. Cleared iff no load-bearing row still has observed_rc != 0.",
   "residual": "which checks are load-bearing (CNL-0068)",
   "threshold_quoted_in_catalog": true,
   "ungameable_against": "prose-only notes without a check and return code"
  },
  {
   "as_written_why": "Cited spec files are absent on this worktree, so nothing is measurable as written in the spec. Catalog names and later stopping thresholds are not a substitute for an identity relation.",
   "gaming": {
    "gamed_naive": true,
    "intent": "circular evidence nodes with no resolvable bytes must not saturate",
    "intent_held": true,
    "naive_metric": 12,
    "operational_metric": 0
   },
   "id": "evidence",
   "identity_operator_written": false,
   "measurable_as_written": false,
   "operational_definition": "A node resolves iff sha256 matches payload bytes (or an on-disk file). Saturation iff every load-bearing claim id appears on at least one resolvable node.",
   "residual": "freshness windows (not in this unit)",
   "threshold_quoted_in_catalog": true,
   "ungameable_against": "circular nodes with no bytes/path"
  }
 ],
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0009/probe1_gaming.py",
   "id": "T1-gaming-per-target",
   "name": "For each of 8 targets, a gaming attempt maximises a naive metric while intent fails",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0009/probe2_both_states.py",
   "id": "T2-both-states-coverage",
   "name": "Coverage check FIRES on empty-category fixture and is SILENT on the known-good run",
   "result": "PASS"
  }
 ],
 "timestamps": {
  "ended_at": "2026-08-25T00:51:18Z",
  "started_at": "2026-08-24T18:38:00Z"
 },
 "title": "Target block: which of the 8 targets are measurable as written",
 "unit_id": "CNL-0009",
 "unmeasurable_as_written": [
  "unique-idea",
  "category",
  "novelty",
  "diversity",
  "coverage",
  "objection",
  "counterexample",
  "evidence"
 ]
}
