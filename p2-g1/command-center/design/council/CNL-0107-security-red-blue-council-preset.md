{
  "answers": {
    "asymmetric_budgets": "Red receives a larger search-round budget (default 6) spent only on in-scope exploration. Blue receives a per-finding rebuttal budget (default 2 rounds per qualifying finding), not a global pool that can be used to wait out the clock. Neutral roles (scope referee, coverage clerk) have a small fixed budget and cannot be starved into issuing a security verdict. Swapping the numeric budgets does not swap the timeout outcome: exhausted red search without a red-signed coverage.ack is still INCONCLUSIVE.",
    "evidence_standards": "A red win-relevant finding is a red_scribe artifact with surface, repro_steps, observable_effect, blast_radius_class, and scribe_signature \u2014 attack-notes or moderator impression do not qualify. A blue close is a counter-artifact (patch, compensating control, or scoped exclusion with a named bound) plus a reproducer verdict. Coverage is a red-signed remaining-surface enumeration recorded by coverage_clerk; blue cannot author it.",
    "timeout_is_not_secure": "The stopping expression evaluates timeout only after RED_WINS and BLUE_WINS gates. timeout_outcome is INCONCLUSIVE and timeout_may_not_map_to_blue_win is true. A blue claim that the system is secure, or a closed-finding set without red coverage.ack, cannot fill that gap. The nearest sibling preset.p08-red-blue-team maps red_budget_exhausted to BLUE_WINS; that is the differential this preset exists to close.",
    "win_conditions": "RED_WINS: at least one unrebutted qualifying finding. BLUE_WINS: every qualifying finding is closed AND a red-signed coverage.ack exists. INCONCLUSIVE: red budget exhausted without those two blue conditions. Illegal: mapping timeout to BLUE_WINS, a majority 'is it secure?' poll, a blue-authored coverage.ack, or a referee security verdict."
  },
  "extends_or_supersedes": [
    {
      "id": "P08",
      "kind": "protocol",
      "note": "Catalog-cited ADVERSARIAL protocol P08 red-blue-team (CNL-0039 family list).",
      "relation": "extends"
    },
    {
      "id": "CNL-0033",
      "kind": "topology_unit",
      "note": "Asymmetric red/blue mandates: budget swap must not swap the winner on timeout.",
      "relation": "instantiates"
    },
    {
      "id": "CNL-0101",
      "kind": "preset_type_unit",
      "note": "Typed delta over a CouncilSpec/protocol base, not a forked charter.",
      "relation": "conforms"
    }
  ],
  "honesty": {
    "catalog_output_schema": "command-center/schema/council-preset.schema.json",
    "dependency_artifacts_present": false,
    "did_not_overwrite_generated_shim": true,
    "executable_schema": "command-center/p2-wave/probes/CNL-0107/council-preset.schema.json",
    "library_12_present": false,
    "reconstruction_note": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json, 11-COUNCIL-SPECIFICATION.schema.json, and dependency artifacts CNL-0101/CNL-0033/CNL-0039 are absent on this worktree. Nearest sibling is a reconstructed P08-bound preset whose naive timeout\u2192BLUE_WINS mapping is the failure named by this unit's question. Second comparator council.preset.catalog-class.editable is the on-tree ARC-0003/ARC-0010 catalog-class reconstruction. This unit does not claim a 72-preset library recount. Catalog command-center/schema/council-preset.schema.json is a generated generic_report shim with no $defs.council_preset; live Draft202012 validation uses the unit-local schema and does not overwrite the shim."
  },
  "instantiation": {
    "protocol_schedule": [
      {
        "actor_role": "scope_referee",
        "artifact": "scope.bound",
        "id": "scope-freeze",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "red_operator",
        "artifact": "search-notes",
        "id": "red-search",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "red_scribe",
        "artifact": "finding.repro",
        "id": "finding-emission",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "blue_reproducer",
        "artifact": "repro.verdict",
        "id": "blue-reproduce",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "blue_defender",
        "artifact": "close.counter-artifact",
        "id": "blue-close",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "coverage_clerk",
        "artifact": "coverage.ack",
        "id": "coverage-ack",
        "task_id": "fixture.authn-gateway-review"
      },
      {
        "actor_role": "coverage_clerk",
        "artifact": "stop.outcome",
        "id": "stop-eval",
        "task_id": "fixture.authn-gateway-review"
      }
    ],
    "roster": [
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "attack-in-scope-surfaces",
        "produces": "search-notes",
        "role_id": "red_operator",
        "seated_on": "fixture.authn-gateway-review",
        "team": "red"
      },
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "emit-qualifying-finding-artifact",
        "produces": "finding.repro",
        "role_id": "red_scribe",
        "seated_on": "fixture.authn-gateway-review",
        "team": "red"
      },
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "rebut-with-counter-artifact",
        "produces": "close.counter-artifact",
        "role_id": "blue_defender",
        "seated_on": "fixture.authn-gateway-review",
        "team": "blue"
      },
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "reproduce-or-fail-to-reproduce",
        "produces": "repro.verdict",
        "role_id": "blue_reproducer",
        "seated_on": "fixture.authn-gateway-review",
        "team": "blue"
      },
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "scope-only-no-security-verdict",
        "produces": "scope.bound",
        "role_id": "scope_referee",
        "seated_on": "fixture.authn-gateway-review",
        "team": "neutral"
      },
      {
        "in_scope": [
          "authn-gateway",
          "session-cookie",
          "refresh-token-store"
        ],
        "mandate": "record-red-signed-coverage-ack-only",
        "produces": "coverage.ack",
        "role_id": "coverage_clerk",
        "seated_on": "fixture.authn-gateway-review",
        "team": "neutral"
      }
    ],
    "stopping_expression": "RED_WINS if unrebutted_qualifying>=1; BLUE_WINS if all_qualifying_closed AND coverage_ack_from_red; else if red_budget_exhausted then INCONCLUSIVE else CONTINUE | timeout_outcome=INCONCLUSIVE | timeout_may_not_map_to_blue_win=True",
    "task_id": "fixture.authn-gateway-review",
    "voting_method": "evidence-gated-classification quorum=4 security_poll_forbidden=True"
  },
  "kind": "council-preset-design",
  "named_probes": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0107/probe1_instantiate.py",
      "id": "probe1",
      "role": "instantiate-and-sibling-differential"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0107/probe2_schema_timeout.py",
      "id": "probe2",
      "role": "schema-and-timeout-not-secure"
    }
  ],
  "nearest_sibling": {
    "differing_axes": [
      "role_ids",
      "voting_rule",
      "security_poll_forbidden",
      "timeout_outcome",
      "timeout_may_not_map_to_blue_win",
      "coverage_ack_rule"
    ],
    "id": "preset.p08-red-blue-team",
    "library_file_on_this_tree": false,
    "named_explicitly": true,
    "profile_differs": true,
    "source": "Reconstructed P08 red-blue-team baseline from catalog-cited protocol name (CNL-0039 question lists P08 red-blue-team). 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree, so this is not a byte copy of a library record."
  },
  "preset": {
    "anti_failure": {
      "no_silent_secure": true,
      "on_split": "surface-unrebutted-findings"
    },
    "artifact_type": "council_preset",
    "audit": {
      "hash_findings": true,
      "persist_transcript": true
    },
    "base_ref": {
      "on_base_version_bump": "list-unmigratable",
      "protocol_id": "P08",
      "spec_kind": "CouncilSpec"
    },
    "budgets": {
      "blue_rebuttal_per_finding": 2,
      "neutral_fixed": 2,
      "notes": "Red has a larger search budget. Blue's budget is per qualifying finding, not a wait-out-the-clock pool. Neutral budget cannot be starved into a security verdict.",
      "red_search_rounds": 6
    },
    "default_binding": {
      "protocol_id": "P08",
      "task_class": "security-review"
    },
    "editable_dials": [
      "budgets.red_search_rounds",
      "budgets.blue_rebuttal_per_finding",
      "protocol_schedule length is not an editable dial"
    ],
    "evidence_standards": {
      "blue_close": [
        "finding_id",
        "counter_artifact_kind",
        "bound",
        "reproducer_verdict"
      ],
      "coverage_ack": "red-signed remaining-surface enumeration recorded by coverage_clerk; blue cannot write it",
      "red_qualifying_finding": [
        "surface",
        "repro_steps",
        "observable_effect",
        "blast_radius_class",
        "scribe_signature"
      ]
    },
    "id": "council.preset.security-red-blue",
    "kind": "typed_delta",
    "protocol_binding": {
      "family": "ADVERSARIAL",
      "name": "red-blue-team",
      "protocol_id": "P08"
    },
    "protocol_schedule": [
      {
        "actor_role": "scope_referee",
        "artifact": "scope.bound",
        "id": "scope-freeze",
        "notes": "In/out of scope only. Referee cannot declare the system secure."
      },
      {
        "actor_role": "red_operator",
        "artifact": "search-notes",
        "id": "red-search",
        "notes": "Consumes red_search_rounds. Exhaustion is a clock event, not a blue win."
      },
      {
        "actor_role": "red_scribe",
        "artifact": "finding.repro",
        "id": "finding-emission",
        "notes": "Qualifying finding must carry surface, repro steps, observable effect, blast-radius class. Cooperative paraphrase is not this artifact."
      },
      {
        "actor_role": "blue_reproducer",
        "artifact": "repro.verdict",
        "id": "blue-reproduce",
        "notes": "Must reproduce or record fail-to-reproduce. Silence is not a close."
      },
      {
        "actor_role": "blue_defender",
        "artifact": "close.counter-artifact",
        "id": "blue-close",
        "notes": "Patch, compensating control, or scoped exclusion with a named bound."
      },
      {
        "actor_role": "coverage_clerk",
        "artifact": "coverage.ack",
        "id": "coverage-ack",
        "notes": "Records a red-signed remaining-surface ack. Blue cannot author this artifact."
      },
      {
        "actor_role": "coverage_clerk",
        "artifact": "stop.outcome",
        "id": "stop-eval",
        "notes": "Evaluate the stopping expression. Timeout without coverage_ack is INCONCLUSIVE."
      }
    ],
    "roles": [
      {
        "id": "red_operator",
        "mandate": "attack-in-scope-surfaces",
        "produces": "search-notes",
        "team": "red"
      },
      {
        "id": "red_scribe",
        "mandate": "emit-qualifying-finding-artifact",
        "produces": "finding.repro",
        "team": "red"
      },
      {
        "id": "blue_defender",
        "mandate": "rebut-with-counter-artifact",
        "produces": "close.counter-artifact",
        "team": "blue"
      },
      {
        "id": "blue_reproducer",
        "mandate": "reproduce-or-fail-to-reproduce",
        "produces": "repro.verdict",
        "team": "blue"
      },
      {
        "id": "scope_referee",
        "mandate": "scope-only-no-security-verdict",
        "produces": "scope.bound",
        "team": "neutral"
      },
      {
        "id": "coverage_clerk",
        "mandate": "record-red-signed-coverage-ack-only",
        "produces": "coverage.ack",
        "team": "neutral"
      }
    ],
    "stopping": {
      "expression": "RED_WINS if unrebutted_qualifying>=1; BLUE_WINS if all_qualifying_closed AND coverage_ack_from_red; else if red_budget_exhausted then INCONCLUSIVE else CONTINUE",
      "max_red_rounds": 6,
      "timeout_may_not_map_to_blue_win": true,
      "timeout_outcome": "INCONCLUSIVE"
    },
    "title": "Security red/blue council preset",
    "unit_origin": "CNL-0107",
    "voting": {
      "quorum": 4,
      "rule": "evidence-gated-classification",
      "security_poll_forbidden": true
    },
    "win_conditions": {
      "BLUE_WINS": "every qualifying finding closed with a counter-artifact AND red-signed coverage.ack",
      "INCONCLUSIVE": "red budget exhausted without RED_WINS and without BLUE_WINS",
      "RED_WINS": "at least one unrebutted qualifying finding.repro",
      "illegal": [
        "map red_budget_exhausted to BLUE_WINS",
        "majority poll on 'is it secure'",
        "blue-authored coverage.ack",
        "referee security verdict"
      ]
    }
  },
  "question": "What asymmetric budgets, evidence standards and win conditions does the red/blue preset set, and what stops the exercise from concluding that the defended system is secure merely because red ran out of time?",
  "reviewer": {
    "independent": true,
    "notes": "Probe 2 re-validates records with Draft202012Validator and re-runs the timeout-without-coverage state without reading probe 1's argument.",
    "reviewer_id": "CNL-0107-probe2-schema-timeout",
    "verdict": "PASS"
  },
  "schema_version": 1,
  "sentinel": "SUCCESS:CNL-0107",
  "state": "SUCCESS",
  "tests": {
    "negative_control": {
      "invalid_record": "command-center/p2-wave/probes/CNL-0107/fixtures/invalid_preset.json",
      "verbatim": "Draft202012Validator on fixtures/invalid_preset.json (missing required roles/stopping/win_conditions/...) yields 14 errors. evaluate_stop on red_budget_exhausted + all_qualifying_closed + blue_claims_secure=true + coverage_ack_from_red=false returns INCONCLUSIVE (INCONCLUSIVE). The check is meant to reject concluding BLUE_WINS / 'system is secure' from the clock plus a blue assertion."
    },
    "schema": {
      "affected_records": {
        "council.preset.catalog-class.editable": 0,
        "council.preset.security-red-blue": 0,
        "preset.p08-red-blue-team": 0
      },
      "draft": "2020-12",
      "expected_error_count_valid": 0,
      "invalid_record_error_count": 14,
      "validator": "jsonschema.Draft202012Validator"
    },
    "sibling_differential": {
      "axes": [
        "role_ids",
        "voting_rule",
        "security_poll_forbidden",
        "timeout_outcome",
        "timeout_may_not_map_to_blue_win",
        "coverage_ack_rule"
      ],
      "sibling_id": "preset.p08-red-blue-team"
    },
    "timeout_control": {
      "ours_outcome": "INCONCLUSIVE",
      "required_ours": "INCONCLUSIVE",
      "sibling_outcome": "BLUE_WINS",
      "state": {
        "all_qualifying_closed": true,
        "blue_claims_secure": true,
        "coverage_ack_from_red": false,
        "red_budget_exhausted": true,
        "unrebutted_qualifying": 0
      }
    }
  },
  "title": "Security red/blue council preset",
  "unit_id": "CNL-0107"
}
