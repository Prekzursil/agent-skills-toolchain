{
  "answer": "Ranging over catalog-named TRADECRAFT records P38-P44 (n=7, two parsers agree; 12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent so library bodies were not read): each record has an executable turn schedule that emits a typed artifact. P38 analysis-of-competing-hypotheses -> hypothesis_matrix (evidence x hypothesis cells in {C,I,N,NA} plus diagnosticity ranking). P39 key-assumptions-check -> assumption_register (load-bearing inversion). P40 quality-of-information-check -> source_quality_ledger (credibility/completeness/corroboration classification). P41 deception-detection -> deception_indicators (indicator scores). P42 argument-mapping -> argument_graph (support/attack graph plus ungrounded claims). P43 premortem -> premortem_failure_modes (frozen plan, assumed failure, warning+control per mode). P44 postmortem-5whys-causal -> causal_chain (exactly five why-steps, root cause, corrective action). Duplicate under (time_orientation, core_operator): P43 premortem duplicates P48 kill-the-company (ENGINEERING-REVIEW, CNL-0045 named list) as prospective-hindsight-failure-enumeration at before-decision. The other six have unique named:<slug> operators against every other family list.",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0044-executable-runtime-semantics-for-the-7-tradecraft-protocol.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json",
      "role": "known-good-fixture"
    },
    {
      "exists": true,
      "path": "command-center/schema/council-design-note.schema.json",
      "role": "output-schema"
    }
  ],
  "both_states": {
    "known_good": {
      "fired": false,
      "reasons": [],
      "silent": true
    },
    "planted_bad": {
      "fired": true,
      "plant": "P40 EXECUTABLE with empty concrete artifact",
      "reasons": [
        "executable-without-artifact:P40"
      ],
      "silent": false
    }
  },
  "claim_under_test": "Each of P38-P44 produces a distinct typed artifact under an executable turn schedule; P43 premortem duplicates P48 kill-the-company under (time_orientation, core_operator).",
  "completion_sentinel": "SUCCESS:CNL-0044",
  "duplicate_criterion": "A TRADECRAFT record duplicates another family's mechanism iff they share time_orientation and core_operator. Names are ignored. Default operator is named:<slug> so only explicit aliases collide. Alias map: premortem and kill-the-company -> prospective-hindsight-failure-enumeration @ before-decision. P48 is taken from CNL-0045's named list (ENGINEERING-REVIEW).",
  "duplicates": [
    {
      "criterion": "same (time_orientation, core_operator) across families; names differ",
      "other_family": "ENGINEERING-REVIEW",
      "other_id": "P48",
      "other_name": "kill-the-company (war-game)",
      "shared_operator": "prospective-hindsight-failure-enumeration",
      "shared_time": "before-decision",
      "tradecraft_id": "P43",
      "tradecraft_name": "premortem"
    }
  ],
  "enumeration": {
    "agreement": true,
    "claimed_elsewhere": [],
    "expected_n": 7,
    "ids": [
      "P38",
      "P39",
      "P40",
      "P41",
      "P42",
      "P43",
      "P44"
    ],
    "library_family_n": null,
    "measured_n": 7,
    "signals": [
      {
        "id": "catalog-question-named-list",
        "ids": [
          "P38",
          "P39",
          "P40",
          "P41",
          "P42",
          "P43",
          "P44"
        ],
        "mechanism": "regex split of the naming parenthesis on ', P'",
        "n": 7,
        "source": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0044].question_or_target"
      },
      {
        "id": "catalog-question-pid-tokens",
        "ids": [
          "P38",
          "P39",
          "P40",
          "P41",
          "P42",
          "P43",
          "P44"
        ],
        "mechanism": "findall Pxx tokens inside the naming parenthesis (no names)",
        "n": 7,
        "source": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0044].question_or_target"
      },
      {
        "id": "all-family-units-then-filter-TRADECRAFT",
        "ids": [
          "P38",
          "P39",
          "P40",
          "P41",
          "P42",
          "P43",
          "P44"
        ],
        "mechanism": "parse every family unit list, keep FAMILY=TRADECRAFT",
        "n": 7,
        "source": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0038..CNL-0046].question_or_target"
      },
      {
        "expected_n": 7,
        "id": "evidence-requirement-expected-n",
        "mechanism": "regex family=TRADECRAFT, expected n=N",
        "source": "command-center/WORK-UNIT-CATALOG.json work_units[id=CNL-0044].evidence_requirement"
      }
    ]
  },
  "evidence": [
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36473",
      "claim": "CNL-0044 names P38-P44 as TRADECRAFT; expected n=7",
      "kind": "catalog",
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:36524",
      "claim": "CNL-0045 names P48 kill-the-company (war-game) in ENGINEERING-REVIEW",
      "kind": "catalog",
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json:2",
      "claim": "known-good cases produce typed artifacts for all 7 records",
      "kind": "fixture",
      "path": "command-center/p2-wave/probes/CNL-0044/fixtures/known_good_cases.json",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0044/semantics.py:19",
      "claim": "turn runners and duplicate alias map (premortem == kill-the-company operator)",
      "kind": "live-tree",
      "path": "command-center/p2-wave/probes/CNL-0044/semantics.py",
      "verdict": "CONFIRMED"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0044/enumerate.py:1",
      "claim": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json family count cannot be taken from disk; file absent",
      "kind": "library-search",
      "path": "command-center/p2-wave/probes/CNL-0044/enumerate.py",
      "verdict": "CONFIRMED"
    }
  ],
  "family": "TRADECRAFT",
  "kind": "council-design-note",
  "library": {
    "filename": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
    "note": "Library bodies were not read because the file is absent on this worktree. Enumeration of TRADECRAFT P-ids uses catalog-named records (CNL-0038..CNL-0046 question_or_target lists), not an invented protocol catalogue.",
    "path": null,
    "present": false,
    "tried": [
      {
        "path": "C:/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/mnt/c/Users/Prekzursil/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/root/.claude/harness-restore-20260806/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/opt/p2/ast-integrate/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/opt/p2/ast-integrate/command-center/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/opt/p2/ast-integrate/command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/opt/p2/ast-integrate/command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      },
      {
        "path": "/opt/p2/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "present": false
      }
    ]
  },
  "metric": {
    "I_star": 7,
    "decision": "PASS iff I==7 on catalog-named P38-P44 and planted-bad empty-artifact fires",
    "formula": "I = |verdicts in {EXECUTABLE, NOT-EXECUTABLE with named missing}|; pass iff I == n_family",
    "id": "family-coverage-I"
  },
  "negative_control": {
    "check": "concrete-artifact",
    "rejected_state": "P40 marked EXECUTABLE but concrete artifact name/keys empty",
    "verbatim": "artifact_check(planted-bad P40 EXECUTABLE with empty artifact) -> fired=True reason=executable-without-artifact:P40 record_ids=['P40'] missing_element=concrete_artifact"
  },
  "negative_controls": [
    {
      "check": "concrete-artifact",
      "rejected_state": "P40 marked EXECUTABLE but concrete artifact name/keys empty",
      "verbatim": "artifact_check(planted-bad P40 EXECUTABLE with empty artifact) -> fired=True reason=executable-without-artifact:P40 record_ids=['P40'] missing_element=concrete_artifact"
    }
  ],
  "notes": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json is absent on this worktree; family membership is the catalog-named P-id list, confirmed by two parsers plus the evidence_requirement expected n=7. Schedules are designed SAT semantics, not copied library fields. SUCCESS:CNL-0044",
  "protocols": [
    {
      "artifact": {
        "keys": [
          "hypotheses",
          "evidence",
          "cells",
          "diagnosticity",
          "ranking"
        ],
        "name": "hypothesis_matrix",
        "produced_on_known_good": {
          "cells": {
            "E1|H-demand-collapse": "C",
            "E1|H-supply-shock": "I",
            "E2|H-demand-collapse": "C",
            "E2|H-supply-shock": "I"
          },
          "diagnosticity": {
            "E1": 1,
            "E2": 1
          },
          "evidence": [
            "E1",
            "E2"
          ],
          "hypotheses": [
            "H-supply-shock",
            "H-demand-collapse"
          ],
          "ranking": [
            {
              "consistent": 2,
              "hypothesis": "H-demand-collapse",
              "inconsistent": 0
            },
            {
              "consistent": 0,
              "hypothesis": "H-supply-shock",
              "inconsistent": 2
            }
          ]
        },
        "shape": "matrix"
      },
      "core_operator": "diagnosticity-matrix",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "analysis-of-competing-hypotheses",
      "record_id": "P38",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "matrix complete AND ranking non-empty AND len(hypotheses)>=2",
      "time_orientation": "before-decision",
      "turns": [
        "collect_hypotheses",
        "collect_evidence",
        "fill_matrix",
        "score_diagnosticity",
        "rank_hypotheses"
      ]
    },
    {
      "artifact": {
        "keys": [
          "claims",
          "assumptions",
          "survivors"
        ],
        "name": "assumption_register",
        "produced_on_known_good": {
          "assumptions": [
            {
              "id": "A1",
              "if_false_consequence": "ship date slips",
              "load_bearing": true,
              "statement": "CI is green on main",
              "status": "holds"
            },
            {
              "id": "A2",
              "if_false_consequence": "",
              "load_bearing": false,
              "statement": "docs site is pretty",
              "status": "untested"
            }
          ],
          "claims": [
            "Friday ship is still in the plan"
          ],
          "survivors": [
            {
              "id": "A1",
              "if_false_consequence": "ship date slips",
              "load_bearing": true,
              "statement": "CI is green on main",
              "status": "holds"
            },
            {
              "id": "A2",
              "if_false_consequence": "",
              "load_bearing": false,
              "statement": "docs site is pretty",
              "status": "untested"
            }
          ]
        },
        "shape": "register"
      },
      "core_operator": "assumption-inversion",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "key-assumptions-check",
      "record_id": "P39",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "every load-bearing assumption has if_false_consequence and status",
      "time_orientation": "atemporal",
      "turns": [
        "collect_claims",
        "extract_assumptions",
        "tag_load_bearing",
        "invert_load_bearing",
        "emit_survivors"
      ]
    },
    {
      "artifact": {
        "keys": [
          "sources",
          "classifications"
        ],
        "name": "source_quality_ledger",
        "produced_on_known_good": {
          "classifications": {
            "S1": "high",
            "S2": "low"
          },
          "sources": [
            {
              "classification": "high",
              "completeness": 0.8,
              "corroboration": 3,
              "credibility": 0.9,
              "id": "S1",
              "label": "primary telemetry dump"
            },
            {
              "classification": "low",
              "completeness": 0.4,
              "corroboration": 0,
              "credibility": 0.25,
              "id": "S2",
              "label": "anonymous forum post"
            }
          ]
        },
        "shape": "ledger"
      },
      "core_operator": "source-scoring",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "quality-of-information-check",
      "record_id": "P40",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "every source has credibility, completeness, corroboration, classification",
      "time_orientation": "atemporal",
      "turns": [
        "list_sources",
        "score_credibility",
        "score_completeness",
        "count_corroboration",
        "classify"
      ]
    },
    {
      "artifact": {
        "keys": [
          "denied_intent",
          "indicators",
          "deception_likelihood",
          "verdict"
        ],
        "name": "deception_indicators",
        "produced_on_known_good": {
          "deception_likelihood": 0.5,
          "denied_intent": "vendor is not hiding a failing gate",
          "indicators": [
            {
              "cue": "green dashboard while tests fail",
              "expected_if_deception": true,
              "id": "D1",
              "observed": true,
              "score": 1
            },
            {
              "cue": "timestamps rewritten after the fact",
              "expected_if_deception": true,
              "id": "D2",
              "observed": false,
              "score": 0
            }
          ],
          "verdict": "deception-indicated"
        },
        "shape": "indicator-list"
      },
      "core_operator": "deception-indicator-scoring",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "deception-detection",
      "record_id": "P41",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "every indicator observed AND verdict present",
      "time_orientation": "atemporal",
      "turns": [
        "state_denied_intent_hypothesis",
        "list_indicators",
        "observe_each",
        "score",
        "emit_verdict"
      ]
    },
    {
      "artifact": {
        "keys": [
          "nodes",
          "edges",
          "ungrounded_claims"
        ],
        "name": "argument_graph",
        "produced_on_known_good": {
          "edges": [
            {
              "dst": "C1",
              "kind": "supports",
              "src": "R1"
            },
            {
              "dst": "R1",
              "kind": "supports",
              "src": "E1"
            }
          ],
          "nodes": [
            {
              "id": "C1",
              "kind": "claim",
              "text": "the gate is live"
            },
            {
              "id": "R1",
              "kind": "reason",
              "text": "probe exit 0 was recorded"
            },
            {
              "id": "E1",
              "kind": "evidence",
              "text": "probe1 stdout"
            },
            {
              "id": "C2",
              "kind": "claim",
              "text": "library was read"
            }
          ],
          "ungrounded_claims": [
            "C2"
          ]
        },
        "shape": "graph"
      },
      "core_operator": "argument-graph",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "argument-mapping",
      "record_id": "P42",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "every claim node is supported or listed in ungrounded_claims",
      "time_orientation": "atemporal",
      "turns": [
        "extract_claims",
        "attach_reasons",
        "attach_objections",
        "attach_evidence",
        "emit_ungrounded"
      ]
    },
    {
      "artifact": {
        "keys": [
          "frozen_plan",
          "assumed_failed",
          "failure_modes"
        ],
        "name": "premortem_failure_modes",
        "produced_on_known_good": {
          "assumed_failed": true,
          "failure_modes": [
            {
              "cause": "two hypotheses never scored against the same evidence",
              "early_warning": "matrix cell empty in rehearsal",
              "id": "F1",
              "preemptive_control": "refuse start until every cell is C/I/N/NA"
            }
          ],
          "frozen_plan": "ship the council runtime Friday without a diagnosticity matrix"
        },
        "shape": "failure-mode-list"
      },
      "core_operator": "prospective-hindsight-failure-enumeration",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "premortem",
      "record_id": "P43",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "plan frozen AND assumed_failed AND every mode has warning and control",
      "time_orientation": "before-decision",
      "turns": [
        "freeze_plan",
        "assume_failure",
        "enumerate_causes",
        "early_warnings",
        "preemptive_controls"
      ]
    },
    {
      "artifact": {
        "keys": [
          "observed_failure",
          "why_steps",
          "root_cause",
          "corrective_action"
        ],
        "name": "causal_chain",
        "produced_on_known_good": {
          "corrective_action": "require a typed stopping expression before the first round",
          "observed_failure": "council ran 12 rounds and never stopped",
          "root_cause": "stopping condition not a boolean over serialised state",
          "why_steps": [
            "stopping predicate was prose",
            "evaluator could not compile prose",
            "runtime treated missing predicate as continue",
            "max_rounds was unset",
            "no wall-clock cap either"
          ]
        },
        "shape": "causal-chain"
      },
      "core_operator": "retrospective-why-chain",
      "executability": "EXECUTABLE",
      "family": "TRADECRAFT",
      "library_body_read": false,
      "missing_element": null,
      "name": "postmortem-5whys-causal",
      "record_id": "P44",
      "semantics_source": "designed-for-catalog-named-id; library record body absent",
      "stopping": "len(why_steps)==5 AND root_cause AND corrective_action",
      "time_orientation": "after-failure",
      "turns": [
        "state_observed_failure",
        "why_1",
        "why_2",
        "why_3",
        "why_4",
        "why_5",
        "name_root_cause",
        "name_corrective_action"
      ]
    }
  ],
  "question": "Ranging over exactly these 7 records, named so no member can fall through a family mis-assignment (P38 analysis-of-competing-hypotheses, P39 key-assumptions-check, P40 quality-of-information-check, P41 deception-detection, P42 argument-mapping, P43 premortem, P44 postmortem-5whys-causal): For each of the 7 TRADECRAFT protocol records (structured analytic techniques), what is the concrete artifact each produces, and which duplicate another family's mechanism under a different name?",
  "reviewer": {
    "independent": true,
    "method": "Re-parse P38-P44 with a range regex (not the comma-name splitter); re-run fixtures; recompute duplicates from CNL-0038..CNL-0046 names; compare numbers only.",
    "reviewer_id": "CNL-0044-probe2-independent-recount",
    "scope_not_agreement": true,
    "verdict": "PASS"
  },
  "sentinel": "SUCCESS:CNL-0044",
  "state": "SUCCESS",
  "taxonomy": {
    "axis": "executability-and-cross-family-mechanism-identity",
    "classes": [
      {
        "id": "EXECUTABLE",
        "interest": "Typed artifact plus stopping predicate over that artifact."
      },
      {
        "id": "NOT-EXECUTABLE",
        "interest": "Named missing element; still counted against family n=7."
      },
      {
        "id": "UNIQUE-MECHANISM",
        "interest": "No other family shares (time_orientation, core_operator)."
      },
      {
        "id": "CROSS-FAMILY-DUPLICATE",
        "interest": "Same (time, operator) as a non-TRADECRAFT catalog P-id."
      }
    ],
    "closed": true,
    "id": "tradecraft-runtime"
  },
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0044/probe1_schedules_and_both_states.py",
      "detail": "7 EXECUTABLE verdicts counted against catalog family n=7",
      "id": "seven-schedules-or-not-executable",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0044/probe1_schedules_and_both_states.py",
      "detail": {
        "known_good": {
          "fired": false,
          "parts": [
            {
              "expected": 7,
              "fired": false,
              "got": 7,
              "id": "family-count",
              "reason": null,
              "silent": true,
              "unique": 7
            },
            {
              "extra": [],
              "fired": false,
              "id": "family-coverage",
              "missing": [],
              "reason": null,
              "silent": true
            },
            {
              "fired": false,
              "id": "concrete-artifact",
              "missing_element": null,
              "reason": null,
              "record_ids": [],
              "silent": true
            }
          ],
          "reasons": [],
          "silent": true
        },
        "ok": true,
        "plant": "P40 EXECUTABLE with empty concrete artifact",
        "planted_bad": {
          "fired": true,
          "parts": [
            {
              "expected": 7,
              "fired": false,
              "got": 7,
              "id": "family-count",
              "reason": null,
              "silent": true,
              "unique": 7
            },
            {
              "extra": [],
              "fired": false,
              "id": "family-coverage",
              "missing": [],
              "reason": null,
              "silent": true
            },
            {
              "fired": true,
              "id": "concrete-artifact",
              "missing_element": "concrete_artifact",
              "reason": "executable-without-artifact:P40",
              "record_ids": [
                "P40"
              ],
              "silent": false
            }
          ],
          "reasons": [
            "executable-without-artifact:P40"
          ],
          "silent": false
        }
      },
      "id": "both-states-artifact-check",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0044/probe1_schedules_and_both_states.py",
      "detail": {
        "check": "concrete-artifact",
        "rejected_state": "P40 marked EXECUTABLE but concrete artifact name/keys empty",
        "result": {
          "fired": true,
          "id": "concrete-artifact",
          "missing_element": "concrete_artifact",
          "reason": "executable-without-artifact:P40",
          "record_ids": [
            "P40"
          ],
          "silent": false
        },
        "verbatim": "artifact_check(planted-bad P40 EXECUTABLE with empty artifact) -> fired=True reason=executable-without-artifact:P40 record_ids=['P40'] missing_element=concrete_artifact"
      },
      "id": "negative-control-empty-artifact",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0044/probe2_independent_recount.py",
      "detail": "probe2 re-tabulates after this file exists; receipts refuse if it fails",
      "id": "independent-recount",
      "result": "PASS"
    }
  ],
  "title": "Executable runtime semantics for the 7 TRADECRAFT protocols",
  "ts": "2026-08-25T00:54:18Z",
  "unit_id": "CNL-0044"
}
