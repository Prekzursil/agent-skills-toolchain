"""Executable conformance tests for the CouncilSpec contract (Phase 4: tests before breadth).

Discipline enforced here:
  * detector control - every "rejects X" test is paired with a known-PRESENT case the same
    detector accepts, so a silent always-fail detector cannot pass this suite;
  * both-states - the conformance runner is run against a deliberately BROKEN copy of the
    examples tree and must go red, so its green is not vacuous;
  * scoped claims - the string round-trip is asserted at TREE level only, and the test that
    proves byte-level round-trip is FALSE is written down rather than hidden.
"""

from __future__ import annotations

import copy
import json
import os
import shutil

import pytest

from councilspec import expression as expr
from councilspec import make_negatives, semantics
from councilspec.registry import (
    SCHEMA_PATH,
    all_metric_names,
    domain_of,
    load_schema,
    metric_domains,
)
from councilspec.validate import (
    EXAMPLES_DIR,
    run_conformance,
    schema_errors,
    validate_file,
    validate_spec,
)

VALID_DIR = os.path.join(EXAMPLES_DIR, "valid")
INVALID_DIR = os.path.join(EXAMPLES_DIR, "invalid")

with open(os.path.join(EXAMPLES_DIR, "EXPECTATIONS.json"), "r", encoding="utf-8") as _fh:
    MANIFEST = json.load(_fh)

POSITIVE_CASES = [c for c in MANIFEST["cases"] if c["expect"] == "pass"]
NEGATIVE_CASES = [c for c in MANIFEST["cases"] if c["expect"] == "fail"]

# The six required executable examples, verbatim from _USER-PROMPTS.md:10937-10942.
SPEC_EXPRESSIONS = [
    "unique_ideas >= 100 AND completeness_score >= 0.90",
    "consensus >= 0.95 AND no_new_objection_rounds >= 2",
    "unanimity == true OR max_rounds == 12",
    "quality_gate == PASS AND unresolved_load_bearing_counterexample == 0",
    "evidence_saturation == true OR time_minutes >= 180",
    "proof_of_impossibility == true",
]


# ------------------------------------------------------------------ schema + registry


def test_schema_is_a_valid_draft_2020_12_schema():
    import jsonschema

    schema = load_schema()
    cls = jsonschema.validators.validator_for(schema)
    assert cls.__name__ == "Draft202012Validator"
    cls.check_schema(schema)


def test_registry_detector_control_known_present_and_known_absent():
    # known-present, one per domain
    assert domain_of("unique_ideas") == "numeric"
    assert domain_of("unanimity") == "boolean"
    assert domain_of("quality_gate") == "enum"
    assert domain_of("custom:anything_here") == "custom"
    # known-absent must raise, not quietly resolve
    with pytest.raises(KeyError):
        domain_of("vibes_score")
    assert len(all_metric_names()) >= 40


def test_metric_domains_are_disjoint():
    d = metric_domains()
    assert not (d["numeric"] & d["boolean"])
    assert not (d["numeric"] & d["enum"])
    assert not (d["boolean"] & d["enum"])


def test_every_spec_required_metric_is_registered():
    required = {
        "unique_ideas", "completeness_score", "consensus", "no_new_objection_rounds",
        "unanimity", "max_rounds", "quality_gate", "unresolved_load_bearing_counterexample",
        "evidence_saturation", "time_minutes", "proof_of_impossibility",
    }
    assert required <= all_metric_names()


def test_schema_covers_the_spec_vocabulary():
    """Enum coverage for the lists the spec enumerates explicitly (10926/10927/10930)."""
    schema = load_schema()
    topologies = set(schema["$defs"]["topology"]["properties"]["kind"]["enum"])
    assert {
        "flat", "chair_led", "committee", "caucus", "proposer_critic_judge", "red_blue",
        "jury", "delphi", "pairwise_tournament", "nested_subcouncil", "council_of_councils",
    } == topologies
    protocols = set(schema["$defs"]["protocol_stage"]["properties"]["kind"]["enum"])
    assert {
        "blind_independent_first_pass", "brainstorm", "round_robin", "nominal_group",
        "socratic", "oxford", "cross_examination", "steelman_before_rebuttal", "premortem",
        "scenario", "war_game", "six_hats", "fishbowl", "prediction_confidence",
        "negotiation", "mediation", "jury", "custom",
    } <= protocols
    methods = set(schema["$defs"]["voting"]["properties"]["method"]["enum"])
    assert {
        "synthesis_only", "majority", "supermajority", "unanimity", "consent_no_objection",
        "ranked_choice", "score", "approval", "condorcet", "juror", "judge", "weighted",
        "bayesian", "veto", "quorum", "abstention", "delegation",
    } == methods
    presets = set(schema["$defs"]["preset_name"]["enum"])
    assert len(presets) >= 24 and "general_purpose_auto_composed" in presets


