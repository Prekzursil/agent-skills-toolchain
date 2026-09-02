{
 "SUCCESS:CNL-0128": true,
 "answer": "Yes. All five catalog phrases round-trip through a shared builder core used by the CLI, the SDK, and the typed structured builder: natural language (or goal_id G1..G5) -> valid CouncilSpec -> field-derived restatement. Encodings: G1 unique_ideas >= 100; G2 unanimity == true OR max_rounds == 12; G3 consensus >= 0.90 with outputs.minority_report == mandatory; G4 no_new_counterexample_rounds >= 2; G5 quality_gate == PASS with no round-count OR-escape. An unrecognized phrase is a named gap at /natural_language, not a guessed spec. An invalid spec returns JSON-Pointer path errors (example: unbound ident vibes -> /stopping_expr) and never a stack trace; CLI validate exits 2.",
 "artifacts": [
  {
   "exists": true,
   "path": "command-center/design/council/CNL-0128-cli-sdk-and-structured-builder-ergonomics-including-invali.md",
   "role": "primary"
  },
  {
   "exists": true,
   "path": "command-center/schema/council-design-note.schema.json",
   "role": "schema"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0128/builder.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0128/spec.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0128/grammar.py",
   "role": "supporting"
  },
  {
   "exists": true,
   "path": "command-center/p2-wave/probes/CNL-0128/fixtures/goals-11198.json",
   "role": "supporting"
  }
 ],
 "both_states": {
  "bad_state": {
   "code": "unbound-ident",
   "detector": "FIRE",
   "id": "unbound-ident-vibes",
   "path": "/stopping_expr"
  },
  "good_state": {
   "detector": "SILENT",
   "errors": 0,
   "id": "five-catalog-goals"
  },
  "pass": true
 },
 "dependencies_noted": {
  "CNL-0010": "stopping-expression grammar consumed as local A10 surface; catalog artifact absent, not blocking the five-goal encodings",
  "CNL-0116": "flagship auto-composed preset is not required to round-trip the five phrases; default roster is local",
  "blocked_on_missing_deps": false
 },
 "evidence": [
  {
   "anchor": "command-center/WORK-UNIT-CATALOG.json:40797",
   "claim": "The five owner goals are quoted in the CNL-0128 catalog question; _USER-PROMPTS.md:11198 is not on this tree.",
   "kind": "catalog",
   "line": 40797,
   "mechanism": "catalog-question-quote",
   "path": "command-center/WORK-UNIT-CATALOG.json",
   "snippet": "brainstorm until 100 unique ideas",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0128/goals.py:33",
   "claim": "G1 encodes unique_ideas >= 100 and round-trips.",
   "kind": "live-tree",
   "line": 33,
   "mechanism": "builder-round-trip",
   "path": "command-center/p2-wave/probes/CNL-0128/goals.py",
   "snippet": "unique_ideas >= 100",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0128/spec.py:98",
   "claim": "Invalid stopping_expr names JSON Pointer /stopping_expr, not a traceback.",
   "kind": "live-tree",
   "line": 98,
   "mechanism": "path-named-validator",
   "path": "command-center/p2-wave/probes/CNL-0128/spec.py",
   "snippet": "\"/stopping_expr\"",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0128/builder.py:63",
   "claim": "Unrecognized owner language is a named gap at /natural_language.",
   "kind": "live-tree",
   "line": 63,
   "mechanism": "named-gap-not-guess",
   "path": "command-center/p2-wave/probes/CNL-0128/builder.py",
   "snippet": "unrecognized-goal",
   "verdict": "CONFIRMED"
  },
  {
   "anchor": "command-center/p2-wave/probes/CNL-0128/surfaces.py:45",
   "claim": "CLI/SDK/builder share one builder core; canonical JSON drops source_surface.",
   "kind": "live-tree",
   "line": 45,
   "mechanism": "surface-parity",
   "path": "command-center/p2-wave/probes/CNL-0128/surfaces.py",
   "snippet": "if k != \"source_surface\"",
   "verdict": "CONFIRMED"
  }
 ],
 "family": {
  "counted_n": 5,
  "expected_n": 5,
  "members": [
   {
    "id": "G1",
    "phrase": "brainstorm until 100 unique ideas",
    "round_trip": true,
    "stopping_expr": "unique_ideas >= 100"
   },
   {
    "id": "G2",
    "phrase": "argue until all agree or 12 rounds",
    "round_trip": true,
    "stopping_expr": "unanimity == true OR max_rounds == 12"
   },
   {
    "id": "G3",
    "phrase": "90 percent consensus with a mandatory minority report",
    "round_trip": true,
    "stopping_expr": "consensus >= 0.90"
   },
   {
    "id": "G4",
    "phrase": "continue until no new counterexample for two rounds",
    "round_trip": true,
    "stopping_expr": "no_new_counterexample_rounds >= 2"
   },
   {
    "id": "G5",
    "phrase": "stop only after an executable test settles it",
    "round_trip": true,
    "stopping_expr": "quality_gate == PASS"
   }
  ],
  "name": "owner-goal-phrasings-11198"
 },
 "invalid_spec_contract": {
  "never": "Python traceback / stack trace",
  "shape": "{path, code, message} JSON Pointer paths",
  "worked_example": {
   "errors": [
    {
     "code": "unbound-ident",
     "message": "unbound identifier(s): vibes",
     "path": "/stopping_expr"
    }
   ],
   "fixture": "stopping_expr=vibes >= 0.9",
   "formatted": "ERROR /stopping_expr: unbound-ident: unbound identifier(s): vibes"
  }
 },
 "kind": "council-design-note",
 "named_probes": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe1_roundtrip.py",
   "id": "probe1",
   "role": "five-goal-round-trip"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe2_invalid_path.py",
   "id": "probe2",
   "role": "invalid-path-negative-control"
  }
 ],
 "negative_control": {
  "control_fixture": "each of the five catalog goal specs, built live",
  "state_the_check_is_meant_to_reject": "an invalid CouncilSpec (unbound stopping ident, empty seats, or statically unsatisfiable expression)",
  "verbatim": "NEGATIVE-CONTROL verbatim: the path-named invalid-spec check is SILENT on each of the five catalog goal specs (zero errors, no traceback); it FIRES on the planted unbound-ident fixture naming /stopping_expr, and the formatted error contains no traceback.",
  "what_the_check_does_on_that_state": "SILENT: validate() returns [] and format_errors contains no Traceback"
 },
 "negative_controls": [
  {
   "bad_state_output": "ERROR /stopping_expr: unbound-ident: unbound identifier(s): vibes",
   "description": "NEGATIVE-CONTROL verbatim: the path-named invalid-spec check is SILENT on each of the five catalog goal specs (zero errors, no traceback); it FIRES on the planted unbound-ident fixture naming /stopping_expr, and the formatted error contains no traceback.",
   "fired_on_bad_state": true,
   "good_state_output": "SILENT on each of the five catalog goal specs: errors=[]",
   "id": "NC-unbound-ident",
   "kind": "malformed-input",
   "silent_on_good_state": true
  }
 ],
 "question": "Can an owner express all five natural-language goals from the spec (brainstorm until 100 unique ideas; argue until all agree or 12 rounds; 90 percent consensus with a mandatory minority report; continue until no new counterexample for two rounds; stop only after an executable test settles it) - and what does the tool say when the spec they wrote is invalid?",
 "report": {
  "control_ids": [
   "NC-unbound-ident"
  ],
  "kind": "council-design-note",
  "observations": [
   {
    "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe1_roundtrip.py",
    "measured": true,
    "method": "builder.round_trip plus CLI/SDK/typed canonical equality",
    "name": "five-goal-round-trip"
   },
   {
    "anchor": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe2_invalid_path.py",
    "measured": "/stopping_expr",
    "method": "spec.validate on unbound-ident fixture",
    "name": "invalid-spec-path-named"
   }
  ]
 },
 "residual_unknowns": [
  "_USER-PROMPTS.md:11198 is not present on this Linux worktree; phrases are taken from the catalog quote of that line.",
  "CNL-0010 catalog artifact is not on this tree; stopping grammar is the local A10 surface (grammar.py), same family as CNL-0083.",
  "CNL-0116 flagship preset artifact is not on this tree; the default three-seat roster is local to this prototype, not a claim that auto-compose is implemented.",
  "Production CLI/SDK/builder modules (IMP-0325/0326/0327) are not shipped here; this unit is the design contract those units must implement."
 ],
 "reviewer": {
  "independent": true,
  "method": "Probe 2 re-extracts the five phrases from the catalog parenthetical and checks encodings from spec fields; it does not trust probe 1's printed restatement table.",
  "reviewer_id": "CNL-0128-probe2-catalog-reread",
  "scope_not_agreement": true,
  "verdict": "PASS"
 },
 "round_trips": [
  {
   "cli_sdk_builder_canonical_equal": true,
   "id": "G1",
   "minority_report": "optional",
   "named_gap": false,
   "natural_language": "brainstorm until 100 unique ideas",
   "restatement": "Stop when unique ideas reach at least 100 (stopping_expr unique_ideas >= 100).",
   "stopping_expr": "unique_ideas >= 100"
  },
  {
   "cli_sdk_builder_canonical_equal": true,
   "id": "G2",
   "minority_report": "optional",
   "named_gap": false,
   "natural_language": "argue until all agree or 12 rounds",
   "restatement": "Stop when all seats agree, or after 12 rounds (unanimity == true OR max_rounds == 12).",
   "stopping_expr": "unanimity == true OR max_rounds == 12"
  },
  {
   "cli_sdk_builder_canonical_equal": true,
   "id": "G3",
   "minority_report": "mandatory",
   "named_gap": false,
   "natural_language": "90 percent consensus with a mandatory minority report",
   "restatement": "Stop when consensus is at least 90 percent. A minority report is mandatory.",
   "stopping_expr": "consensus >= 0.90"
  },
  {
   "cli_sdk_builder_canonical_equal": true,
   "id": "G4",
   "minority_report": "optional",
   "named_gap": false,
   "natural_language": "continue until no new counterexample for two rounds",
   "restatement": "Stop after two consecutive rounds with no new counterexample (no_new_counterexample_rounds >= 2).",
   "stopping_expr": "no_new_counterexample_rounds >= 2"
  },
  {
   "cli_sdk_builder_canonical_equal": true,
   "id": "G5",
   "minority_report": "optional",
   "named_gap": false,
   "natural_language": "stop only after an executable test settles it",
   "restatement": "Stop only after an executable test settles it (quality_gate == PASS). No round-count OR-escape.",
   "stopping_expr": "quality_gate == PASS"
  }
 ],
 "schema_version": 1,
 "sentinel": "SUCCESS:CNL-0128",
 "spec_line_11198": {
  "claimed_source": "_USER-PROMPTS.md:11198",
  "live_quote": "command-center/WORK-UNIT-CATALOG.json:40797",
  "phrases": [
   "brainstorm until 100 unique ideas",
   "argue until all agree or 12 rounds",
   "90 percent consensus with a mandatory minority report",
   "continue until no new counterexample for two rounds",
   "stop only after an executable test settles it"
  ],
  "present_on_this_tree": false
 },
 "state": "SUCCESS",
 "surfaces": {
  "cli": {
   "entry": "surfaces.py build|validate",
   "invalid_exit_code": 2,
   "never_traceback": true
  },
  "sdk": {
   "entry": "surfaces.sdk_build / sdk_validate",
   "returns": "typed dict (ok, spec|errors), not a string as truth"
  },
  "shared_core": "builder.build_from_goal; canonical JSON ignores source_surface",
  "structured_builder": {
   "entry": "builder.build_from_answers({goal_id})",
   "satisfies_disjunct": "visual OR structured builder \u2014 structured builder SATISFIES",
   "typed_question": "which of G1..G5?"
  }
 },
 "tests": [
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe1_roundtrip.py",
   "id": "probe1-roundtrip",
   "result": "PASS"
  },
  {
   "command": "PYTHONDONTWRITEBYTECODE=1 python3 -B command-center/p2-wave/probes/CNL-0128/probe2_invalid_path.py",
   "id": "probe2-invalid-path",
   "result": "PASS"
  }
 ],
 "title": "CLI, SDK and structured builder ergonomics, including invalid-spec errors",
 "ts": "2026-08-25T00:27:59Z",
 "unit_id": "CNL-0128",
 "verdicts": [
  {
   "record_id": "G1",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "G2",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "G3",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "G4",
   "verdict": "EXECUTABLE"
  },
  {
   "record_id": "G5",
   "verdict": "EXECUTABLE"
  }
 ]
}
