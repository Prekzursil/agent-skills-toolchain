"""End-to-end tests for the scanner-detector-integrity probe (SPLIT out of BP-SEC-01, card 61).

Mechanism under test: the SAME instrument is run twice against two deliberately different
states, and BOTH halves must be asserted. A probe that only checks the broken half cannot tell
a working detector from one that always fires; a probe that only checks the clean half cannot
tell a working detector from one that never fires. The blueprint therefore carries two gates,
and this module proves neither can be deleted without detection.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "scanner-detector-integrity-probe"


@pytest.fixture(scope="module")
def doc() -> dict:
    return H.load(NAME)


def test_schema_and_semantics_are_clean(doc: dict) -> None:
    assert H.conformance_failures(doc) == []


def test_inline_units_pass_normative_and_strict(doc: dict) -> None:
    assert H.inline_units(doc)
    assert H.unit_profile_failures(doc, "normative") == []
    assert H.unit_profile_failures(doc, "strict") == []


def test_sentinels_name_their_own_units(doc: dict) -> None:
    assert H.sentinel_violations(doc) == []


def test_worked_example_conforms(doc: dict) -> None:
    assert H.worked_example_failures(doc) == []


def test_worked_example_checker_fires_on_a_dropped_binding(doc: dict) -> None:
    fails = H.worked_example_failures(H.mutated(doc, H.drop_a_required_binding))
    assert any("has no value in the worked example" in f for f in fails), fails


def test_worked_example_checker_fires_on_an_unknown_stage(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["expected_stage_path"].append("no-such-stage")

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("unknown stage" in f for f in fails), fails


# ------------------------------------------------------- mechanism: both halves are asserted


def test_the_same_instrument_runs_against_two_different_states(doc: dict) -> None:
    broken = H.stage(doc, "run-on-broken-state")
    clean = H.stage(doc, "run-on-clean-state")
    assert broken["role"] == clean["role"], "a second instrument would not be a control"
    # ordering: broken -> assert fired -> restore -> clean -> assert silent
    body_ids = [s["id"] for s in H.stage(doc, "probe-each-scanner")["body"]]
    assert body_ids == [
        "materialise-broken-state",
        "run-on-broken-state",
        "must-have-fired",
        "restore-clean-state",
        "run-on-clean-state",
        "must-be-silent",
    ], body_ids


def test_both_gates_exist_and_assert_opposite_outcomes(doc: dict) -> None:
    exprs = H.gate_expressions(doc)
    fired = exprs["fired-on-broken-state"]
    silent = exprs["silent-on-clean-state"]
    assert ">= 1" in fired and "broken_state" in fired
    assert "== 0" in silent and "clean_state" in silent
    assert fired != silent, "one gate cannot cover both states"
    assert H.stage(doc, "must-have-fired")["gate_ref"] == "fired-on-broken-state"
    assert H.stage(doc, "must-be-silent")["gate_ref"] == "silent-on-clean-state"


@pytest.mark.parametrize(
    "gate_name,stage_id",
    [
        ("fired-on-broken-state", "must-have-fired"),
        ("silent-on-clean-state", "must-be-silent"),
    ],
)
def test_deleting_either_half_is_detected(doc: dict, gate_name: str, stage_id: str) -> None:
    def bend(d: dict) -> None:
        del d["gates"][gate_name]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-005" in v and gate_name in v for v in violations), violations
    # The violation is reported by JSON pointer, not by stage id (measured: the message reads
    # "/stages/0/body/5"), so the stage identity is confirmed from the document instead.
    body = H.stage(doc, "probe-each-scanner")["body"]
    referencing = [s["id"] for s in body if s.get("gate_ref") == gate_name]
    assert referencing == [stage_id], referencing
    pointer_index = [s["id"] for s in body].index(stage_id)
    assert any(f"/body/{pointer_index}" in v for v in violations), violations


def test_a_one_sided_probe_would_not_satisfy_the_declared_mechanism(doc: dict) -> None:
    """Removing the clean-state run leaves a probe that cannot distinguish the two states."""

    def bend(d: dict) -> None:
        body = d["stages"][0]["body"]
        d["stages"][0]["body"] = [s for s in body if s["id"] != "run-on-clean-state"]

    mutant = H.mutated(doc, bend)
    ids = {s["id"] for s in mutant["stages"][0]["body"]}
    assert "run-on-clean-state" not in ids
    assert H.semantic_violations(mutant) != [], (
        "must-be-silent still depends on the deleted run, so DSL-SEM-002 must fire"
    )


# ------------------------------------------------------------- mechanism: fail closed


def test_unproven_is_gated_only_when_fail_closed_is_requested(doc: dict) -> None:
    gate = H.stage(doc, "unproven-gate")
    assert gate["when"] == "fail_closed == true"
    assert gate["gate_ref"] == "no-scanner-unproven"
    assert H.gate_expressions(doc)["no-scanner-unproven"] == "scanners_unproven == 0"
    assert doc["params"]["fail_closed"]["default"] is True, (
        "the safe posture must be the default, not the opt-in"
    )


def test_probe_never_touches_the_live_tree(doc: dict) -> None:
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy["network"] == "none"
    assert "platform/**" in policy["forbid_write_paths"]
    substrates = {
        u["execution_substrate"] for u in H.inline_units(doc)
    }
    assert substrates <= {"worktree-isolated", "local-serialized", "container"}, substrates
    assert doc["params"]["sandbox_substrate"]["enum"] == [
        "worktree-isolated",
        "container",
        "modal-sandbox",
    ]


def test_replay_is_fully_deterministic_here(doc: dict) -> None:
    """A detector control that cannot be replayed exactly is not a control."""
    replay = doc["replay"]
    assert replay["deterministic"] is True
    assert replay["verify"] == "hash-equal"
    assert replay["on_divergence"] == "fail"
    for source in ("clock", "random", "network", "filesystem-order", "process-id"):
        assert source in replay["forbid_nondeterministic_sources"]


def test_dropping_the_seed_from_a_deterministic_replay_is_rejected(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["replay"]["seed"]

    errs = H.schema_errors(H.mutated(doc, bend))
    assert any("seed" in e for e in errs), errs