# ------------------------------------------------------------------- expression parse


@pytest.mark.parametrize("text", SPEC_EXPRESSIONS)
def test_spec_expression_parses(text):
    tree = expr.parse(text)
    assert isinstance(tree, dict)
    assert schema_errors({"x": 1}) != []  # sanity: the schema validator is live


def test_spec_expression_trees_are_exactly_as_expected():
    assert expr.parse(SPEC_EXPRESSIONS[0]) == {
        "all_of": [
            {"metric": "unique_ideas", "op": ">=", "value": 100},
            {"metric": "completeness_score", "op": ">=", "value": 0.9},
        ]
    }
    assert expr.parse(SPEC_EXPRESSIONS[2]) == {
        "any_of": [
            {"metric": "unanimity", "op": "==", "value": True},
            {"metric": "max_rounds", "op": "==", "value": 12},
        ]
    }
    assert expr.parse(SPEC_EXPRESSIONS[3]) == {
        "all_of": [
            {"metric": "quality_gate", "op": "==", "value": "PASS"},
            {"metric": "unresolved_load_bearing_counterexample", "op": "==", "value": 0},
        ]
    }
    assert expr.parse(SPEC_EXPRESSIONS[5]) == {
        "metric": "proof_of_impossibility", "op": "==", "value": True
    }


@pytest.mark.parametrize("text", SPEC_EXPRESSIONS)
def test_parsed_spec_expression_validates_against_the_schema(text):
    """A parsed spec string must be a schema-legal stop_expression, not just a dict."""
    tree = expr.parse(text)
    probe = _minimal_spec(tree)
    assert schema_errors(probe) == []


@pytest.mark.parametrize("text", SPEC_EXPRESSIONS)
def test_unparse_parse_is_tree_idempotent(text):
    tree = expr.parse(text)
    assert expr.parse(expr.unparse(tree)) == tree


def test_byte_level_roundtrip_is_NOT_claimed():
    """Scoping the claim: 0.90 normalises to 0.9, so text is not preserved verbatim."""
    text = "unique_ideas >= 100 AND completeness_score >= 0.90"
    assert expr.unparse(expr.parse(text)) != text
    assert expr.unparse(expr.parse(text)) == (
        "unique_ideas >= 100 AND completeness_score >= 0.9"
    )
    assert expr.parse(expr.unparse(expr.parse(text))) == expr.parse(text)


def test_precedence_not_binds_tighter_than_and_which_binds_tighter_than_or():
    tree = expr.parse("unanimity == true OR NOT deadlock_detected == true AND consensus >= 0.5")
    assert tree == {
        "any_of": [
            {"metric": "unanimity", "op": "==", "value": True},
            {
                "all_of": [
                    {"not": {"metric": "deadlock_detected", "op": "==", "value": True}},
                    {"metric": "consensus", "op": ">=", "value": 0.5},
                ]
            },
        ]
    }


def test_parentheses_override_precedence():
    flat = expr.parse("unanimity == true OR quorum_met == true AND consensus >= 0.9")
    grouped = expr.parse("(unanimity == true OR quorum_met == true) AND consensus >= 0.9")
    assert flat != grouped
    assert "all_of" in grouped and "any_of" in flat
    assert expr.parse(expr.unparse(grouped)) == grouped  # parens survive the round trip


def test_any_all_sugar_normalises_to_any_of_and_all_of():
    """Spec 10760 names ANY/ALL; the preset catalogue writes `ANY[rounds>=1, ...]`."""
    assert expr.parse("ANY[unanimity == true, max_rounds == 12]") == expr.parse(
        "unanimity == true OR max_rounds == 12"
    )
    assert expr.parse("ALL[consensus >= 0.95, no_new_objection_rounds >= 2]") == expr.parse(
        "consensus >= 0.95 AND no_new_objection_rounds >= 2"
    )
    nested = expr.parse("ALL[ANY[unanimity == true, quorum_met == true], consensus >= 0.9]")
    assert nested["all_of"][0] == {
        "any_of": [
            {"metric": "unanimity", "op": "==", "value": True},
            {"metric": "quorum_met", "op": "==", "value": True},
        ]
    }


