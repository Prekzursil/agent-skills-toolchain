{
  "answer": "The compiler auto-selects a protocol by table lookup. Lookup keys must be members of closed enums; prose cannot index a catalogue without NLP, and NLP is not a compiler. ENUMS the compiler branches on: risk_tier {low, medium, high, critical}, desired_output {decision, ranked_options, specification, review, counterexample, plan}, consensus_intent {unanimous, supermajority, majority, owner_decides, dissent_required}. PROSE that survives: objective (the actual task text) and success_criteria (human-facing done-when). Fallbacks when the compiler cannot branch: objective empty => COMPILE_REJECT reason=objective_required (completeness, not a silent protocol); objective present => copied to task_prose and excluded from protocol_id; success_criteria empty => attach protocol-native stopping and emit success_criteria_absent_used_protocol_default; success_criteria present => copied to human_success_criteria and never parsed. Unknown or missing enum => COMPILE_REJECT (unknown_enum:/missing_enum:), never a default protocol. Cartesian size of the live table is 120. The losing option (all five fields as prose plus dict.get default) silent-defaults risk_tier='urgent-ish' to consult.vote.majority; the live compiler rejects that input. SUCCESS:CNL-0003",
  "artifacts": [
    {
      "exists": true,
      "path": "command-center/design/council/CNL-0003-charter-block-the-typed-fields-a-compiler-actually-branche.md",
      "role": "primary"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0003/charter_block.schema.json",
      "role": "charter-block-schema"
    },
    {
      "exists": true,
      "path": "command-center/p2-wave/probes/CNL-0003/compiler.py",
      "role": "compiler"
    }
  ],
  "charter_block": {
    "axis_maps": {
      "consensus_intent": {
        "dissent_required": "dissent",
        "majority": "majority",
        "owner_decides": "advise",
        "supermajority": "supermajority",
        "unanimous": "unanimous"
      },
      "desired_output": {
        "counterexample": "refute",
        "decision": "vote",
        "plan": "plan",
        "ranked_options": "rank",
        "review": "review",
        "specification": "draft"
      },
      "risk_tier": {
        "critical": "owner_gated",
        "high": "adversarial",
        "low": "consult",
        "medium": "deliberate"
      }
    },
    "cartesian": 120,
    "enum_fields": {
      "consensus_intent": [
        "unanimous",
        "supermajority",
        "majority",
        "owner_decides",
        "dissent_required"
      ],
      "desired_output": [
        "decision",
        "ranked_options",
        "specification",
        "review",
        "counterexample",
        "plan"
      ],
      "risk_tier": [
        "low",
        "medium",
        "high",
        "critical"
      ]
    },
    "prose_fields": {
      "objective": {
        "branches": false,
        "empty_fallback": "COMPILE_REJECT:objective_required",
        "present_fallback": "copy to task_prose; exclude from protocol_id"
      },
      "success_criteria": {
        "branches": false,
        "empty_fallback": "success_criteria_absent_used_protocol_default",
        "present_fallback": "copy to human_success_criteria; exclude from protocol_id"
      }
    },
    "protocol_id_shape": "risk_family.output_family.intent_family",
    "silent_default": "forbidden"
  },
  "cloud_ok": false,
  "completion_sentinel": "SUCCESS:CNL-0003",
  "dependency_cnl_0001": {
    "note": "CNL-0001 is not delivered on this tree. The charter-block enums are specified independently of the v2 root envelope.",
    "output_path": "command-center/design/council/CNL-0001-councilspec-v2-root-envelope-that-supersedes-council-chart.schema.json",
    "present": false
  },
  "evidence": [
    {
      "anchor": "command-center/p2-wave/probes/CNL-0003/compiler.py:79",
      "claim": "Unknown enum COMPILE_REJECTs; there is no default arm.",
      "kind": "probe-runtime",
      "line": 79,
      "path": "command-center/p2-wave/probes/CNL-0003/compiler.py",
      "snippet": "if key not in axis:"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0003/compiler.py:81",
      "claim": "Live select() uses dict[key], not dict.get(key, default).",
      "kind": "probe-runtime",
      "line": 81,
      "path": "command-center/p2-wave/probes/CNL-0003/compiler.py",
      "snippet": "return axis[key], None"
    },
    {
      "anchor": "command-center/p2-wave/probes/CNL-0003/charter_block.schema.json:21",
      "claim": "Second signal: risk_tier is a JSON Schema enum, not prose.",
      "kind": "schema-file",
      "line": 21,
      "path": "command-center/p2-wave/probes/CNL-0003/charter_block.schema.json",
      "snippet": "\"enum\": [\"low\", \"medium\", \"high\", \"critical\"]"
    },
    {
      "anchor": "command-center/WORK-UNIT-CATALOG.json:34451",
      "claim": "The unit question names the five charter fields under test.",
      "kind": "catalog",
      "line": 34451,
      "path": "command-center/WORK-UNIT-CATALOG.json",
      "snippet": "as ENUMS rather than prose in order to auto-select a protocol"
    }
  ],
  "known_good_compile": {
    "fallbacks": [
      "prose_field_cannot_branch:objective",
      "prose_field_cannot_branch:success_criteria"
    ],
    "ok": true,
    "protocol_id": "deliberate.vote.majority",
    "reason": "selected"
  },
  "negative_controls": [
    {
      "check_does": "COMPILE_REJECT with reason unknown_enum:risk_tier:urgent-ish and protocol_id=None. Does not emit consult.vote.majority.",
      "fires_on_planted_bad": true,
      "id": "unknown-enum-silent-default",
      "reject_state": "risk_tier='urgent-ish' (prose in an enum field)",
      "silent_on_known_good": true,
      "verbatim": "ok=False protocol_id=None reason=unknown_enum:risk_tier:urgent-ish"
    }
  ],
  "not_checked": [
    {
      "claim": "v1 Council Charter already types these five fields as enums in 11-COUNCIL-SPECIFICATION.schema.json",
      "reason": "File absent on this worktree; cannot harvest v1 property shapes. Enum members here are compiler requirements."
    },
    {
      "claim": "protocol_id tokens equal named cards in 12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "reason": "Catalogue absent (same measurement as ARC-0003/A2). Family tokens are not a 58-card count."
    }
  ],
  "question": "Which charter fields (objective, risk tier, desired output, success criteria, consensus intent) does the council compiler need as ENUMS rather than prose in order to auto-select a protocol, and for each prose field that survives, what is the fallback when the compiler cannot branch?",
  "required_fix": null,
  "reviewer": {
    "counterexample": {
      "consensus_intent": "majority",
      "desired_output": "decision",
      "objective": "Reviewer counterexample: prose stuffed into an enum field.",
      "risk_tier": "urgent-ish",
      "success_criteria": "Must COMPILE_REJECT, never silent-default."
    },
    "counterexample_claim": "If the compiler silent-defaulted, risk_tier='urgent-ish' would still yield a protocol_id. The live compiler must COMPILE_REJECT.",
    "independent": true,
    "mechanism": "jsonschema-file enum arrays, not compiler.py dict keys",
    "recount_agrees": true,
    "recounted_cartesian": 120,
    "reviewer_id": "CNL-0003-schema-file-cartesian-recount",
    "verdict": "PASS"
  },
  "schema_note_path": "command-center/schema/council-design-note.schema.json",
  "schema_note_present": true,
  "sentinel": "SUCCESS:CNL-0003",
  "source_absence": {
    "note": "Enum members are the compiler's required closed sets for a total branch function, not harvested from the absent v1 schema or the 58/72 catalogue records. Protocol ids here are family tokens, not 12-COUNCIL card names.",
    "protocol_catalogue": {
      "checked": [
        "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "command-center/sources/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "command-center/schema/12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
        "command-center/design/council/12-COUNCIL-PROTOCOLS-AND-PRESETS.json"
      ],
      "hit_count": 0,
      "name": "12-COUNCIL-PROTOCOLS-AND-PRESETS.json",
      "present": false
    },
    "v1_schema": {
      "checked": [
        "11-COUNCIL-SPECIFICATION.schema.json",
        "command-center/sources/11-COUNCIL-SPECIFICATION.schema.json",
        "command-center/schema/11-COUNCIL-SPECIFICATION.schema.json",
        "command-center/design/council/11-COUNCIL-SPECIFICATION.schema.json"
      ],
      "hit_count": 0,
      "name": "11-COUNCIL-SPECIFICATION.schema.json",
      "present": false
    }
  },
  "state": "SUCCESS",
  "tests": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0003/probe1_branch_table.py",
      "exit_code": 0,
      "id": "probe1-compiler-branch-table",
      "raw_output": "cartesian=120 routed_risk=4 routed_output=6 routed_intent=5 unknown_reject=unknown_enum:risk_tier:urgent-ish losing_silent_default=consult.vote.majority\nSUCCESS:CNL-0003-probe1 compiler-branch table every enum routes; no silent default",
      "result": "PASS"
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0003/probe2_both_states.py",
      "exit_code": 0,
      "id": "probe2-both-states-jsonschema",
      "raw_output": "both-states schema good_errs=0 bad_risk_errs=1 compiler_good_ok=True compiler_bad_reason=unknown_enum:risk_tier:pretty important reviewer_cartesian=120 negative=ok=False protocol_id=None reason=unknown_enum:risk_tier:urgent-ish\nSUCCESS:CNL-0003-probe2 both-states + jsonschema + reviewer counterexample",
      "result": "PASS"
    },
    {
      "command": "compiler.losing_select(risk_tier='urgent-ish')",
      "id": "losing-option-silent-default",
      "note": "Losing option implemented far enough to demonstrate the failure the criterion predicts: unknown enum still yields consult.vote.majority",
      "result": "PASS"
    }
  ],
  "title": "Charter block: the typed fields a compiler actually branches on",
  "unit_id": "CNL-0003"
}
