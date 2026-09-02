"""End-to-end tests for the BP-SEC-01 blueprint (card 61).

Mechanism under test: BOTH arms are mandatory (deterministic scanners AND a reasoned review),
the scanner-integrity subworkflow runs FIRST so a scanner's silence is only trusted once it has
been shown able to fire, and every finding enters a BOUNDED fix-then-rescan loop.

Every mechanism assertion is paired with a mutation control: the same assertion is re-run against
a document with that mechanism removed, and must fail there. An assertion that passes in both
states measures nothing.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "security-review-scanner-fix-loop"


@pytest.fixture(scope="module")
def doc() -> dict:
    return H.load(NAME)


# ------------------------------------------------------------------------- conformance


def test_schema_and_semantics_are_clean(doc: dict) -> None:
    assert H.conformance_failures(doc) == []


def test_inline_units_pass_the_strictest_work_unit_profile(doc: dict) -> None:
    assert H.inline_units(doc), (
        "a task-bearing blueprint with no inline unit proves nothing"
    )
    assert H.unit_profile_failures(doc, "normative") == []
    assert H.unit_profile_failures(doc, "strict") == []


def test_every_inline_sentinel_names_its_own_unit(doc: dict) -> None:
    assert H.sentinel_violations(doc) == []


# --------------------------------------------------------------- worked example (both states)


def test_worked_example_conforms(doc: dict) -> None:
    assert H.worked_example_failures(doc) == []


def test_worked_example_checker_fires_when_a_required_binding_is_dropped(
    doc: dict,
) -> None:
    mutant = H.mutated(doc, H.drop_a_required_binding)
    fails = H.worked_example_failures(mutant)
    assert any("has no value in the worked example" in f for f in fails), fails


def test_worked_example_checker_fires_on_an_undeclared_artifact(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["expected_artifacts"].append(
            "command-center/security/not-produced-anywhere.json"
        )

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("is not declared by any stage or output" in f for f in fails), fails


# ------------------------------------------------------------------ mechanism: both arms


def test_both_arms_are_present_and_ordered(doc: dict) -> None:
    """The scanner arm and the reasoning arm both exist, and the review depends on the scans."""
    scan = H.stage(doc, "scan-one")
    review = H.stage(doc, "reasoned-review")
    assert scan["kind"] == "task" and review["kind"] == "task"
    assert review["depends_on"] == ["run-scanners"], (
        "the reasoned review must consume the scanner output, not run beside it"
    )
    scanner_tools = {
        t
        for t in H.all_tool_tokens(doc)
        if t.startswith("Bash:") and t != "Bash:python"
    }
    assert len(scanner_tools) >= 3, (
        f"expected several pinned scanners, got {scanner_tools}"
    )


def test_removing_the_scanner_arm_leaves_a_detectable_dangling_dependency(
    doc: dict,
) -> None:
    """Delete the scanner arm and do NOT repair the reference - repairing it would make the
    control self-defeating, which is exactly how this test failed on its first run."""

    def bend(d: dict) -> None:
        d["stages"] = [s for s in d["stages"] if s["id"] != "run-scanners"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-002" in v and "run-scanners" in v for v in violations), (
        violations
    )


# ---------------------------------------------- mechanism: detector integrity gates the silence


def test_detector_probe_runs_before_any_scan_and_gates_it(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order.index("prove-scanners-can-fire") < order.index("run-scanners")
    gate = H.stage(doc, "detector-gate")
    assert gate["gate_ref"] == "scanner-silence-is-trustworthy"
    assert H.stage(doc, "run-scanners")["depends_on"] == ["detector-gate"]
    expr = H.gate_expressions(doc)["scanner-silence-is-trustworthy"]
    assert "scanner_detector_state" in expr and "GREEN" in expr


def test_the_probe_is_a_real_subworkflow_reference_to_a_file_on_disk(doc: dict) -> None:
    ref = H.stage(doc, "prove-scanners-can-fire")["workflow"]["workflow_id"]
    declared = doc["subworkflows"][ref]
    assert declared["source"] == f"platform/workflows/{ref}.json"
    child = H.load(ref)
    assert child["id"] == ref
    assert child["kind"] == "subworkflow"
    assert H.conformance_failures(child) == [], (
        "the referenced child must itself be valid"
    )


def test_removing_the_detector_gate_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["gates"]["scanner-silence-is-trustworthy"]

    mutant = H.mutated(doc, bend)
    violations = H.semantic_violations(mutant)
    assert any("DSL-SEM-005" in v for v in violations), violations


# ----------------------------------------------------------- mechanism: bounded fix loop


def test_fix_loop_is_bounded_and_has_an_anti_grind_exit(doc: dict) -> None:
    loop = H.stage(doc, "fix-loop")
    conv = loop["convergence"]
    assert loop["kind"] == "loop"
    assert 1 <= conv["max_iterations"] <= 10, (
        "an unbounded fix loop is the failure mode"
    )
    assert conv["no_progress_rounds"] >= 1, "no anti-grind exit"
    assert conv["on_no_convergence"] == "escalate"
    declared_metrics = {m["name"] for m in conv["metrics"]}
    assert "findings_without_disposition" in declared_metrics
    # the loop rescans after fixing - a fix with no re-measure is not a loop
    assert H.stage(doc, "rescan")["depends_on"] == ["apply-fix"]


def test_an_unbounded_loop_would_be_rejected_by_the_schema(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "fix-loop":
                del s["convergence"]["max_iterations"]

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("max_iterations" in e for e in errs), errs


def test_convergence_metric_must_be_declared(doc: dict) -> None:
    """A convergence expression naming an undeclared metric can never fire."""

    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "fix-loop":
                s["convergence"]["converged_when"] = "undeclared_metric == 0"

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-008" in v for v in violations), violations


# ------------------------------------------------------- mechanism: residual risk is named


def test_residual_risk_is_owner_accepted_not_omitted(doc: dict) -> None:
    record = H.stage(doc, "record-residual")
    assert record["work_unit"]["owner_approval_required"] is True
    checkpoint = H.stage(doc, "owner-accept-residual")
    assert checkpoint["kind"] == "human_checkpoint"
    assert checkpoint["approval_mode"] == "owner-only"
    assert checkpoint["on_timeout"] in {"fail", "escalate"}, (
        "an unanswered risk acceptance must never resolve to proceed"
    )
    assert "command-center/security/residual-risk-ledger.json" in H.declared_paths(doc)


def test_a_proceed_on_timeout_would_be_caught_by_this_assertion(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "owner-accept-residual":
                s["on_timeout"] = "proceed"

    mutant = H.mutated(doc, bend)
    assert H.stage(mutant, "owner-accept-residual")["on_timeout"] == "proceed"
    with pytest.raises(AssertionError):
        assert H.stage(mutant, "owner-accept-residual")["on_timeout"] in {
            "fail",
            "escalate",
        }


# ------------------------------------------------------------------- policy is deny-by-default


def test_tool_policy_is_deny_by_default_and_closed_over_every_request(
    doc: dict,
) -> None:
    assert doc["tool_policy"]["default"] == "deny"
    missing = H.contains_all(
        doc["tool_policy"]["allow"], sorted(H.all_tool_tokens(doc))
    )
    assert missing == [], f"tools requested but not allowed: {missing}"


def test_an_unpermitted_tool_is_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["roles"]["fixer"]["tool_permissions"].append("Bash:curl")

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-011" in v for v in violations), violations