def test_any_all_sugar_is_input_only_and_unparse_stays_canonical():
    """Scoped claim: sugar is accepted, never emitted; the round trip is tree-level."""
    tree = expr.parse("ANY[unanimity == true, max_rounds == 12]")
    assert expr.unparse(tree) == "unanimity == true OR max_rounds == 12"
    assert expr.parse(expr.unparse(tree)) == tree


@pytest.mark.parametrize(
    "bad, needle",
    [
        ("ANY[unanimity == true]", "needs at least two operands"),
        ("ANY unanimity == true", "expected a metric name"),
        ("ANY[unanimity == true, ", "unexpected end"),
        ("ALL[unanimity == true max_rounds == 12]", "expected rbracket"),
    ],
)
def test_any_all_sugar_rejects_malformed_forms(bad, needle):
    with pytest.raises(expr.ExpressionError) as exc:
        expr.parse(bad)
    assert needle in str(exc.value)


def test_custom_metric_parse_declares_its_value_type():
    tree = expr.parse("custom:solver_unsat == true")
    assert tree == {
        "metric": "custom:solver_unsat", "op": "==", "value": True, "value_type": "boolean"
    }
    assert expr.parse("custom:budget_burn >= 0.75")["value_type"] == "number"


@pytest.mark.parametrize(
    "bad, needle",
    [
        ("unanimity >= 0.95", "illegal for boolean"),
        ("unique_ideas == true", "needs a number"),
        ("quality_gate == BANANA", "enum tokens"),
        ("quality_gate >= PASS", "illegal for enum"),
        ("vibes_score >= 1", "unknown metric"),
        ("true AND unanimity == true", "bare boolean literal"),
        ("unique_ideas >= 100 AND", "unexpected end"),
        ("unique_ideas >= 100 100", "trailing token"),
        ("unique_ideas 100", "expected op"),
        ("", "empty stopping expression"),
        ("custom:x_thing >= true", "may only use"),
    ],
)
def test_parser_rejects_ill_typed_expressions(bad, needle):
    with pytest.raises(expr.ExpressionError) as exc:
        expr.parse(bad)
    assert needle in str(exc.value)


def test_parser_accepts_the_control_case_it_almost_rejected():
    """Detector control for the test above: a legal expression must still parse."""
    assert expr.parse("unanimity == true") == {
        "metric": "unanimity", "op": "==", "value": True
    }
    assert expr.parse("quality_gate != FAIL")["value"] == "FAIL"


# ---------------------------------------------------------------- expression evaluate


def test_evaluate_all_of_any_of_not():
    tree = expr.parse(SPEC_EXPRESSIONS[0])
    assert expr.evaluate(tree, {"unique_ideas": 100, "completeness_score": 0.9}) is True
    assert expr.evaluate(tree, {"unique_ideas": 99, "completeness_score": 0.99}) is False
    or_tree = expr.parse(SPEC_EXPRESSIONS[2])
    assert expr.evaluate(or_tree, {"unanimity": True, "max_rounds": 3}) is True
    assert expr.evaluate(or_tree, {"unanimity": False, "max_rounds": 12}) is True
    assert expr.evaluate(or_tree, {"unanimity": False, "max_rounds": 11}) is False
    not_tree = expr.parse("NOT deadlock_detected == true")
    assert expr.evaluate(not_tree, {"deadlock_detected": False}) is True
    assert expr.evaluate(not_tree, {"deadlock_detected": True}) is False


def test_evaluate_weighted_threshold_boundary():
    tree = {
        "weighted": {
            "threshold": 0.7,
            "clauses": [
                {"weight": 0.5, "when": {"metric": "counterexamples_found", "op": ">=", "value": 3}},
                {"weight": 0.3, "when": {"metric": "quorum_met", "op": "==", "value": True}},
                {"weight": 0.4, "when": {"metric": "evidence_saturation", "op": "==", "value": True}},
            ],
        }
    }
    base = {"counterexamples_found": 0, "quorum_met": False, "evidence_saturation": False}
    assert expr.evaluate(tree, base) is False
    assert expr.evaluate(tree, {**base, "counterexamples_found": 3}) is False        # 0.5
    assert expr.evaluate(tree, {**base, "counterexamples_found": 3, "quorum_met": True}) is True  # 0.8
    assert expr.evaluate(tree, {**base, "quorum_met": True, "evidence_saturation": True}) is True  # 0.7 == threshold


