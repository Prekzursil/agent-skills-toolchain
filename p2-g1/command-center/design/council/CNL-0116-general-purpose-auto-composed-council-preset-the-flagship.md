{
  "unit_id": "CNL-0116",
  "state": "SUCCESS",
  "sentinel": "SUCCESS:CNL-0116",
  "completion_sentinel": "SUCCESS:CNL-0116",
  "title": "General-purpose auto-composed council preset (the flagship)",
  "question": "For an arbitrary owner request with no preset named, what does the auto-composer produce, how does it explain every dial it chose, and what is the owner's one-step override path?",
  "answer": "When the owner names no preset, the flagship C-GP01 auto-composer is the default_binding. It derives risk_tier from the task (or an explicit charter value), seats Orchestrator+Domain+Adversary+Evidence-auditor plus feature-triggered Legal/Security/Operator seats, binds a risk-tier protocol schedule, a matching vote rule and a declarative stopping expression, and emits a contestable explanation for every dial. The owner's one-step override path is owner.override(dial, value): one call records the override and re-derives unlocked dials. Naming a preset is also one-step and exits the flagship path. Silent edits and non-editable dials are rejected. Nearest sibling in the estate fixture is C-M01 (static general-purpose four-voice); the differential is auto-compose, mandatory explanation, recorded override, and a different roster/vote/stop \u2014 not the name. SUCCESS:CNL-0116",
  "preset": {
    "id": "C-GP01",
    "name": "flagship-auto-composed",
    "status": "DESIGN",
    "base_spec_ref": "CouncilSpec/v2",
    "default_binding": "auto-compose",
    "editable_dials": [
      "charter.risk_tier",
      "roles",
      "protocol_binding.schedule",
      "voting.rule",
      "stopping.max_rounds",
      "stopping.expression",
      "budgets.max_rounds",
      "evidence.standard"
    ],
    "charter": {
      "objective": "unspecified-owner-request",
      "risk_tier": "derived",
      "desired_output": "decision-with-explanation",
      "success_criteria": "every-dial-explained-and-contestable",
      "consensus_intent": "derived"
    },
    "participants": {
      "mode": "auto-compose",
      "min_seats": 4,
      "max_seats": 8
    },
    "roles": [
      "Orchestrator",
      "Domain",
      "Adversary",
      "Evidence-auditor"
    ],
    "engagement": {
      "style": "facilitated-deliberation",
      "asynchronous_ok": true
    },
    "budgets": {
      "max_rounds": "derived",
      "token_ceiling": "owner-constraint-or-default"
    },
    "evidence": {
      "standard": "derived",
      "untrusted_transcript": true
    },
    "voting": {
      "rule": "derived",
      "quorum": "derived"
    },
    "stopping": {
      "max_rounds": "derived",
      "expression": "derived",
      "on_timeout": "BLOCKED"
    },
    "outcomes": [
      "decision",
      "conditional-decision",
      "no-decision",
      "irreducible-disagreement",
      "dissent-with-minority-report",
      "proof-of-impossibility"
    ],
    "integrity": {
      "explanation_required": true,
      "silent_override_forbidden": true,
      "anti_failure": {
        "on_split": "surface-disagreement",
        "no_silent_average": true
      }
    },
    "artifacts": {
      "required": [
        "roster",
        "protocol_schedule",
        "voting",
        "stopping",
        "explanation",
        "overrides"
      ]
    },
    "execution": {
      "composer": "command-center/p2-wave/probes/CNL-0116/composer.py",
      "instantiate": "compose(task, risk_tier=None, override=None, named_preset=None)"
    },
    "protocol_binding": {
      "mode": "auto-compose",
      "schedule": "derived"
    },
    "meta": {
      "unit_id": "CNL-0116",
      "purpose_class": "general-unspecified-request",
      "supersedes": [
        "C-M01"
      ],
      "extends": [
        "council.preset.catalog-class.editable"
      ],
      "one_step_override": "owner.override(dial, value)",
      "explanation_required": true
    }
  },
  "auto_composer": {
    "module": "command-center/p2-wave/probes/CNL-0116/composer.py",
    "entry": "compose(task, risk_tier=None, override=None, named_preset=None)",
    "core_roles": [
      "Orchestrator",
      "Domain",
      "Adversary",
      "Evidence-auditor"
    ],
    "feature_seats": [
      "Legal",
      "Security",
      "Operator"
    ],
    "risk_tiers": [
      "low",
      "medium",
      "high",
      "critical"
    ],
    "unnamed_path_only": true,
    "twenty_keys": [
      "id",
      "name",
      "status",
      "base_spec_ref",
      "default_binding",
      "editable_dials",
      "charter",
      "participants",
      "roles",
      "engagement",
      "budgets",
      "evidence",
      "voting",
      "stopping",
      "outcomes",
      "integrity",
      "artifacts",
      "execution",
      "protocol_binding",
      "meta"
    ]
  },
  "one_step_override": {
    "path": "owner.override(dial, value)",
    "editable_dials": [
      "charter.risk_tier",
      "roles",
      "protocol_binding.schedule",
      "voting.rule",
      "stopping.max_rounds",
      "stopping.expression",
      "budgets.max_rounds",
      "evidence.standard"
    ],
    "locked_dials": [
      "default_binding",
      "id",
      "integrity.explanation_required",
      "integrity.silent_override_forbidden",
      "meta.explanation_required"
    ],
    "named_preset_exit": "owner.override('preset', '<id>') leaves flagship unused",
    "unsatisfiable_constraint": "BLOCKED, never a quiet relaxation (CNL-0004)"
  },
  "sibling": {
    "library": "command-center/p2-wave/probes/CNL-0116/fixtures/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "harness_restore_on_this_tree": false,
    "catalog_cited_preset_count": 72,
    "fixture_preset_count": 3,
    "nearest_named": "C-M01",
    "distance": {
      "integer_axes": 6,
      "differed": [
        "roles",
        "protocol_schedule",
        "voting_rule",
        "stopping_expression",
        "binding",
        "explanation_mandatory"
      ],
      "role_jaccard_distance": 1.0,
      "name_only": false,
      "a_id": "C-GP01",
      "b_id": "C-M01"
    },
    "supersedes": [
      "C-M01"
    ],
    "extends": [
      "council.preset.catalog-class.editable"
    ],
    "name_only_duplicate_rejected": true
  },
  "worked_example": {
    "task_id": "T-PROD-GNG",
    "task": "Ship a cache invalidation change to the production API. Need a go/no-go. No council preset named.",
    "instance": {
      "roles": [
        "Orchestrator",
        "Domain",
        "Adversary",
        "Evidence-auditor",
        "Operator"
      ],
      "protocol_schedule": [
        "intake",
        "independent-draft",
        "red-team",
        "synthesis",
        "vote",
        "owner-checkpoint"
      ],
      "voting": {
        "rule": "unanimous-or-escalate",
        "quorum": 5
      },
      "stopping": {
        "max_rounds": 12,
        "expression": "consensus OR owner_checkpoint OR round>=12",
        "on_timeout": "BLOCKED"
      },
      "risk_tier": "high",
      "binding": "auto-compose",
      "override_path": "owner.override(dial, value)",
      "explanation_count": 15
    },
    "fingerprint": {
      "roles": [
        "Adversary",
        "Domain",
        "Evidence-auditor",
        "Operator",
        "Orchestrator"
      ],
      "protocol_schedule": [
        "intake",
        "independent-draft",
        "red-team",
        "synthesis",
        "vote",
        "owner-checkpoint"
      ],
      "voting_rule": "unanimous-or-escalate",
      "stopping_expression": "consensus OR owner_checkpoint OR round>=12",
      "binding": "auto-compose",
      "explanation_mandatory": true,
      "purpose_class": "general-unspecified-request",
      "id": "C-GP01"
    }
  },
  "tests": [
    {
      "id": "instantiate-fixture-task",
      "probe": "probe1_instantiate.py",
      "records": [
        "roster",
        "protocol_schedule",
        "voting_method",
        "stopping_expression"
      ]
    },
    {
      "id": "nearest-sibling-differential",
      "probe": "probe2_sibling_schema.py",
      "nearest_must_be_named": true
    },
    {
      "id": "jsonschema-draft202012",
      "probe": "probe2_sibling_schema.py",
      "expected_errors_on_valid": 0
    },
    {
      "id": "negative-control",
      "probe": "probe2_sibling_schema.py"
    }
  ],
  "negative_controls": [
    {
      "id": "missing-explanation",
      "rejects": "a composed instance whose voting.rule explanation reason is empty",
      "verbatim": "check_integrity FIRES missing-explanation:voting.rule on a composed instance whose explanation reason for voting.rule was deleted; the unmodified instance is SILENT (0 errors)."
    },
    {
      "id": "non-editable-dial",
      "rejects": "owner.override('default_binding', 'static')",
      "verbatim": "compose(..., override={'default_binding': 'static'}) raises ComposerError non-editable dial override rejected."
    },
    {
      "id": "name-only-duplicate",
      "rejects": "a sibling copy of the flagship instance with only id/name changed",
      "verbatim": "distance(name-mutant, flagship).name_only is True and the preset is rejected as a mechanism-duplicate; C-M01 is not."
    },
    {
      "id": "legal-false-positive",
      "rejects": "seating Legal on a task with no legal cue",
      "verbatim": "T-CSV 'Refactor an internal CSV parser...' must NOT seat Legal."
    }
  ],
  "reviewer": {
    "reviewer_id": "CNL-0116-probe2-sibling-schema",
    "independent": true,
    "verdict": "PASS",
    "method": "Re-instantiate C-GP01 against T-PROD-GNG and recompute nearest sibling over the fixture catalog; require integer_axes >= 2 versus named C-M01."
  },
  "honesty": {
    "catalog_output_schema": "command-center/schema/council-preset.schema.json",
    "catalog_schema_owner_on_this_tree": "CNL-0107",
    "catalog_schema_defs": [
      "council_preset"
    ],
    "executable_schema": "command-center/p2-wave/probes/CNL-0116/council-preset.schema.json",
    "twelve_council_bytes_present": false,
    "nearest_sibling_scope": "estate fixture (not a 72-row recount)",
    "cloud_ok_is_not_delivery": true
  },
  "residual_unknowns": [
    {
      "id": "12-COUNCIL-bytes-absent",
      "detail": "harness-restore 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is not on this worktree. Nearest-sibling is computed over the estate fixture (C-M01 citation + on-tree catalog-class sample + contrast row), not a 72-row recount."
    },
    {
      "id": "CNL-0101-0102-not-on-disk",
      "detail": "Typed-delta key list is the 20 names this unit enumerates and validates; CNL-0101/0102 artifacts are not present to cross-check the binding matrix of all 72."
    },
    {
      "id": "catalog-schema-path-occupied-by-CNL-0107",
      "detail": "command-center/schema/council-preset.schema.json is the CNL-0107 typed-delta wrapper (unit_id const CNL-0107, $defs.council_preset). CNL-0116 did not overwrite it. Live Draft202012 validation uses the unit-local schema."
    }
  ],
  "artifacts": [
    {
      "path": "command-center/design/council/CNL-0116-general-purpose-auto-composed-council-preset-the-flagship.md",
      "role": "primary"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0116/council-preset.schema.json",
      "role": "schema"
    },
    {
      "path": "command-center/p2-wave/probes/CNL-0116/composer.py",
      "role": "composer"
    }
  ],
  "ts": "2026-08-25T00:52:56Z"
}
