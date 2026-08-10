"""End-to-end tests for BP-SEC-05 (card 65), the licence and rights governance register.

Mechanism under test: VERBATIM rider preservation with byte offsets, block-on-absence, and
DEFER-to-owner on ambiguity. The failure this blueprint exists to prevent is flattening
"MIT plus a clause forbidding ML training and eval folding" to the word "MIT".
"""

from __future__ import annotations

import pytest

import _harness as H

NAME = "license-and-rights-governance-register"


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


def test_worked_example_checker_fires_on_an_illegal_enum_item(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["x_extensions"]["worked_example"]["params"]["intended_use"].append("world-domination")

    fails = H.worked_example_failures(H.mutated(doc, bend))
    assert any("outside the item enum" in f for f in fails), fails


# ------------------------------------------------- mechanism: verbatim, with re-checkable offsets


def test_riders_are_extracted_as_byte_spans_not_summaries(doc: dict) -> None:
    unit = H.stage(doc, "extract-obligations")["work_unit"]
    target = unit["question_or_target"]
    assert "VERBATIM span" in target
    assert "start and end offsets" in target
    ev = unit["evidence_requirement"]
    assert "byte offsets" in ev and "sha256" in ev
    assert "re-checkable without the extractor" in ev, (
        "if only the extractor can verify its own output, byte-identity is not asserted"
    )
    assert "rider-summarised-away" in unit["failure_classification"]
    assert "offset-mismatch" in unit["failure_classification"]


def test_the_verbatim_gate_compares_extracted_against_source(doc: dict) -> None:
    expr = H.gate_expressions(doc)["riders-preserved-verbatim"]
    assert "riders_extracted == riders_byte_identical_to_source" in expr
    assert "riders_summarised_away == 0" in expr
    assert doc["gates"]["riders-preserved-verbatim"]["on_fail"] == "fail"


def test_the_mit_plus_rider_case_is_an_explicit_test_requirement(doc: dict) -> None:
    tests = " ".join(H.stage(doc, "extract-obligations")["work_unit"]["tests_required"])
    assert "no-ML-training" in tests
    assert "never flattened to MIT" in tests
    # and the lineage records the real artifact this rule came from, with its licence
    sources = {row["source"]: row for row in doc["lineage"]["derived_from"]}
    rider_row = next(r for s, r in sources.items() if "agent_mail" in s)
    assert "rider" in rider_row["license"].lower()


def test_weakening_the_verbatim_gate_is_detectable(doc: dict) -> None:
    def bend(d: dict) -> None:
        d["gates"]["riders-preserved-verbatim"]["expression"] = "riders_extracted >= 0"

    mutant = H.mutated(doc, bend)
    assert H.conformance_failures(mutant) == []
    assert "byte_identical" not in H.gate_expressions(mutant)["riders-preserved-verbatim"]


# ------------------------------------------------------------ mechanism: block on absence


def test_absence_of_a_licence_blocks_adoption_and_is_a_measured_finding(doc: dict) -> None:
    locate = H.stage(doc, "locate-license")["work_unit"]
    assert "ABSENT" in locate["question_or_target"]
    assert "searched-paths list" in " ".join(locate["tests_required"])
    assert "license-absent" in locate["failure_classification"]
    gate = H.stage(doc, "absent-license-gate")
    assert gate["when"] == "block_on_absent_license == true"
    assert doc["params"]["block_on_absent_license"]["default"] is True
    assert (
        H.gate_expressions(doc)["no-artifact-without-license"]
        == "artifacts_with_absent_license_marked_adoptable == 0"
    )


def test_the_locator_covers_more_than_one_licence_format(doc: dict) -> None:
    """A format check that only knows LICENSE files prints a confident false on an SPDX header."""
    locate = H.stage(doc, "locate-license")["work_unit"]
    target = locate["question_or_target"]
    for fmt in ("LICENSE", "COPYING", "SPDX", "package metadata"):
        assert fmt in target, fmt
    assert "SPDX-header-only artifact must be located" in " ".join(locate["tests_required"])


# ------------------------------------------------------- mechanism: ambiguity defers to owner


def test_ambiguity_defers_and_never_defaults_permissive(doc: dict) -> None:
    cp = H.stage(doc, "owner-resolves-ambiguity")
    assert cp["kind"] == "human_checkpoint"
    assert cp["when"] == "artifacts_ambiguous >= 1"
    assert cp["on_timeout"] == "fail"
    assert "do-not-adopt" in cp["options"]
    assert "will not assume a permissive reading" in cp["prompt"]
    assert doc["failure_policy"]["on_failure"] == "quarantine"


def test_not_legal_advice_is_stated_in_the_document(doc: dict) -> None:
    assert "not interpret enforceability" in doc["x_extensions"]["not_legal_advice"]


# --------------------------------------------------------------- mechanism: pinning is required


def test_every_registered_artifact_must_carry_an_immutable_ref(doc: dict) -> None:
    assert H.gate_expressions(doc)["every-artifact-pinned"] == "artifacts_without_pinned_ref == 0"
    unit = H.stage(doc, "pin-and-register")["work_unit"]
    assert "commit sha" in unit["question_or_target"]
    assert "floating ref" in " ".join(unit["tests_required"])
    assert "unpinned-dependency" in unit["failure_classification"]
    assert unit["owner_approval_required"] is True


def test_removing_the_pin_gate_leaves_a_dangling_reference(doc: dict) -> None:
    def bend(d: dict) -> None:
        del d["gates"]["every-artifact-pinned"]

    violations = H.semantic_violations(H.mutated(doc, bend))
    assert any("DSL-SEM-005" in v and "every-artifact-pinned" in v for v in violations), violations