def test_missing_metric_is_not_false():
    with pytest.raises(expr.MissingMetricError):
        expr.evaluate(expr.parse("unique_ideas >= 100"), {})


@pytest.mark.parametrize(
    "text, snapshot",
    [
        ("unanimity == true", {"unanimity": 1}),          # int masquerading as bool
        ("unique_ideas >= 100", {"unique_ideas": True}),   # bool masquerading as number
        ("unique_ideas >= 100", {"unique_ideas": "100"}),  # string masquerading as number
        ("quality_gate == PASS", {"quality_gate": 1}),
    ],
)
def test_evaluate_rejects_wrongly_typed_snapshot_values(text, snapshot):
    with pytest.raises(expr.MetricTypeError):
        expr.evaluate(expr.parse(text), snapshot)


def test_evaluate_accepts_the_correctly_typed_control():
    assert expr.evaluate(expr.parse("unanimity == true"), {"unanimity": True}) is True
    assert expr.evaluate(expr.parse("unique_ideas >= 100"), {"unique_ideas": 100}) is True
    assert expr.evaluate(expr.parse("quality_gate == PASS"), {"quality_gate": "PASS"}) is True


def test_referenced_metrics_walks_every_node_kind():
    tree = {
        "all_of": [
            {"not": {"metric": "deadlock_detected", "op": "==", "value": True}},
            {
                "weighted": {
                    "threshold": 1,
                    "clauses": [{"weight": 1, "when": {"metric": "consensus", "op": ">=", "value": 0.9}}],
                }
            },
            {"any_of": [
                {"metric": "unanimity", "op": "==", "value": True},
                {"metric": "time_minutes", "op": ">=", "value": 5},
            ]},
        ]
    }
    assert expr.referenced_metrics(tree) == {
        "deadlock_detected", "consensus", "unanimity", "time_minutes"
    }


# -------------------------------------------------------------------- the 6 examples


@pytest.mark.parametrize("case", POSITIVE_CASES, ids=lambda c: os.path.basename(c["file"]))
def test_required_example_validates(case):
    path = os.path.join(EXAMPLES_DIR, case["file"].replace("/", os.sep))
    result = validate_file(path)
    assert result["schema_errors"] == []
    assert result["semantic_errors"] == []
    assert result["ok"] is True


@pytest.mark.parametrize("case", POSITIVE_CASES, ids=lambda c: os.path.basename(c["file"]))
def test_required_example_encodes_its_spec_string(case):
    path = os.path.join(EXAMPLES_DIR, case["file"].replace("/", os.sep))
    with open(path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    assert case["spec_expression"] in SPEC_EXPRESSIONS
    assert expr.parse(case["spec_expression"]) == spec["stopping"]["expression"]


@pytest.mark.parametrize("case", POSITIVE_CASES, ids=lambda c: os.path.basename(c["file"]))
def test_required_example_stopping_rule_executes_both_states(case):
    path = os.path.join(EXAMPLES_DIR, case["file"].replace("/", os.sep))
    with open(path, "r", encoding="utf-8") as fh:
        tree = json.load(fh)["stopping"]["expression"]
    assert expr.evaluate(tree, case["metrics_satisfying"]) is True
    assert expr.evaluate(tree, case["metrics_not_satisfying"]) is False


def test_all_six_spec_expressions_are_covered_by_an_example():
    covered = {c["spec_expression"] for c in POSITIVE_CASES}
    assert covered == set(SPEC_EXPRESSIONS)
    assert len(POSITIVE_CASES) == 6


# ------------------------------------------------------------------ the must-fail set


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda c: os.path.basename(c["file"]))
def test_negative_fixture_is_rejected_by_the_named_detector(case):
    path = os.path.join(EXAMPLES_DIR, case["file"].replace("/", os.sep))
    result = validate_file(path)
    assert result["ok"] is False, f"{case['file']} was accepted: {case['reason']}"
    blob = " | ".join(result["schema_errors"] + result["semantic_errors"])
    if case["detector"] == "schema":
        assert result["schema_errors"], "expected a schema rejection"
    else:
        assert result["semantic_errors"], "expected a semantic rejection"
    assert case["contains"] in blob


def test_headline_must_fail_case_is_the_typed_leaf_violation():
    """The single required MUST-FAIL instance, shown failing with its message."""
    path = os.path.join(INVALID_DIR, "N1-typed-leaf-violation.councilspec.json")
    result = validate_file(path)
    assert result["ok"] is False
    assert any("stopping" in msg and "not valid under any of the given schemas" in msg
               for msg in result["schema_errors"])


