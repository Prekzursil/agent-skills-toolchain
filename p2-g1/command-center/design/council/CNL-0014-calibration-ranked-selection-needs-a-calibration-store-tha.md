{
  "schema_version": 1,
  "report_kind": "council-design-note",
  "unit_id": "CNL-0014",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0014",
  "completion_sentinel": "SUCCESS:CNL-0014",
  "title": "Calibration-ranked selection needs a calibration store that does not exist yet",
  "question": "Calibration-ranked participant selection presupposes a per-participant calibration history - what is the minimum store schema, how is it populated on cold start without inventing scores, and what does the selector do for a participant with zero history?",
  "spec_anchor": "command-center/WORK-UNIT-CATALOG.json:35000",
  "produced_by": {
    "vendor": "cursor",
    "model": "grok-4.6",
    "role": "council-systems-designer",
    "execution_substrate": "headless-linux"
  },
  "ts": "2026-08-25T00:55:23Z",
  "dependencies_on_this_tree": {
    "CNL-0005_artifact_present": false,
    "CNL-0074_artifact_present": false,
    "note": "Neither dependency artifact is on this worktree. This unit still specifies the store because the question is that the store does not exist yet; cold-start is the live operational mode."
  },
  "inputs_on_this_tree": {
    "11-COUNCIL-SPECIFICATION.schema.json": false,
    "12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "platform/schema/councilspec.schema.json": true,
    "command-center/schema/councilspec.v2.schema.json": true,
    "command-center/design/council/CNL-0005-participant-descriptor-type-the-9-per-seat-dials.md": false,
    "command-center/design/council/CNL-0074-confidence-trajectory-and-the-post-run-calibration-report.md": false
  },
  "answer": "Minimum store is council-calibration-store/v1: per (participant_id, task_class) an append-only outcomes list, derived resolved_n, scoreable, brier, and rank_class. Brier is the mean squared error of stated_confidence versus resolved_correct on SCOREABLE rows only; it is null whenever resolved_n < min_resolved_n (default 1). Cold start writes UNRANKABLE identity stubs with outcomes=[] and never a numeric score. UNSCOREABLE rows (no ground truth, the CNL-0074 path) do not increment resolved_n. The calibration-ranked selector ranks only RANK_ELIGIBLE rows by ascending Brier and leaves zero-history participants in unrankable with reason ZERO_HISTORY; it does not impute the pool mean, 0.5, or any other average, and it does not silently switch method when the ranked list is empty. On this worktree the mixed fixture ranks ['alice', 'bob'] and leaves ['cara', 'drew'] UNRANKABLE. The planted-average selector assigns the scored-pool mean 0.28541666666666665 to cara/drew, which lets cara outrank bob \u2014 the defect the detector is built to catch.",
  "decision": {
    "summary": "Use council-calibration-store/v1 with append-only SCOREABLE outcomes, null brier at cold start, and UNRANKABLE ranking for zero-history participants; never impute the pool mean or 0.5.",
    "zero_history": "UNRANKABLE, not average",
    "cold_start": "identity stubs, no invented scores"
  },
  "store_schema": {
    "id": "council-calibration-store/v1",
    "path": "command-center/p2-wave/probes/CNL-0014/store.schema.json",
    "min_fields": [
      "schema_id",
      "min_resolved_n",
      "records[].participant_id",
      "records[].task_class",
      "records[].resolved_n",
      "records[].outcomes",
      "records[].scoreable",
      "records[].brier",
      "records[].rank_class"
    ],
    "invariants": [
      "resolved_n equals the count of SCOREABLE outcomes, not the list length",
      "if resolved_n < min_resolved_n then scoreable=false, brier=null, rank_class=UNRANKABLE",
      "SCOREABLE outcomes require boolean resolved_correct and a non-empty resolution_source",
      "UNSCOREABLE outcomes must not carry resolved_correct and must not mint a brier",
      "the store never writes a prior, pool mean, or 0.5 in place of a measured brier"
    ]
  },
  "cold_start_policy": "Create an empty store document (records=[]). The first time a candidate is seen, insert an identity row via observe_candidate with outcomes=[], resolved_n=0, brier=null, rank_class=UNRANKABLE. Do not copy industry averages, peer means, or uninformative priors into brier. Population after cold start is append-only SCOREABLE outcomes from a post-run calibration report (CNL-0074) that carries a resolution_source. That report is absent on this tree; the store stays empty of scores until such rows exist.",
  "zero_history_policy": "Zero-history participants are UNRANKABLE. They must NOT be ranked as average by default. The calibration-ranked selector returns them only in the unrankable pool with reason ZERO_HISTORY, brier=null, and never switches method to invent a roster. A higher-layer composer (CNL-0013) may seat them under a different named method; that method change must be recorded, not hidden inside calibration-rank.",
  "cold_start": {
    "ranked_count": 0,
    "unrankable_count": 4,
    "switched_method": false,
    "sets": {
      "zero_history_ids": [
        "alice",
        "bob",
        "cara",
        "drew"
      ],
      "ranked_ids": [],
      "overlap": [],
      "disjoint": true
    },
    "imputed_would_rank": 4,
    "impute_source": "uninformative-0.5",
    "imputed_average": 0.5
  },
  "mixed_history": {
    "ranked_ids": [
      "alice",
      "bob"
    ],
    "unrankable_ids": [
      "cara",
      "drew"
    ],
    "alice_brier": 0.05666666666666667,
    "bob_brier": 0.5141666666666667,
    "cara_resolved_n": 0,
    "cara_rank_class": "UNRANKABLE",
    "sets": {
      "zero_history_ids": [
        "cara",
        "drew"
      ],
      "ranked_ids": [
        "alice",
        "bob"
      ],
      "overlap": [],
      "disjoint": true
    },
    "imputed_ranked_ids": [
      "alice",
      "cara",
      "drew",
      "bob"
    ],
    "imputed_average": 0.28541666666666665,
    "cara_beats_bob_under_imputation": true
  },
  "both_states": {
    "on_known_good": "SILENT",
    "on_planted_bad": "FIRES",
    "discriminates": true,
    "known_good_finding_count": 0,
    "planted_bad_finding_count": 8,
    "verbatim_mixed": "both-states-mixed silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=8 discriminates=True",
    "verbatim_cold": "both-states-cold silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=16 discriminates=True",
    "planted_bad_is": "rank_with_average_imputation assigns the scored-pool mean (or 0.5 on total cold start) to every participant with resolved_n=0 and places them on the ranked roster"
  },
  "claims": [
    {
      "id": "C1",
      "claim": "A minimum store schema exists that refuses a numeric brier when resolved_n=0.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/store.py:47"
    },
    {
      "id": "C2",
      "claim": "Cold start populates UNRANKABLE identity rows and yields an empty ranked list.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/selector.py:37"
    },
    {
      "id": "C3",
      "claim": "Zero-history participants must NOT be ranked as average; the selector marks them UNRANKABLE.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/detector.py:20"
    },
    {
      "id": "C4",
      "claim": "11-COUNCIL-SPECIFICATION.schema.json on this worktree already defines this store.",
      "verdict": "REFUTED",
      "anchor": "inputs_on_this_tree.11-COUNCIL-SPECIFICATION.schema.json=false"
    },
    {
      "id": "C5",
      "claim": "Treating missing history as the pool mean is a harmless default.",
      "verdict": "REFUTED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/detector.py:20"
    }
  ],
  "evidence": [
    {
      "claim": "Set algebra over raw SCOREABLE counts vs ranked ids is empty for the honest selector and non-empty for average-imputation.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/selector.py:disjoint_zero_history",
      "mechanism": "python set intersection on resolved_n counted from outcomes[] (not rank_class)",
      "command_or_anchor": "python3 -B command-center/p2-wave/probes/CNL-0014/probe1_cold_start.py",
      "verbatim": "set-algebra cold overlap=[] disjoint=True mixed overlap=[] disjoint=True ranked=['alice', 'bob']"
    },
    {
      "claim": "The detector is SILENT on the honest ranking and FIRES on planted mean-imputation, including the cold-start 0.5 default.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/detector.py:20",
      "mechanism": "both-states ranking-document inspection (finding codes, not set algebra)",
      "command_or_anchor": "python3 -B command-center/p2-wave/probes/CNL-0014/probe2_both_states.py",
      "verbatim": "both-states-mixed silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=8 discriminates=True | both-states-cold silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=16 discriminates=True"
    },
    {
      "claim": "Store validator accepts the mixed fixture and rejects a planted brier=0.5 at resolved_n=0.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0014/store.schema.json",
      "mechanism": "jsonschema Draft7 plus derived-field invariants",
      "command_or_anchor": "command-center/p2-wave/probes/CNL-0014/store.schema.json",
      "verbatim": "store-gate known_good_accepted=True planted_invented_rejected=True invented_errors=['derived-mismatch:alice', 'INVENTED_SCORE:alice', 'INVENTED_SCORE_ZERO_HISTORY:alice', 'ZERO_HISTORY_MARKED_ELIGIBLE:alice']"
    }
  ],
  "tests": [
    {
      "id": "T-COLD-START",
      "name": "zero-history participants must NOT be ranked as average",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0014/probe1_cold_start.py",
      "result": "PASS"
    },
    {
      "id": "T-BOTH-STATES",
      "name": "detector FIRES on planted-average and is SILENT on known-good",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0014/probe2_both_states.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-AVERAGE-IMPUTATION",
      "rejects": "a ranking that assigns the scored-pool mean or uninformative 0.5 to participants with resolved_n=0 and places them on the ranked roster",
      "observed": "SILENT on known-good honest ranking; FIRES on planted-average. both-states-mixed silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=8 discriminates=True",
      "on_known_good": "SILENT",
      "on_planted_bad": "FIRES",
      "verbatim": "the check FIRES when a zero-history participant is assigned the mean Brier of the scored pool (or 0.5 when the pool is empty) and placed on the ranked roster; it is SILENT when zero-history participants are UNRANKABLE, brier=null, and absent from ranked. both-states-mixed silent_on_good=True fires_on_bad=True good_findings=0 bad_findings=8 discriminates=True"
    },
    {
      "id": "NC-INVENTED-STORE-ROW",
      "rejects": "a store record with resolved_n=0 and brier=0.5 / RANK_ELIGIBLE",
      "observed": "store-gate known_good_accepted=True planted_invented_rejected=True invented_errors=['derived-mismatch:alice', 'INVENTED_SCORE:alice', 'INVENTED_SCORE_ZERO_HISTORY:alice', 'ZERO_HISTORY_MARKED_ELIGIBLE:alice']",
      "on_known_good": "SILENT",
      "on_planted_bad": "FIRES",
      "verbatim": "store-gate known_good_accepted=True planted_invented_rejected=True invented_errors=['derived-mismatch:alice', 'INVENTED_SCORE:alice', 'INVENTED_SCORE_ZERO_HISTORY:alice', 'ZERO_HISTORY_MARKED_ELIGIBLE:alice']"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0014-probe2-both-states",
    "verdict": "PASS",
    "independent": true,
    "scope_not_agreement": true,
    "counterexample": "Instance: mixed fixture + rank_with_average_imputation. cara has only an UNSCOREABLE outcome (resolved_n=0) and receives the pool mean 0.28541666666666665, which ranks her above bob (brier=0.5141666666666667). Honest selector does not emit that roster; detector findings include ZERO_HISTORY_RANKED."
  },
  "schema_controls": {
    "design_note_garbage_rejected": {
      "n": 3,
      "rejected": 3,
      "details": [
        {
          "rejected": true,
          "n_errors": 8
        },
        {
          "rejected": true,
          "n_errors": 7
        },
        {
          "rejected": true,
          "n_errors": 8
        }
      ]
    },
    "store_garbage_rejected": {
      "n": 3,
      "rejected": 3,
      "details": [
        {
          "rejected": true,
          "n_errors": 4
        },
        {
          "rejected": true,
          "n_errors": 4
        },
        {
          "rejected": true,
          "n_errors": 4
        }
      ]
    },
    "catalog_output_schema": {
      "path": "command-center/schema/council-design-note.schema.json",
      "generated_shim": true,
      "remote_ref_not_resolved": true,
      "local_probe_contract_used": true
    }
  },
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0014-calibration-ranked-selection-needs-a-calibration-store-tha.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0014/store.schema.json",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0014/store.py",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0014/selector.py",
      "exists": true,
      "role": "supporting"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0014/detector.py",
      "exists": true,
      "role": "supporting"
    }
  ],
  "named_probes": [
    {
      "id": "probe1",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0014/probe1_cold_start.py",
      "role": "cold-start-zero-history"
    },
    {
      "id": "probe2",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0014/probe2_both_states.py",
      "role": "both-states-average-imputation"
    }
  ]
}
