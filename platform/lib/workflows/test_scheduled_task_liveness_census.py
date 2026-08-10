"""FLAGSHIP end-to-end test for `scheduled-task-liveness-census` (bp-8, slot 95, BP-MNT-04).

Mechanism claims under test: task STATE and output FRESHNESS are two independent signals measured
by two roles that are forbidden from reading each other's field, and only their PAIRING is a
verdict; a task with NO oracle is a gap that must be reported and must NOT be counted healthy - the
most valuable output of a first run; a non-zero last-result code is not automatically a failure,
because a single-instance refusal is a designed steady state; power-off windows are subtracted
before an output is called stale, so a weekend is not an alarm; and a task that cannot be triggered
is exactly why this census pairs a declarative state with an artifact age instead of triggering.

Every check ships with a targeted mutant and is asserted to FAIL on it.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp8_testkit as K
import pytest

WORKFLOW_ID = "scheduled-task-liveness-census"
DOC = K.load(WORKFLOW_ID)


# ------------------------------------------------------------------------------- the checks


def check_the_two_signals_are_read_by_different_roles(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-independence")
    assert "state_read_by_enumerator == true" in spec["expression"]
    assert "freshness_read_by_oracle == true" in spec["expression"]
    assert "oracle_read_task_state == false" in spec["expression"], (
        "an oracle that peeks at task state is not a second signal"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert K.stage(doc, "enumerate-and-decode")["role"] == "task-enumerator"
    assert K.stage(doc, "measure-one-oracle")["role"] == "freshness-oracle"
    assert K.stage(doc, "pair-and-classify")["role"] == "pairing-adjudicator"


def check_the_pairing_cannot_happen_before_independence_is_proven(
    doc: Mapping[str, Any],
) -> None:
    order = K.top_level_stage_ids(doc)
    K.assert_precedes(order, "enumerate-and-decode", "gate-result-codes")
    K.assert_precedes(order, "gate-result-codes", "measure-freshness")
    K.assert_precedes(order, "measure-freshness", "gate-independence")
    K.assert_precedes(order, "gate-independence", "pair-and-classify")
    assert K.depends_on(doc, "pair-and-classify") == ["gate-independence"], (
        "the join must be reachable only through the independence gate"
    )


def check_the_adjudicator_is_a_cross_examining_veto(doc: Mapping[str, Any]) -> None:
    adjudicator = doc["roles"]["pairing-adjudicator"]
    assert adjudicator["authority"] == "veto"
    assert adjudicator["independence"] == "cross-examining"
    assert "Bash:pwsh" not in adjudicator["tool_permissions"], (
        "the adjudicator must not be able to re-read the scheduler and become a third instrument"
    )
    assert "Bash:python" not in adjudicator["tool_permissions"]
    routes = K.routes_for(doc, "pairing-adjudicator")
    assert routes and routes[0]["target"]["effort"] == "high", (
        "the pairing is the whole idea; that is where effort belongs"
    )


def check_no_oracle_is_a_gap_not_a_pass(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-no-oracle")
    assert "tasks_without_oracle_reported == true" in spec["expression"]
    assert "tasks_without_oracle_counted_as_healthy == false" in spec["expression"], (
        "an unmonitorable task silently counted healthy is the defect this census exists for"
    )
    assert spec["blocking"] is True and spec["on_fail"] == "fail"
    assert "no-oracle-counted-healthy" in doc["retry_policy"]["no_retry_on"]
    assert "oracle-path-absent" in doc["failure_policy"]["classify_as"]


def check_a_nonzero_result_code_is_decoded_not_assumed(doc: Mapping[str, Any]) -> None:
    spec = K.gate_for_stage(doc, "gate-result-codes")
    assert (
        "nonzero_results_classified == nonzero_results_found" in spec["expression"]
    ), "an undecoded non-zero code is an unclassified task, not a failing one"
    assert "expected_refusals_not_counted_as_failing == true" in spec["expression"]
    designed = doc["params"]["designed_nonzero_results"]
    assert designed["type"] == "array" and designed["min_items"] == 0, (
        "the designed-refusal list must be declarable and may legitimately be empty"
    )
    assert "result-code-undecoded" in doc["retry_policy"]["no_retry_on"]
    ids = {c["id"] for c in K.benchmark_cases(doc)}
    assert "designed-refusal" in ids


def check_power_off_windows_are_subtracted_before_staleness(
    doc: Mapping[str, Any],
) -> None:
    spec = doc["params"]["power_off_windows"]
    props = spec["items"]["properties"]
    assert {"from", "to"} <= set(props), "a window with no bounds cannot be subtracted"
    assert spec["min_items"] == 0, (
        "a box that never sleeps declares an empty list, not none"
    )
    cases = {c["id"]: c for c in K.benchmark_cases(doc)}
    assert "weekend-not-an-alarm" in cases, (
        "without this case the census would alarm on every power-off window"
    )
    assert "HEALTHY" in cases["weekend-not-an-alarm"]["expect"]


def check_the_oracle_declares_a_cadence_and_a_signal(doc: Mapping[str, Any]) -> None:
    spec = doc["params"]["output_oracles"]
    props = spec["items"]["properties"]
    for field in ("task", "path", "expected_cadence_seconds", "freshness_signal"):
        assert field in props, f"an oracle with no {field!r} cannot judge freshness"
    assert props["expected_cadence_seconds"]["minimum"] >= 1, (
        "a zero cadence makes every output instantly stale"
    )
    assert spec["min_items"] >= 1, "a census with no oracle at all is a state snapshot"


def check_a_green_but_dead_task_escalates(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "green-but-dead-found")
    assert "green_but_dead > 0" in rule["expression"]
    assert rule["on_stop"] == "escalate"
    complete = K.stopping_rule(doc, "every-task-classified")
    assert "tasks_classified == tasks_enumerated" in complete["expression"], (
        "classifying a subset and reporting completion is the floor-as-total defect"
    )
    assert "census_complete == true" in complete["minimum_conditions"]


def check_an_incomplete_census_is_partial_not_complete(doc: Mapping[str, Any]) -> None:
    rule = K.stopping_rule(doc, "census-incomplete")
    assert "census_complete == false" in rule["expression"]
    assert rule["on_stop"] == "emit-partial"
    spec = K.barrier(doc, "measure-freshness")
    K.assert_rejects_fire_and_forget(spec)
    assert spec["mode"] == "deadline" and spec["deadline_seconds"] > 0
    assert spec["on_partial"] == "proceed-degraded"
    assert doc["failure_policy"]["on_failure"] == "degrade-loudly"
    assert doc["failure_policy"]["never_silent"] is True


def check_a_single_signal_verdict_is_never_retried(doc: Mapping[str, Any]) -> None:
    no_retry = set(doc["retry_policy"]["no_retry_on"])
    assert "single-signal-verdict" in no_retry, (
        "a one-signal verdict is a category error, not a transient failure"
    )
    assert "scheduler-api-unavailable" in doc["retry_policy"]["retry_on"], (
        "a genuinely transient scheduler failure IS the retryable case"
    )
    assert "single-signal-verdict" in doc["failure_policy"]["classify_as"]


def check_the_census_cannot_touch_the_system_it_reads(doc: Mapping[str, Any]) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert "C:/Windows/**" in policy["forbid_write_paths"]
    assert "Bash:pwsh" in policy["require_owner_approval"]
    assert policy["write_paths"] == ["command-center/census/**"]
    forbidden = set(doc["dry_run"]["forbid_tools"])
    assert {"Bash:pwsh", "Bash:python"} <= forbidden


def check_it_does_not_pretend_to_trigger_anything(doc: Mapping[str, Any]) -> None:
    kinds = {str(st.get("kind")) for _, st in K.stages(doc)}
    assert "loop" not in kinds and "repair_loop" not in kinds, (
        "a scheduled task's cadence IS the subject; a retry loop around it would fake the cadence"
    )
    reason = K.ext(doc, "not_a_duplicate_because")
    assert "vs_firing-path-revalidation" in reason, (
        "the trigger-vs-pairing distinction must be stated against the workflow it is nearest to"
    )
    assert "cannot trigger" in reason["vs_firing-path-revalidation"]


def check_the_worked_example_shows_all_four_decodings(doc: Mapping[str, Any]) -> None:
    census = K.worked_examples(doc)[0]["census"]
    verdicts = {row["verdict"] for row in census}
    for needed in ("EXPECTED-REFUSAL", "GREEN-BUT-DEAD", "HEALTHY", "NO-ORACLE"):
        assert needed in verdicts, f"the worked example never demonstrates {needed}"
    refusal = next(r for r in census if r["verdict"] == "EXPECTED-REFUSAL")
    assert refusal["last_result_raw"] not in ("0x0", "0"), (
        "the designed-refusal row must carry a NON-zero raw code or it proves nothing"
    )
    dead = next(r for r in census if r["verdict"] == "GREEN-BUT-DEAD")
    assert dead["last_result_raw"] == "0x0" and dead["state"] == "Ready", (
        "the green-but-dead row must look healthy on the state signal alone"
    )
    no_oracle = next(r for r in census if r["verdict"] == "NO-ORACLE")
    assert no_oracle["output_adjusted_age_seconds"] is None, (
        "a NO-ORACLE row must carry no age at all, not a zero that reads as fresh"
    )


ALL_CHECKS = (
    check_the_two_signals_are_read_by_different_roles,
    check_the_pairing_cannot_happen_before_independence_is_proven,
    check_the_adjudicator_is_a_cross_examining_veto,
    check_no_oracle_is_a_gap_not_a_pass,
    check_a_nonzero_result_code_is_decoded_not_assumed,
    check_power_off_windows_are_subtracted_before_staleness,
    check_the_oracle_declares_a_cadence_and_a_signal,
    check_a_green_but_dead_task_escalates,
    check_an_incomplete_census_is_partial_not_complete,
    check_a_single_signal_verdict_is_never_retried,
    check_the_census_cannot_touch_the_system_it_reads,
    check_it_does_not_pretend_to_trigger_anything,
    check_the_worked_example_shows_all_four_decodings,
)


@pytest.mark.parametrize("check", ALL_CHECKS, ids=lambda c: c.__name__)
def test_shipped_blueprint_satisfies_every_mechanism_check(check: Any) -> None:
    check(DOC)


def test_shipped_blueprint_is_conformant() -> None:
    assert K.schema_errors(DOC) == []
    assert K.semantic_violations(DOC) == []
    assert K.blueprint_meta(DOC)["slot"] == 95
    assert K.blueprint_meta(DOC)["design_card"] == "BP-MNT-04"
    assert DOC["flagship"] is True


# ------------------------------------------------------------------------- mutation controls


def _let_the_oracle_read_task_state(doc: dict) -> None:
    doc["gates"]["signals-are-independent"]["expression"] = (
        "state_read_by_enumerator == true AND freshness_read_by_oracle == true"
    )


def _pair_before_the_independence_gate(doc: dict) -> None:
    K.find_stage_mut(doc, "pair-and-classify")["depends_on"] = ["measure-freshness"]


def _give_the_adjudicator_the_scheduler(doc: dict) -> None:
    doc["roles"]["pairing-adjudicator"]["tool_permissions"].append("Bash:pwsh")


def _count_an_unmonitored_task_as_healthy(doc: dict) -> None:
    doc["gates"]["no-oracle-is-a-gap"]["expression"] = (
        "tasks_without_oracle_reported == true"
    )


def _assume_every_nonzero_code_is_a_failure(doc: dict) -> None:
    doc["gates"]["result-codes-decoded"]["expression"] = (
        "nonzero_results_classified == nonzero_results_found"
    )


def _drop_the_power_off_window_bounds(doc: dict) -> None:
    doc["params"]["power_off_windows"]["items"]["properties"].pop("to")


def _drop_the_cadence_from_the_oracle(doc: dict) -> None:
    doc["params"]["output_oracles"]["items"]["properties"].pop(
        "expected_cadence_seconds"
    )


def _let_a_dead_task_complete(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "green-but-dead-found":
            rule["on_stop"] = "complete"


def _hide_an_incomplete_census(doc: dict) -> None:
    for rule in doc["stopping_rules"]:
        if rule["id"] == "census-incomplete":
            rule["on_stop"] = "complete"
    doc["failure_policy"]["never_silent"] = False


def _retry_a_single_signal_verdict(doc: dict) -> None:
    doc["retry_policy"]["no_retry_on"] = ["result-code-undecoded"]


def _allow_writes_into_windows(doc: dict) -> None:
    doc["tool_policy"]["forbid_write_paths"] = ["platform/schema/**"]


def _wrap_the_census_in_a_retry_loop(doc: dict) -> None:
    doc["stages"].append(
        {
            "id": "retry-the-cadence",
            "title": "pretend a scheduled task can be triggered",
            "kind": "loop",
            "depends_on": ["gate-no-oracle"],
            "loop_var": "attempt",
            "timeout_seconds": 600,
            "convergence": {
                "max_iterations": 3,
                "converged_when": "tasks_classified == tasks_enumerated",
                "metrics": [
                    {"name": "tasks_classified", "direction": "increase", "target": 1}
                ],
                "on_no_convergence": "escalate",
            },
            "body": [
                {
                    "id": "retry-body",
                    "kind": "task",
                    "role": "task-enumerator",
                    "timeout_seconds": 300,
                }
            ],
        }
    )


def _drop_the_no_oracle_row_from_the_example(doc: dict) -> None:
    example = doc["x_extensions"]["worked_examples"][0]
    example["census"] = [r for r in example["census"] if r["verdict"] != "NO-ORACLE"]


MUTATIONS = (
    (
        check_the_two_signals_are_read_by_different_roles,
        _let_the_oracle_read_task_state,
    ),
    (
        check_the_pairing_cannot_happen_before_independence_is_proven,
        _pair_before_the_independence_gate,
    ),
    (
        check_the_adjudicator_is_a_cross_examining_veto,
        _give_the_adjudicator_the_scheduler,
    ),
    (check_no_oracle_is_a_gap_not_a_pass, _count_an_unmonitored_task_as_healthy),
    (
        check_a_nonzero_result_code_is_decoded_not_assumed,
        _assume_every_nonzero_code_is_a_failure,
    ),
    (
        check_power_off_windows_are_subtracted_before_staleness,
        _drop_the_power_off_window_bounds,
    ),
    (
        check_the_oracle_declares_a_cadence_and_a_signal,
        _drop_the_cadence_from_the_oracle,
    ),
    (check_a_green_but_dead_task_escalates, _let_a_dead_task_complete),
    (check_an_incomplete_census_is_partial_not_complete, _hide_an_incomplete_census),
    (check_a_single_signal_verdict_is_never_retried, _retry_a_single_signal_verdict),
    (check_the_census_cannot_touch_the_system_it_reads, _allow_writes_into_windows),
    (check_it_does_not_pretend_to_trigger_anything, _wrap_the_census_in_a_retry_loop),
    (
        check_the_worked_example_shows_all_four_decodings,
        _drop_the_no_oracle_row_from_the_example,
    ),
)


@pytest.mark.parametrize(
    "check,mutate", MUTATIONS, ids=lambda v: getattr(v, "__name__", "")
)
def test_each_check_fails_on_its_mutated_blueprint(check: Any, mutate: Any) -> None:
    broken = K.mutant(DOC, mutate)
    assert K.raises_assertion(check, broken), (
        f"{check.__name__} stayed silent on the mutated blueprint, so it measures nothing"
    )


def test_the_oracle_peeking_mutant_is_schema_legal() -> None:
    """Collapsing two signals into one is valid DSL and reads exactly like the real thing."""
    broken = K.mutant(DOC, _let_the_oracle_read_task_state)
    assert K.schema_errors(broken) == []
    assert K.semantic_violations(broken) == []
    assert K.raises_assertion(check_the_two_signals_are_read_by_different_roles, broken)