@pytest.mark.parametrize("case", NEGATIVE_CASES, ids=lambda c: os.path.basename(c["file"]))
def test_negative_fixture_base_still_passes(case):
    """Both-states control: the fixture differs from a PASSING base by one mutation."""
    base = os.path.join(EXAMPLES_DIR, case["mutation_of"].replace("/", os.sep))
    assert validate_file(base)["ok"] is True


def test_negative_fixtures_match_their_declared_single_mutation():
    assert make_negatives.main(["--check"]) == 0


def test_negative_fixtures_differ_from_base_at_exactly_one_site():
    """A fixture that drifted into a multi-defect file would test something else."""
    for mut in make_negatives.MUTATIONS:
        with open(os.path.join(VALID_DIR, mut.base), "r", encoding="utf-8") as fh:
            base = json.load(fh)
        with open(os.path.join(INVALID_DIR, mut.out), "r", encoding="utf-8") as fh:
            mutant = json.load(fh)
        changed = _changed_top_level_keys(base, mutant)
        allowed = {mut.path[0]}
        if mut.drop_source_expression:
            allowed.add("stopping")
        assert changed <= allowed, f"{mut.out} changed {changed}, expected {allowed}"


def test_semantic_rules_have_real_fixture_coverage():
    covered = {c["contains"] for c in NEGATIVE_CASES if c["detector"] == "semantic"}
    assert len(covered) >= 5, f"only {covered} semantic rules are proven to fire"


# ----------------------------------------------------------------- semantic rule unit


