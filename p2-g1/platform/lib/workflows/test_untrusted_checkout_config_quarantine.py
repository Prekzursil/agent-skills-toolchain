"""End-to-end tests for BP-SEC-03 (card 63), the untrusted-checkout config quarantine.

Mechanism under test: containment happens BEFORE the risky action, the scan is agent-free and
deterministic, quarantine is a rename-aside that preserves bytes (never a delete), and the verdict
defaults to FALSE under adverse inference when the scan is incomplete.
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "untrusted-checkout-config-quarantine"


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


def test_worked_example_checker_fires_when_a_stage_is_both_walked_and_skipped(
    doc: dict,
) -> None:
    def bend(d: dict) -> None:
        ex = d["x_extensions"]["worked_example"]
        ex["skipped_stages"] = [ex["expected_stage_path"][0]]
        ex["skipped_because"] = "deliberately contradictory, for the control"

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("both walked and skipped" in f for f in fails), fails


# ------------------------------------------------- mechanism: containment precedes the action


def test_the_scan_precedes_every_other_stage_and_gates_entry(doc: dict) -> None:
    order = H.top_level_stage_ids(doc)
    assert order[0] == "scan-auto-load-surfaces"
    assert order[-1] == "entry-verdict"
    assert order.index("completeness-gate") < order.index("classify-execution-risk")
    assert order.index("containment-gate") < order.index("entry-verdict")


def test_the_scan_never_executes_what_it_finds(doc: dict) -> None:
    tokens = H.all_tool_tokens(doc)
    assert "Bash" not in tokens
    assert doc["tool_policy"]["network"] == "none"
    assert "mcp__codex__codex" in doc["tool_policy"]["deny"]
    # every requested tool is read-shaped or a scoped write into the trust tree
    for token in tokens:
        assert token.startswith(
            ("Read", "Glob", "Grep", "Bash:python", "Write(command-center/")
        ), token


# -------------------------------------------------- mechanism: rename-aside, never delete


def test_quarantine_is_serialized_and_asserts_byte_preservation(doc: dict) -> None:
    fan = H.stage(doc, "quarantine-executables")
    assert fan["kind"] == "fanout"
    assert fan["max_concurrency"] == 1, (
        "two concurrent moves against one tree would each be the other's residue"
    )
    assert fan["on_item_failure"] == "abort"
    unit = H.stage(doc, "rename-aside-one")["work_unit"]
    ev = unit["evidence_requirement"]
    assert "pre-move sha256" in ev and "post-move sha256" in ev
    assert "negative existence probe" in ev, (
        "without a negative probe a move that silently failed reads as success"
    )
    assert "quarantine-by-delete" in unit["failure_classification"]


def test_the_containment_gate_rejects_both_residue_and_deletion(doc: dict) -> None:
    expr = H.gate_expressions(doc)["no-executable-surface-live"]
    assert "executable_surfaces_still_in_place == 0" in expr
    assert "quarantined_by_delete == 0" in expr, (
        "a gate that only checks 'nothing left in place' would accept deletion"
    )


def test_removing_the_delete_clause_weakens_the_gate_detectably(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["no-executable-surface-live"]["expression"] = (
            "executable_surfaces_still_in_place == 0"
        )

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == [], (
        "the mutant is still schema-valid on purpose"
    )
    assert (
        "quarantined_by_delete"
        not in H.gate_expressions(mutant)["no-executable-surface-live"]
    )
    with pytest.raises(AssertionError):
        assert (
            "quarantined_by_delete == 0"
            in H.gate_expressions(mutant)["no-executable-surface-live"]
        )


# ------------------------------------------------------- mechanism: adverse inference default


def test_an_incomplete_scan_cannot_certify_entry(doc: dict) -> None:
    expr = H.gate_expressions(doc)["scan-complete-or-unsafe"]
    assert "patterns_scanned == patterns_requested" in expr
    assert "scan_errors == 0" in expr
    unit = H.stage(doc, "entry-verdict")["work_unit"]
    assert "adverse inference" in " ".join(unit["tests_required"]).lower()
    assert doc["failure_policy"]["on_failure"] == "fail-fast"


def test_the_owner_decision_only_fires_for_an_unknown_third_party(doc: dict) -> None:
    cp = H.stage(doc, "owner-entry-decision")
    assert cp["when"] == "trust_level == unknown-third-party"
    assert cp["on_timeout"] == "fail", (
        "an unanswered entry decision must not resolve to proceed"
    )
    assert "refuse-entry" in cp["options"]
    assert doc["params"]["trust_level"]["enum"] == [
        "first-party",
        "known-third-party",
        "unknown-third-party",
    ]


def test_the_disclosed_gap_is_recorded_rather_than_claimed_away(doc: dict) -> None:
    gap = doc["x_extensions"]["disclosed_gap"]
    assert "floor" in gap and "settling experiment" in gap, gap


def test_an_unparseable_when_guard_would_be_caught(doc: dict) -> None:
    def bend(d: dict) -> None:
        for s in d["stages"]:
            if s["id"] == "owner-entry-decision":
                s["when"] = "trust_level == ((("

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-007" in v for v in violations), violations
