{
  "answer": "Yes, if and only if every published weighted result carries an equal-weight counterfactual on the same frozen seated set, a numeric weighting_delta, and a boolean weighting_flip. The counterfactual re-scores every seated ballot at weight 1 without dropping seats. A result that omits the counterfactual is unpublished, not audited. A flip is a disclosure that weighting changed the winner or threshold-status; it does not by itself void the decision. Catalog Windows inputs and CNL-0023/CNL-0058 artifacts are not on this tree; this note consumes their interfaces rather than claiming those units are delivered.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0064-weighted-voting-weight-provenance-and-post-hoc-audit.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0064/note.schema.json",
      "role": "unit-local-schema"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "catalog-declared-schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0064/tabulate.py",
      "role": "author-tabulator"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0064/recount.py",
      "role": "independent-recount"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0064/publication.py",
      "role": "publication-detector"
    }
  ],
  "catalog_inputs_on_tree": {
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/11-COUNCIL-SPECIFICATION.schema.json": false,
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json": false,
    "C:/Users/Prekzursil/.claude/harness-restore-20260806/_USER-PROMPTS.md": false
  },
  "claim_under_test": "A decided weighted council is not publishable unless an auditor can recompute the equal-weight counterfactual from the same ballots and read a published delta plus flip flag beside the result.",
  "claims": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0064/tabulate.py:190",
      "claim": "Every non-rejected weighted fixture publishes an equal-weight counterfactual computed from the same seated ballots.",
      "id": "C1",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0064/tabulate.py:190",
      "claim": "A decision whose winner or threshold-status changes under equal weights is flagged weighting_flip=true; a stable weighted majority is flagged false but still carries the delta.",
      "id": "C2",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0064/recount.py:60",
      "claim": "An independent grouped-list recount agrees with the running-total tabulator on winner, status, and flip for every council fixture.",
      "id": "C3",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0064/publication.py:49",
      "claim": "A published weighted result that omits the counterfactual is rejected by the publication check; a complete audit is silent.",
      "id": "C4",
      "verdict": "CONFIRMED"
    }
  ],
  "decision_rule": {
    "equal_denominator": "seated count",
    "equal_weight_unit": "1",
    "flip": "winner inequality or status inequality",
    "provenance_required_when": "seat weight != 1",
    "weighted_denominator": "sum of seated weights"
  },
  "declared_signal": {
    "denominator_rule": "weighted threshold uses seated_weight; equal-weight threshold uses seated_count; seated set is frozen",
    "flip_rule": "weighting_flip is true iff weighted winner differs from equal-weight winner OR weighted status differs from equal-weight status",
    "name": "weighting_audit",
    "required_fields": [
      "weighted_result",
      "equal_weight_counterfactual",
      "weighting_delta",
      "weighting_flip"
    ]
  },
  "dependency_status": {
    "CNL-0023": {
      "artifact_present": false,
      "path": "command-center/design/council/CNL-0023-vote-rights-and-the-provenance-of-every-non-equal-weight.md",
      "role": "pre-run provenance gate for non-unit weights"
    },
    "CNL-0058": {
      "artifact_present": false,
      "path": "command-center/design/council/CNL-0058-majority-supermajority-and-their-interaction-with-quorum.md",
      "role": "threshold denominator freeze / quorum interaction"
    }
  },
  "evidence": [
    {
      "claim": "equal-weight re-score is implemented, not asserted",
      "kind": "running-total-tabulator",
      "line": 190,
      "path": "command-center/p2-wave/probes/CNL-0064/tabulate.py",
      "snippet": "Equal-weight counterfactual: every seated ballot is re-scored at weight 1."
    },
    {
      "claim": "reviewer sums grouped weights without importing tabulate",
      "kind": "grouped-list-recount",
      "line": 60,
      "path": "command-center/p2-wave/probes/CNL-0064/recount.py",
      "snippet": "Map option -> list of contributing weights (not a running total)."
    },
    {
      "claim": "omitted counterfactual is a detectable publication defect",
      "kind": "publication-detector",
      "line": 49,
      "path": "command-center/p2-wave/probes/CNL-0064/publication.py",
      "snippet": "True when the publication check rejects the document."
    }
  ],
  "fixture_results": [
    {
      "equal_status": "PLURALITY",
      "equal_weight_counterfactual": {
        "denominator": "3/1",
        "leading_ratio": "2/3",
        "scores": {
          "adopt": "2/1",
          "reject": "1/1"
        },
        "seated_count": 3,
        "seated_weight": "3/1",
        "status": "PLURALITY",
        "winner": "adopt"
      },
      "equal_winner": "adopt",
      "expect_flip": false,
      "id": "equal-weight",
      "rejected": false,
      "weighted_result": {
        "denominator": "3/1",
        "leading_ratio": "2/3",
        "scores": {
          "adopt": "2/1",
          "reject": "1/1"
        },
        "seated_count": 3,
        "seated_weight": "3/1",
        "status": "PLURALITY",
        "winner": "adopt"
      },
      "weighted_status": "PLURALITY",
      "weighted_winner": "adopt",
      "weighting_delta": {
        "excess_weight_on_weighted_winner": "0/1",
        "score_shift": {
          "adopt": "0/1",
          "reject": "0/1"
        },
        "status_changed": false,
        "winner_changed": false
      },
      "weighting_flip": false
    },
    {
      "equal_weight_counterfactual": null,
      "equal_winner": null,
      "id": "missing-provenance",
      "reject_code": "MISSING_PROVENANCE",
      "rejected": true,
      "weighted_winner": null,
      "weighting_flip": null
    },
    {
      "equal_status": "TIE",
      "equal_weight_counterfactual": {
        "denominator": "4/1",
        "leading_ratio": "1/2",
        "scores": {
          "adopt": "2/1",
          "reject": "2/1"
        },
        "seated_count": 4,
        "seated_weight": "4/1",
        "status": "TIE",
        "winner": null
      },
      "equal_winner": null,
      "expect_flip": true,
      "id": "threshold-flip",
      "rejected": false,
      "weighted_result": {
        "denominator": "8/1",
        "leading_ratio": "3/4",
        "scores": {
          "adopt": "6/1",
          "reject": "2/1"
        },
        "seated_count": 4,
        "seated_weight": "8/1",
        "status": "THRESHOLD-PASS",
        "winner": "adopt"
      },
      "weighted_status": "THRESHOLD-PASS",
      "weighted_winner": "adopt",
      "weighting_delta": {
        "excess_weight_on_weighted_winner": "4/1",
        "score_shift": {
          "adopt": "4/1",
          "reject": "0/1"
        },
        "status_changed": true,
        "winner_changed": true
      },
      "weighting_flip": true
    },
    {
      "equal_status": "PLURALITY",
      "equal_weight_counterfactual": {
        "denominator": "3/1",
        "leading_ratio": "2/3",
        "scores": {
          "adopt": "1/1",
          "reject": "2/1"
        },
        "seated_count": 3,
        "seated_weight": "3/1",
        "status": "PLURALITY",
        "winner": "reject"
      },
      "equal_winner": "reject",
      "expect_flip": true,
      "id": "weighted-flip",
      "rejected": false,
      "weighted_result": {
        "denominator": "7/1",
        "leading_ratio": "5/7",
        "scores": {
          "adopt": "5/1",
          "reject": "2/1"
        },
        "seated_count": 3,
        "seated_weight": "7/1",
        "status": "PLURALITY",
        "winner": "adopt"
      },
      "weighted_status": "PLURALITY",
      "weighted_winner": "adopt",
      "weighting_delta": {
        "excess_weight_on_weighted_winner": "4/1",
        "score_shift": {
          "adopt": "4/1",
          "reject": "0/1"
        },
        "status_changed": false,
        "winner_changed": true
      },
      "weighting_flip": true
    },
    {
      "equal_status": "PLURALITY",
      "equal_weight_counterfactual": {
        "denominator": "3/1",
        "leading_ratio": "2/3",
        "scores": {
          "adopt": "2/1",
          "reject": "1/1"
        },
        "seated_count": 3,
        "seated_weight": "3/1",
        "status": "PLURALITY",
        "winner": "adopt"
      },
      "equal_winner": "adopt",
      "expect_flip": false,
      "id": "weighted-stable",
      "rejected": false,
      "weighted_result": {
        "denominator": "6/1",
        "leading_ratio": "5/6",
        "scores": {
          "adopt": "5/1",
          "reject": "1/1"
        },
        "seated_count": 3,
        "seated_weight": "6/1",
        "status": "PLURALITY",
        "winner": "adopt"
      },
      "weighted_status": "PLURALITY",
      "weighted_winner": "adopt",
      "weighting_delta": {
        "excess_weight_on_weighted_winner": "3/1",
        "score_shift": {
          "adopt": "3/1",
          "reject": "0/1"
        },
        "status_changed": false,
        "winner_changed": false
      },
      "weighting_flip": false
    }
  ],
  "negative_controls": [
    {
      "id": "NC-equal-weight",
      "rejects": "an enumerator that flags weighting_flip on an all-weight-1 council",
      "verbatim": "negative-control target=equal-weight weighting_flip=false excess=0/1 rejected=False. If weighting_flip were true, the flip enumerator would be wrong."
    },
    {
      "id": "NC-missing-provenance",
      "rejects": "a non-unit weight with no provenance record",
      "verbatim": "negative-control target=missing-provenance rejected=True code=MISSING_PROVENANCE. The check fires before any score is accumulated."
    },
    {
      "id": "NC-unpublished-delta",
      "rejects": "a weighted result published without the equal-weight audit",
      "verbatim": "unpublished_fires=True on fixture unpublished-delta, which carries weighted_result only. Complete weighted-stable audit is silent."
    }
  ],
  "output_schema_catalog": "command-center/schema/council-design-note.schema.json",
  "output_schema_validated_against": "command-center/p2-wave/probes/CNL-0064/note.schema.json",
  "question": "Given a decided council, can an auditor recompute the outcome under equal weights and see how much of the decision the weighting alone produced - and is that delta published with the result?",
  "residual": "CNL-0023 and CNL-0058 artifacts are absent on this worktree. The provenance gate and frozen-denominator rule are implemented here as consumed interfaces, not as a claim that those units are delivered. Harness restore files named in the catalog inputs are not on this Linux tree.",
  "reviewer": {
    "independent": true,
    "method": "recount.py groups ballots by option then sums; publication.py fires on unpublished-delta and is silent on weighted-stable",
    "re_ran_both_states": true,
    "reviewer_id": "CNL-0064-probe2-grouped-recount",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0064",
  "shared_schema_note": "Catalog names command-center/schema/council-design-note.schema.json. That file is a generated $ref shim to ast-integrate.invalid; Draft7Validator on this image raises RefResolutionError (no network). This note is validated against the unit-local schema so the negative_controls mutant is a real rejection rather than a fetch error.",
  "state": "SUCCESS",
  "strongest_surviving_counterargument": "Publishing the flip does not force any consumer to treat a weight-driven winner as illegitimate; a later gate could ignore the audit fields. This unit requires publication and detection of omission, not a downstream halt. Consumption of the flag is a later unit.",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0064/probe1_counterfactual.py",
      "id": "probe1",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0064/probe2_negative_control.py",
      "id": "probe2",
      "result": "PASS"
    }
  ],
  "title": "Weighted voting: weight provenance and post-hoc audit",
  "unit_id": "CNL-0064",
  "which_stops_the_round": {
    "does_not_stop": "a non-zero score delta that leaves winner and threshold-status unchanged; that is disclosed, not a halt",
    "satisfy_quota_from_padding": false,
    "stops": "publishing a weighted decision without equal_weight_counterfactual, or publishing weighting_flip false/absent when winner or status changes under equal weights"
  }
}
