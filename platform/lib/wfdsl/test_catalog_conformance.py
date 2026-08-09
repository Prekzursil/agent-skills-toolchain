"""Conformance of the REAL 2,007-unit catalog against the work-unit contract.

These tests assert only what must hold TODAY. The normative and strict profiles are
deliberately stricter than the current corpus, so their failure counts are recorded as
MEASUREMENTS (with an upper bound that must not regress) rather than asserted to be zero -
an assertion of zero there would be a false claim about the corpus, and silently loosening
the schema to make it pass would be worse.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wfdsl import resolve, schemas, semantics, validate

CATALOG = schemas.REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"

# Measured 2026-08-09 against WORK-UNIT-CATALOG.json (2,007 units). These are ceilings:
# the count may fall as the substrate is repaired, and must never rise.
CEILINGS = {
    "normative_fail": 217,
    "strict_fail": 328,
    "SEM-001": 40,  # unresolvable dependency tokens (41 refs across 40 units)
    "SEM-002": 96,  # sentinel does not name its own unit id
}


@pytest.fixture(scope="module")
def catalog() -> dict:
    if not CATALOG.is_file():  # pragma: no cover - environment guard
        pytest.skip(f"catalog not present at {CATALOG}")
    return json.loads(Path(CATALOG).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report(catalog: dict) -> dict:  # noqa: ARG001 - fixture ordering only
    return validate.validate_catalog(CATALOG)


def test_catalog_container_validates(report: dict) -> None:
    assert report["container_valid"], report["container_schema_errors"]


def test_catalog_has_the_expected_unit_count(report: dict) -> None:
    assert report["work_units"] == 2007, report["work_units"]


def test_no_unit_is_missing_any_of_the_nineteen_fields(report: dict) -> None:
    assert report["missing_mandated_fields"] == {}, report["missing_mandated_fields"]


def test_all_units_pass_the_structural_profile(report: dict) -> None:
    prof = report["profiles"]["structural"]
    assert prof["fail"] == 0, prof["reason_histogram"]
    assert prof["pass"] == report["work_units"]


def test_normative_failures_do_not_regress(report: dict) -> None:
    prof = report["profiles"]["normative"]
    assert prof["fail"] <= CEILINGS["normative_fail"], (
        prof["fail"],
        prof["reason_histogram"],
    )


def test_strict_failures_do_not_regress(report: dict) -> None:
    prof = report["profiles"]["strict"]
    assert prof["fail"] <= CEILINGS["strict_fail"], (
        prof["fail"],
        prof["reason_histogram"],
    )


def test_semantic_rules_do_not_regress(report: dict) -> None:
    by_rule = {r["rule"]: r["violations"] for r in report["semantic_rules"]}
    assert by_rule["SEM-003"] == 0, "duplicate unit ids"
    assert by_rule["SEM-004"] == 0, "two units claim one output_path"
    assert by_rule["SEM-005"] == 0, "self-dependency"
    assert by_rule["SEM-006"] == 0, "dependency cycle"
    assert by_rule["SEM-001"] <= CEILINGS["SEM-001"], by_rule["SEM-001"]
    assert by_rule["SEM-002"] <= CEILINGS["SEM-002"], by_rule["SEM-002"]


def test_semantic_detectors_fire_on_injected_defects(catalog: dict) -> None:
    """Both-states control on the CATALOG detectors, using the real corpus as the good state."""
    units = [dict(u) for u in catalog["work_units"][:200]]
    clean = {r.rule: len(r.violations) for r in semantics.check_work_units(units)}

    dup = units + [dict(units[0])]
    assert len(semantics.check_work_units(dup)[2].violations) > clean.get("SEM-003", 0)

    same_path = [dict(units[0]), {**units[1], "output_path": units[0]["output_path"]}]
    assert any(
        r.rule == "SEM-004" and r.violations
        for r in semantics.check_work_units(same_path)
    )

    selfdep = [{**units[0], "dependencies": [units[0]["id"]]}]
    fired = {r.rule for r in semantics.check_work_units(selfdep) if r.violations}
    assert "SEM-005" in fired

    a, b = dict(units[0]), dict(units[1])
    a["dependencies"], b["dependencies"] = [b["id"]], [a["id"]]
    fired = {r.rule for r in semantics.check_work_units([a, b]) if r.violations}
    assert "SEM-006" in fired

    dangling = [{**units[0], "dependencies": ["ZZ-9999"]}]
    fired = {r.rule for r in semantics.check_work_units(dangling) if r.violations}
    assert "SEM-001" in fired


def test_every_normative_failure_has_a_named_reason(report: dict) -> None:
    """No silent failures: a failing unit must always come with the keyword that rejected it."""
    prof = report["profiles"]["normative"]
    if prof["fail"]:
        assert prof["reason_histogram"], "units failed with no recorded reason"
        assert sum(prof["reason_histogram"].values()) >= prof["fail"]
        for sample in prof["sample_failures"]:
            assert sample["errors"], sample


def test_defaults_block_present_but_not_load_bearing(report: dict) -> None:
    audit = report["defaults_audit"]
    assert audit["defaults_present"] is True
    assert audit["load_bearing"] is False, audit["fields_units_depend_on"]


def test_mandated_field_list_matches_the_spec_count() -> None:
    assert len(resolve.MANDATED_FIELDS) == 19
    assert len(set(resolve.MANDATED_FIELDS)) == 19