def test_semantic_recursion_reaches_subcouncils():
    """topology.subcouncils uses `$ref: '#'`; prove a broken CHILD fails the PARENT."""
    path = os.path.join(VALID_DIR, "E6-council-of-councils-impossibility.councilspec.json")
    with open(path, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    assert validate_spec(spec)["ok"] is True                       # control: healthy
    broken = copy.deepcopy(spec)
    broken["topology"]["subcouncils"][1]["stopping"]["expression"] = {
        "metric": "unanimity", "op": ">=", "value": 0.5           # boolean metric, numeric op
    }
    result = validate_spec(broken)
    assert result["ok"] is False
    assert any("subcouncils" in msg for msg in result["schema_errors"])

    drifted = copy.deepcopy(spec)
    drifted["topology"]["subcouncils"][1]["stopping"]["source_expression"] = (
        "unique_ideas >= 999 AND NOT deadlock_detected == true"
    )
    sem = validate_spec(drifted)
    assert sem["ok"] is False
    assert any("subcouncils[1]" in msg and "SEM-001" in msg for msg in sem["semantic_errors"])


def test_sem006_unknown_participant_reference():
    spec = _load_valid("E2-architecture-review-board.councilspec.json")
    spec["topology"]["chair"] = "ghost-participant"
    findings = semantics.check(spec)
    assert any(f.rule == "SEM-006" and f.severity == "ERROR" for f in findings)


def test_sem005_weighted_requires_a_positive_weight():
    spec = _load_valid("E2-architecture-review-board.councilspec.json")
    spec["voting"]["method"] = "weighted"
    spec["voting"]["weights"] = {"chair-arch": 0}
    findings = semantics.check(spec)
    assert any(f.rule == "SEM-005" for f in findings)
    spec["voting"]["weights"] = {"chair-arch": 2}
    assert not [f for f in semantics.check(spec) if f.rule == "SEM-005"]


def test_sem009_minority_report_required_needs_the_outcome():
    spec = _load_valid("E2-architecture-review-board.councilspec.json")
    spec["outcomes"]["allowed"] = ["decision", "no_decision"]
    findings = semantics.errors(semantics.check(spec))
    assert any(f.rule == "SEM-009" for f in findings)


def test_sem012_custom_metric_without_producer_only_warns():
    spec = _load_valid("E3-oxford-debate-unanimity-or-12-rounds.councilspec.json")
    spec["stopping"].pop("source_expression")
    spec["stopping"]["expression"] = {
        "any_of": [
            {"metric": "unanimity", "op": "==", "value": True},
            {"metric": "custom:owner_says_stop", "op": "==", "value": True,
             "value_type": "boolean"},
        ]
    }
    result = validate_spec(spec)
    assert result["ok"] is True, result["semantic_errors"]
    assert any("SEM-012" in w for w in result["warnings"])


def test_a_healthy_spec_produces_no_findings_at_all():
    """Detector control for the whole semantic layer: it must not fire on clean input."""
    spec = _load_valid("E4-release-readiness-board.councilspec.json")
    assert semantics.check(spec) == []


# ---------------------------------------------------------------- conformance runner


def test_conformance_runner_is_green_on_the_real_tree():
    ok, lines = run_conformance()
    assert ok, "\n".join(lines)
    assert len(lines) == len(MANIFEST["cases"])
    assert sum(1 for line in lines if line.startswith("PASS")) == 6
    assert sum(1 for line in lines if line.startswith("REJECTED")) == 10


def _copy_examples(tmp_path):
    dest = os.path.join(str(tmp_path), "examples")
    shutil.copytree(EXAMPLES_DIR, dest)
    return dest


def test_conformance_runner_fires_when_a_positive_is_broken(tmp_path):
    """Both-states: a green runner that cannot go red measures nothing."""
    dest = _copy_examples(tmp_path)
    target = os.path.join(dest, "valid", "E1-hundred-idea-brainstorm.councilspec.json")
    with open(target, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    spec["participants"]["count"]["min"] = 99
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    ok, lines = run_conformance(dest)
    assert ok is False
    assert any("expected to validate" in line for line in lines)


def test_conformance_runner_fires_when_a_negative_starts_passing(tmp_path):
    dest = _copy_examples(tmp_path)
    target = os.path.join(dest, "invalid", "N3-count-min-gt-max.councilspec.json")
    with open(target, "r", encoding="utf-8") as fh:
        spec = json.load(fh)
    spec["participants"]["count"]["min"] = 4          # repair the planted defect
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(spec, fh)
    ok, lines = run_conformance(dest)
    assert ok is False
    assert any("expected REJECTION" in line for line in lines)


def test_conformance_runner_fires_on_an_unlisted_example(tmp_path):
    dest = _copy_examples(tmp_path)
    shutil.copyfile(
        os.path.join(dest, "valid", "E1-hundred-idea-brainstorm.councilspec.json"),
        os.path.join(dest, "valid", "E99-not-in-manifest.councilspec.json"),
    )
    ok, lines = run_conformance(dest)
    assert ok is False
    assert any("not in EXPECTATIONS.json" in line for line in lines)


def test_conformance_runner_fires_when_a_manifest_file_is_missing(tmp_path):
    dest = _copy_examples(tmp_path)
    os.remove(os.path.join(dest, "invalid", "N7-delegation-cycle.councilspec.json"))
    ok, lines = run_conformance(dest)
    assert ok is False
    assert any(line.startswith("MISSING") for line in lines)


def test_cli_returns_terminal_state(capsys):
    from councilspec.validate import main

    rc = main(["--conformance"])
    out = capsys.readouterr().out
    assert rc == 0
    assert out.strip().endswith("SUCCESS:councilspec-conformance")

    rc = main([os.path.join(INVALID_DIR, "N1-typed-leaf-violation.councilspec.json")])
    out = capsys.readouterr().out
    assert rc == 1
    assert "FAILED:councilspec-validate" in out


# ------------------------------------------------------------------------- utilities


def _load_valid(name):
    with open(os.path.join(VALID_DIR, name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def _changed_top_level_keys(a, b):
    keys = set(a) | set(b)
    return {k for k in keys if a.get(k, object()) != b.get(k, object())}


def _minimal_spec(stop_tree):
    """Smallest schema-legal CouncilSpec wrapping a stopping expression."""
    return {
        "schema_version": "1.0.0",
        "council_id": "probe-minimal",
        "objective": {
            "statement": "probe instance for schema-legality of a parsed expression",
            "risk_tier": "low",
            "desired_output": "decision",
        },
        "participants": {"selection": {"mode": "automatic"}, "count": {"mode": "exact", "exact_n": 3}},
        "topology": {"kind": "flat"},
        "protocol": {"sequence": [{"kind": "brainstorm"}, {"kind": "synthesis"}]},
        "voting": {"method": "majority"},
        "stopping": {"expression": stop_tree},
        "targets": {"unique_ideas": 1000},
        "outcomes": {"allowed": ["decision", "proof_of_impossibility"]},
    }


def test_minimal_spec_helper_is_itself_valid():
    """If this helper drifted invalid, the parametrised legality test above would lie."""
    assert schema_errors(_minimal_spec({"metric": "unanimity", "op": "==", "value": True})) == []


def test_schema_path_points_at_the_shipped_contract():
    assert os.path.isfile(SCHEMA_PATH)
    assert SCHEMA_PATH.endswith(os.path.join("schema", "councilspec.schema.json"))
