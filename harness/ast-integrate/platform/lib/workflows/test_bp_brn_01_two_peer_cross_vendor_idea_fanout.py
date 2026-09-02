"""FLAGSHIP end-to-end test: BP-BRN-01 Two-Peer Cross-Vendor Idea Fan-out.

The measured failure this blueprint repairs was in the ADAPTER, not the vendor: three
cross-vendor agents produced zero artifacts, an inline prompt blew the OS command-line limit, a
backgrounded job's result was unreachable, and one agent forwarded a progress stream as its
terminal answer. So the tests here are dispatch-contract tests:

* the prompt travels BY FILE;
* the dispatch BLOCKS and may never return a receipt;
* acceptance is an AND-gate of three signals, because exit zero alone is SEVERED;
* the repair loop retries ONCE and carries an INDEPENDENT verify.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp1_testkit as K  # noqa: E402

BP = "bp-brn-01-two-peer-cross-vendor-idea-fanout"
RECEIPT_PATTERNS = ("started in the background", "Check /codex:status")


@pytest.fixture(scope="module")
def doc() -> dict:
    return K.load(BP)


def test_validates_and_is_flagship(doc):
    assert K.schema_errors(doc) == []
    assert K.semantic_violations(doc) == []
    assert doc["flagship"] is True


def test_the_worked_example_plans_end_to_end(doc):
    ex = K.example(doc)
    plan = K.plan_from_example(doc)
    assert plan.stage_order == ex["expected_stage_order"]
    assert plan.kinds() == {"fanout": 1, "gate": 3, "repair_loop": 1, "task": 6}
    assert sorted(g.stage_id for g in plan.gates) == sorted(ex["expected_gate_ids"])


def test_the_prompt_travels_by_file_and_is_marshalled_first(doc):
    plan = K.plan_from_example(doc)
    assert plan.stage_order[0] == "marshal-prompt"
    unit = K.stage(doc, "marshal-prompt")["work_unit"]
    assert "never inline" in unit["title"]
    assert "win-arg-limit" in unit["failure_classification"]
    tests = " | ".join(unit["tests_required"])
    assert "larger than the OS command-line limit" in tests
    assert "byte count" in unit["evidence_requirement"]


def test_the_dispatch_blocks_and_a_receipt_is_never_a_result(doc):
    peer = K.stage(doc, "dispatch-peer")["work_unit"]
    target = peer["question_or_target"]
    assert "BLOCK until it finishes" in target
    assert "Never background" in target
    assert "never return a job id" in target
    assert "progress stream" in target
    fanout = K.stage(doc, "dispatch-peers")
    for pattern in RECEIPT_PATTERNS:
        assert pattern in fanout["barrier"]["reject_result_matching"]
    assert fanout["barrier"]["verify_artifact_exists"] is True
    assert "elapsed wall-clock" in peer["evidence_requirement"], (
        "a turn count is not evidence a call blocked; wall-clock delta is"
    )


def test_acceptance_is_a_three_signal_and_gate_not_an_exit_code(doc):
    gate = doc["gates"]["dispatch-and-gate"]
    assert (
        "peer_results_exit_zero_and_nonempty_and_schema_valid == peer_results_total"
        in gate["expression"]
    )
    assert "receipt_string_results == 0" in gate["expression"]
    assert "peer_results_total > 0" in gate["expression"], (
        "zero peers must not satisfy the gate vacuously"
    )
    assert gate["blocking"] is True
    audit = K.stage(doc, "audit-dispatch")["work_unit"]
    tests = " | ".join(audit["tests_required"])
    assert "EMPTY output file must be SEVERED" in tests
    assert "schema-invalid but non-empty" in tests
    assert audit["assigned_model_vendor_role"]["model"] == "none-deterministic-script"


def test_the_repair_loop_is_bounded_and_carries_an_independent_verify(doc):
    repair = K.stage(doc, "repair-dispatch")
    assert repair["kind"] == "repair_loop"
    assert repair["target"] == ["dispatch-peers"]
    assert repair["max_attempts"] == 2, (
        "two strikes then stop; a third attempt is the anti-grind violation"
    )
    assert repair["require_root_cause"] is True
    assert set(repair["classification_filter"]) >= {"win-arg-limit", "severed-stream"}
    verify = repair["verify"]
    assert verify["kind"] == "gate"
    assert verify["gate"]["blocking"] is True
    assert (
        "retried_peers_exit_zero_and_nonempty_and_schema_valid == retried_peers_total"
        in verify["gate"]["expression"]
    )
    assert verify["gate"]["on_fail"] == "escalate-to-human"
    assert repair["diagnose"]["id"] == "diagnose-dispatch"
    assert repair["repair"]["id"] == "apply-scoped-retry"


def test_the_retry_is_class_specific_and_happens_at_most_once(doc):
    unit = K.stage(doc, "apply-scoped-retry")["work_unit"]
    assert "exactly once" in unit["question_or_target"]
    assert "scoped configuration" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "at most ONCE" in tests
    assert "terminal FAILED marker" in tests
    assert unit["retry_policy"].startswith("none"), (
        "the repair loop IS the bounded retry"
    )


def test_the_peers_are_cross_vendor_and_blind_to_each_other(doc):
    role = doc["roles"]["cross-vendor-peer"]
    assert role["vendor"] == "openai"
    assert role["cross_vendor_required"] is True
    assert role["independence"] == "independent"
    assert "NO sight of any sibling peer" in role["description"]
    assert role["min_participants"] >= 2, (
        "one peer cannot be cross-checked for independence"
    )
    gate = doc["gates"]["independence-preserved"]
    assert "peers_that_saw_a_sibling_output == 0" in gate["expression"]
    assert "peers_returning_terminal_state == peer_results_total" in gate["expression"]


def test_two_peers_is_a_floor_not_a_default(doc):
    params = doc["params"]
    assert params["n_peers"]["minimum"] == 2
    assert params["peer_models"]["min_items"] == 2
    assert params["peer_models"]["required"] is True
    assert params["dispatch_timeout_seconds"]["minimum"] >= 300, (
        "an explicit timeout is mandatory; the silent default is what a fire-and-forget dispatch "
        "was once rationalised to escape"
    )


def test_the_synthesis_keeps_novel_to_one_peer_separate_from_consensus(doc):
    unit = K.stage(doc, "synthesise")["work_unit"]
    assert "novel-to-one-peer" in unit["question_or_target"]
    assert "never folded" in unit["question_or_target"]
    tests = " | ".join(unit["tests_required"])
    assert "must appear in novel-to-one-peer, not in merged" in tests
    assert "one peer returned SUCCESS" in tests
    assert "independence-lost" in unit["failure_classification"]


def test_a_single_surviving_peer_is_reported_as_lost_independence(doc):
    control = next(
        c
        for c in K.example(doc)["stopping_rule_controls"]
        if c["rule"] == "independence-lost"
    )
    K.stopping_both_states(doc, control)
    fires = K.D.check_stopping_rules(doc, control["fires_on"])
    row = next(r for r in fires["rules"] if r["id"] == "independence-lost")
    assert row["on_stop"] == "emit-partial", (
        "one peer is not consensus; the run must emit partial rather than complete"
    )


def test_stopping_rules_hold_in_both_states(doc):
    for control in K.example(doc)["stopping_rule_controls"]:
        K.stopping_both_states(doc, control)


# ------------------------------------------------------------- mutation controls


def test_mutation_weakening_the_and_gate_to_an_exit_code_is_detectable(doc):
    def three_signals(d) -> bool:
        expr = d["gates"]["dispatch-and-gate"]["expression"]
        return (
            "exit_zero_and_nonempty_and_schema_valid" in expr
            and "receipt_string_results == 0" in expr
        )

    K.both_states(
        doc,
        lambda d: d["gates"]["dispatch-and-gate"].__setitem__(
            "expression", "peer_results_exit_zero == peer_results_total"
        ),
        three_signals,
        "acceptance reduced to an exit code",
    )


def test_mutation_removing_the_receipt_rejection_patterns_is_detectable(doc):
    def receipts_rejected(d) -> bool:
        patterns = K.stage(d, "dispatch-peers")["barrier"]["reject_result_matching"]
        return all(p in patterns for p in RECEIPT_PATTERNS)

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "dispatch-peers":
                st["barrier"]["reject_result_matching"] = []

    K.both_states(
        doc, mutate, receipts_rejected, "a background receipt could be parsed as ideas"
    )


def test_mutation_raising_the_repair_attempt_cap_is_detectable(doc):
    def two_strikes(d) -> bool:
        return K.stage(d, "repair-dispatch")["max_attempts"] == 2

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "repair-dispatch":
                st["max_attempts"] = 8

    K.both_states(doc, mutate, two_strikes, "repair loop allowed to grind")


def test_mutation_deleting_the_repair_verify_stage_is_schema_rejected(doc):
    """A repair loop without an independent verify is a retry that reports success."""

    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "repair-dispatch":
                st.pop("verify", None)

    K.both_states(doc, mutate, K.is_conformant, "repair loop without a verify stage")


def test_mutation_pointing_the_repair_at_a_nonexistent_stage_is_rejected(doc):
    def mutate(d):
        for st in d["stages"]:
            if st.get("id") == "repair-dispatch":
                st["target"] = ["stage-that-does-not-exist"]

    K.both_states(doc, mutate, K.is_conformant, "repair loop targeting nothing")


def test_mutation_collapsing_the_peers_to_one_vendor_is_detectable(doc):
    def cross_vendor(d) -> bool:
        role = d["roles"]["cross-vendor-peer"]
        return role["vendor"] == "openai" and role.get("cross_vendor_required") is True

    K.both_states(
        doc,
        lambda d: d["roles"]["cross-vendor-peer"].update(
            {"vendor": "anthropic", "cross_vendor_required": False, "model": "opus"}
        ),
        cross_vendor,
        "the peers stopped being cross-vendor, which is the entire premise",
    )


def test_mutation_allowing_one_peer_is_detectable(doc):
    def two_peer_floor(d) -> bool:
        return (
            d["params"]["peer_models"]["min_items"] >= 2
            and d["params"]["n_peers"]["minimum"] >= 2
        )

    def mutate(d):
        d["params"]["peer_models"]["min_items"] = 1
        d["params"]["n_peers"]["minimum"] = 1

    K.both_states(doc, mutate, two_peer_floor, "a single peer would pass as a fan-out")
