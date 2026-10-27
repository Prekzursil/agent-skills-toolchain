{
  "unit_id": "CNL-0018",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0018",
  "completion_sentinel": "SUCCESS:CNL-0018",
  "format": "council-design-note/v1+json",
  "title": "Model and vendor diversity selection under a real quota ceiling",
  "question": "Cross-vendor seats consume a SECOND paid subscription - what diversity objective is worth that spend, at what council risk tier does vendor diversity become mandatory rather than optional, and what happens when the quota for the second vendor is exhausted mid-council?",
  "answers": {
    "diversity_objective": "The second paid subscription is worth the spend only as a second failure domain: a vendor that does not share the first vendor's outage, safety-layer, training-correlation, or quota pool. Costume diversity (two labels on one base model, or two models on one vendor) is not that objective and is not vendor-diverse.",
    "mandatory_from_risk_tier": "high-stakes",
    "quota_exhaustion": "When the second vendor's remaining-call counter hits zero mid-council the runtime emits a loud QUOTA-EXHAUSTED event, freezes the partial transcript as the artifact, marks independence_void, and refuses to pad the roster with another seat of a vendor already present. At high-stakes/irreversible the council stops in DEGRADED rather than continuing as if independent. It never silently re-seats the same vendor twice.",
    "worth_the_spend": "Independence is the only diversity objective that justifies a second subscription. Procurement of that subscription is not authorized by this note; this note specifies when a seated council must USE a second vendor (mandatory from high-stakes) and what happens if that vendor's quota is exhausted."
  },
  "risk_tiers": {
    "enum": [
      "discovery",
      "standard",
      "high-stakes",
      "irreversible"
    ],
    "discovery": "optional \u2014 single-vendor may run; independence waiver recorded",
    "standard": "recommended \u2014 missing diversity is a recorded waiver, council may run",
    "high-stakes": "mandatory \u2014 refuse to start if not vendor-diverse; quota exhaustion degrades loudly and stops",
    "irreversible": "mandatory \u2014 same seating rule as high-stakes; exhaustion still preserves the partial artifact",
    "mandatory_from": "high-stakes"
  },
  "vendor_diversity_predicate": {
    "rule": "vendor_diverse iff distinct_vendors>=2 AND distinct_base_models>=2 AND no base_model seated twice",
    "same_base_model_twice_is_not_vendor_diverse": true,
    "computed": {
      "diverse": {
        "vendor_diverse": true,
        "same_base_model_twice": false,
        "reason": "vendor-diverse",
        "distinct_vendors": [
          "anthropic",
          "openai"
        ],
        "distinct_base_models": [
          "claude-opus",
          "gpt-4o"
        ],
        "duplicate_base_models": [],
        "vendor_counts": {
          "anthropic": 1,
          "openai": 1
        },
        "base_model_counts": {
          "claude-opus": 1,
          "gpt-4o": 1
        },
        "seat_count": 2
      },
      "same_base_twice": {
        "vendor_diverse": false,
        "same_base_model_twice": true,
        "reason": "same-base-model-twice",
        "distinct_vendors": [
          "anthropic"
        ],
        "distinct_base_models": [
          "claude-opus"
        ],
        "duplicate_base_models": [
          "claude-opus"
        ],
        "vendor_counts": {
          "anthropic": 2
        },
        "base_model_counts": {
          "claude-opus": 2
        },
        "seat_count": 2
      },
      "same_base_cross_vendor": {
        "vendor_diverse": false,
        "same_base_model_twice": true,
        "reason": "same-base-model-twice",
        "distinct_vendors": [
          "azure",
          "openai"
        ],
        "distinct_base_models": [
          "gpt-4o"
        ],
        "duplicate_base_models": [
          "gpt-4o"
        ],
        "vendor_counts": {
          "azure": 1,
          "openai": 1
        },
        "base_model_counts": {
          "gpt-4o": 2
        },
        "seat_count": 2
      },
      "same_vendor_diff_model": {
        "vendor_diverse": false,
        "same_base_model_twice": false,
        "reason": "single-vendor",
        "distinct_vendors": [
          "anthropic"
        ],
        "distinct_base_models": [
          "claude-opus",
          "claude-sonnet"
        ],
        "duplicate_base_models": [],
        "vendor_counts": {
          "anthropic": 2
        },
        "base_model_counts": {
          "claude-opus": 1,
          "claude-sonnet": 1
        },
        "seat_count": 2
      }
    }
  },
  "quota_exhaustion_control": {
    "declared_before_scoring": {
      "n_rounds": 3,
      "quota_bad": {
        "anthropic": 100,
        "openai": 1
      },
      "quota_good": {
        "anthropic": 100,
        "openai": 100
      }
    },
    "bad_fired": true,
    "good_silent": true,
    "turns_preserved_on_bad": 3,
    "reseated_same_vendor": false,
    "substitution_refused": true,
    "bad_terminal": "DEGRADED",
    "good_terminal": "SUCCESS",
    "independent_recount_turns_before": 3
  },
  "diversity_control": {
    "same_base_twice_flagged": true,
    "diverse_accepted": true,
    "cross_vendor_same_base_flagged": true,
    "mandatory_same_base_action": "refuse",
    "optional_same_base_action": "seat-with-waiver"
  },
  "owner_gate": {
    "catalog_requires_approval": true,
    "owner_decisions_md_present": true,
    "new_spend_default_guessed": false,
    "new_dollar_or_remaining_quota_default": null,
    "how_discharged": "The owner gate forbids guessing a spend/quota default. This note does not guess one. Diversity objective and exhaustion behaviour are derived from cited standing positions (independence; quota as scheduler input; cost does not lower rigor). Whether to purchase a second subscription is a procurement question and is NOT-CHECKED. OWNER-DECISIONS.md is absent on this worktree and is not forged.",
    "standing_positions": [
      "multiple providers/models for independence when permitted",
      "treat quota and arrival rate as scheduler inputs",
      "resource cost is not a reason to lower rigor"
    ]
  },
  "inputs_live": {
    "user_prompts_md": false,
    "council_specification_schema": true,
    "cnl_0005_artifact_present": false,
    "owner_decisions_md": true,
    "surrogate_for_10579": "command-center/p2-wave/probes/WFA-0042/_validate_out.json around_10723 harvest of _USER-PROMPTS.md"
  },
  "claims": [
    {
      "id": "C1",
      "claim": "Independence is the diversity objective that justifies a second paid vendor.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json:254"
    },
    {
      "id": "C2",
      "claim": "Vendor diversity is mandatory from risk tier high-stakes.",
      "verdict": "CONFIRMED",
      "anchor": "command-center/p2-wave/probes/CNL-0018/mechanism.py"
    },
    {
      "id": "C3",
      "claim": "Mid-council quota exhaustion degrades loudly, preserves the partial artifact, and refuses same-vendor reseat.",
      "verdict": "CONFIRMED",
      "anchor": "quota_exhaustion_control"
    },
    {
      "id": "C4",
      "claim": "Same-base-model-twice rosters are not vendor-diverse, including cross-vendor label pairs.",
      "verdict": "CONFIRMED",
      "anchor": "diversity_control"
    },
    {
      "id": "C5",
      "claim": "Live remaining-quota / dollar cost of a second subscription on this estate.",
      "verdict": "NOT-CHECKED",
      "reason": "No live vendor quota or price was measured. Fixture integers are declared test counters, not production remaining-calls."
    },
    {
      "id": "C6",
      "claim": "Verbatim read of _USER-PROMPTS.md:10579 and 11-COUNCIL-SPECIFICATION.schema.json on this Linux worktree.",
      "verdict": "NOT-CHECKED",
      "reason": "Those Windows restore paths are absent here. The independence/budget-pacing sentences are cited from the WFA-0042 harvest of that file."
    }
  ],
  "tests": [
    {
      "id": "probe1-quota-exhaustion",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0018/probe1_quota_exhaustion.py",
      "result": "PASS"
    },
    {
      "id": "probe2-same-base-model",
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0018/probe2_same_base_model.py",
      "result": "PASS"
    }
  ],
  "negative_controls": [
    {
      "id": "NC-quota",
      "rejects": "silent same-vendor reseat after exhaustion",
      "verbatim": "NEGATIVE CONTROL (quota): the check FIRES on planted exhaustion (openai remaining=1, 3 rounds) with 1 QUOTA-EXHAUSTED event(s), preserves the partial transcript (3 turns), and refuses same-vendor reseat (1 SUBSTITUTION-REFUSED). The check is SILENT on the known-good remaining map (both vendors=100): zero QUOTA-EXHAUSTED events, terminal=SUCCESS, independence_void=False."
    },
    {
      "id": "NC-diversity",
      "rejects": "same-base-model-twice counted as vendor-diverse",
      "verbatim": "NEGATIVE CONTROL (diversity): the check FIRES on a same-base-model-twice roster (two claude-opus seats; vendor_diverse=false, same_base_model_twice=true, reason=same-base-model-twice) and is SILENT on the known-good roster (anthropic/claude-opus + openai/gpt-4o; vendor_diverse=true). It also FIRES on openai/gpt-4o + azure/gpt-4o (distinct vendor labels, same base model) so vendor-string makeup cannot game the metric."
    }
  ],
  "evidence": [
    {
      "path": "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
      "line": 254,
      "snippet": "Use multiple providers/models for independence when permitted",
      "kind": "harvested-prompt",
      "claim": "Standing owner text names independence, not costume diversity, as the reason to use multiple providers.",
      "anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json:254"
    },
    {
      "path": "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
      "line": 253,
      "snippet": "Treat quota and arrival rate as scheduler inputs.",
      "kind": "harvested-prompt",
      "claim": "Standing budget-pacing position: quota is a scheduler input, not a reason to silently substitute seats.",
      "anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json:253"
    },
    {
      "path": "command-center/p2-wave/probes/WFA-0042/_validate_out.json",
      "line": 259,
      "snippet": "Resource cost is not a reason to lower rigor. It is a reason to choose a safer execution substrate.",
      "kind": "harvested-prompt",
      "claim": "Standing budget-pacing position: cost does not lower rigor; exhaustion degrades or stops, it does not pad the roster.",
      "anchor": "command-center/p2-wave/probes/WFA-0042/_validate_out.json:259"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35200,
      "snippet": "a quota-exhaustion fixture mid-council must degrade loudly and preserve the partial artifact, never silently re-seat the same vendor twice",
      "kind": "catalog",
      "claim": "Catalog test requires loud degrade, partial preservation, and no same-vendor reseat.",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35200"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35201,
      "snippet": "a same-base-model-twice roster must be flagged as NOT vendor-diverse",
      "kind": "catalog",
      "claim": "Catalog test requires same-base-model-twice to fail the vendor-diversity check.",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35201"
    },
    {
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "line": 35178,
      "snippet": "emit NOT-CHECKED for any quota figure not actually measured",
      "kind": "catalog",
      "claim": "Catalog evidence rule: unmeasured quota figures stay NOT-CHECKED.",
      "anchor": "command-center/WORK-UNIT-CATALOG.json:35178"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0018/mechanism.py",
      "line": 30,
      "snippet": "MANDATORY_FROM_TIER = \"high-stakes\"",
      "kind": "live-tree",
      "claim": "Executable seating rule: vendor diversity is mandatory from high-stakes upward.",
      "anchor": "command-center/p2-wave/probes/CNL-0018/mechanism.py:30"
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0018-probe2-same-base-model-recount",
    "verdict": "PASS",
    "independent": true,
    "method": "Mechanical re-derivation: Counter over fixtures/declared.json base_model fields, plus jsonschema garbage rejection. Does not take the author's prose as evidence.",
    "scope_not_agreement": true
  },
  "schema_note": "Catalog output_schema is command-center/schema/council-design-note.schema.json, a generated $ref shim to ast-integrate.invalid. This unit does not rebuild that shared file. Validation uses the per-unit schema.",
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0018-model-and-vendor-diversity-selection-under-a-real-quota-ce.md",
      "exists": true,
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0018/council-design-note.schema.json",
      "exists": true,
      "role": "unit-local-schema"
    },
    {
      "path": "command-center/schema/council-design-note.schema.json",
      "exists": true,
      "role": "catalog-named-schema-shim"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0018/mechanism.py",
      "exists": true,
      "role": "mechanism"
    }
  ],
  "residual_unknowns": [
    "Live remaining-call counters per vendor: NOT-CHECKED.",
    "CNL-0005 nine-dial participant descriptor is not on disk; this note uses vendor/model/base_model only.",
    "OWNER-DECISIONS.md is absent; no new spend authorization is recorded."
  ]
}
