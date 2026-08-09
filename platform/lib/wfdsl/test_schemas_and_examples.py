"""Conformance tests for the schema documents, the examples and the mutation battery.

Executable conformance BEFORE broad implementation (spec Phase 4, line 10822).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wfdsl import capabilities, mutations, resolve, schemas, semantics

EXAMPLES = Path(__file__).resolve().parent / "examples"


# --------------------------------------------------------------------- the schemas


def test_every_schema_is_valid_draft_2020_12() -> None:
    result = schemas.check_metaschema()
    assert set(result) == set(schemas.SCHEMA_FILES.values())
    assert all(v == "OK" for v in result.values())


def test_declared_ids_match_filenames() -> None:
    # load_all() raises if any $id drifts from its filename mapping
    docs = schemas.load_all()
    assert len(docs) == len(schemas.SCHEMA_FILES)


def test_registry_is_offline_and_refuses_external_fetch() -> None:
    from referencing.exceptions import NoSuchResource

    reg = schemas.registry()
    with pytest.raises(NoSuchResource):
        reg.get_or_retrieve("https://example.invalid/not-a-local-schema.json")


def test_no_schema_ref_points_outside_the_local_document_set() -> None:
    """Second, mechanically different signal for the 'no network' claim.

    The offline-registry test proves a fetch would RAISE; this proves no ``$ref`` would ever
    need one, by enumerating every absolute-URI ``$ref`` in every document.
    """
    known = set(schemas.SCHEMA_FILES.values())
    offenders: list[tuple[str, str]] = []

    def walk(node: object, doc_id: str) -> None:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith(("http://", "https://")):
                base = ref.split("#", 1)[0]
                if base and base not in known:
                    offenders.append((doc_id, ref))
            for value in node.values():
                walk(value, doc_id)
        elif isinstance(node, list):
            for value in node:
                walk(value, doc_id)

    for doc_id, doc in schemas.load_all().items():
        walk(doc, doc_id)
    assert not offenders, offenders


def test_work_unit_schema_requires_all_nineteen_spec_fields() -> None:
    doc = schemas.load_all()[schemas.WORK_UNIT_PROFILES["structural"]]
    assert set(doc["required"]) == set(resolve.MANDATED_FIELDS)
    assert len(doc["required"]) == 19


@pytest.mark.parametrize("field", list(resolve.MANDATED_FIELDS))
def test_removing_any_single_mandated_field_fails_validation(field: str) -> None:
    """19 mutations: the schema must notice EACH missing field, not just the first."""
    unit = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )["work_units"][0]
    assert not list(schemas.work_unit_validator("strict").iter_errors(unit)), (
        "fixture must start valid"
    )
    broken = {k: v for k, v in unit.items() if k != field}
    errors = list(schemas.work_unit_validator("structural").iter_errors(broken))
    assert errors, f"removing {field} was not detected"
    assert any(field in e.message for e in errors), (
        f"error does not name {field}: {[e.message for e in errors][:2]}"
    )


def test_reference_unit_passes_all_three_profiles() -> None:
    """The strict profile must be SATISFIABLE - an unsatisfiable contract is not a contract."""
    unit = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )["work_units"][0]
    for profile in ("structural", "normative", "strict"):
        errs = schemas.error_summary(
            schemas.work_unit_validator(profile).iter_errors(unit)
        )
        assert not errs, f"{profile}: {errs}"


def test_profiles_are_strictly_ordered() -> None:
    """A document rejected by a looser profile must also be rejected by a stricter one."""
    unit = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )["work_units"][0]
    cases = [
        ("normative", {**unit, "id": "bad_id"}),
        (
            "normative",
            {**unit, "output_schema": "receipt.schema.json profile=x (required: y)"},
        ),
        ("normative", {**unit, "dependencies": ["ARC"]}),
        (
            "strict",
            {**unit, "assigned_model_vendor_role": "opus/anthropic/implementer"},
        ),
        ("strict", {**unit, "tests_required": "just a prose sentence about tests"}),
        (
            "strict",
            {**unit, "failure_classification": "P1-blocking / classes: whatever"},
        ),
        ("strict", {**unit, "typo_field": 1}),
    ]
    for first_rejecting, doc in cases:
        rejected_by = [
            p
            for p in ("structural", "normative", "strict")
            if list(schemas.work_unit_validator(p).iter_errors(doc))
        ]
        assert first_rejecting in rejected_by, (
            f"{first_rejecting} accepted {doc.get('id')} / keys={sorted(set(doc) - set(unit))}"
        )
        order = ["structural", "normative", "strict"]
        idx = order.index(first_rejecting)
        assert all(p in rejected_by for p in order[idx:]), (
            f"stricter profile accepted what {first_rejecting} rejected: {rejected_by}"
        )


def test_strict_profile_rejects_an_unknown_property_while_structural_allows_it() -> (
    None
):
    """Regression guard for a draft-2020-12 annotation trap that was measured LIVE here.

    ``additionalProperties: true`` in the structural profile annotates unknown properties as
    evaluated, which silently neutralises ``unevaluatedProperties: false`` in the strict
    profile. Before the fix, a unit carrying ``typo_field`` passed strict. Omitting the keyword
    is validation-equivalent but annotation-different, so this test is the both-states control.
    """
    unit = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )["work_units"][0]
    typo = {**unit, "dependencie": ["CC-0002"]}
    assert not list(schemas.work_unit_validator("structural").iter_errors(typo)), (
        "structural must stay permissive"
    )
    assert not list(schemas.work_unit_validator("normative").iter_errors(typo)), (
        "normative must stay permissive"
    )
    strict_errors = list(schemas.work_unit_validator("strict").iter_errors(typo))
    assert strict_errors, "strict profile did not reject an unknown property"
    assert any(e.validator == "unevaluatedProperties" for e in strict_errors), [
        e.validator for e in strict_errors
    ]


def test_structural_profile_must_not_declare_additional_properties() -> None:
    """The exact regression vector for the test above, asserted on the schema text itself."""
    doc = schemas.load_all()[schemas.WORK_UNIT_PROFILES["structural"]]
    assert "additionalProperties" not in doc, (
        "declaring additionalProperties here (even `true`) annotates unknown properties as "
        "evaluated and disables the strict profile's unevaluatedProperties check"
    )


def test_tool_token_pattern_rejects_comma_packed_and_accepts_hyphenated_mcp() -> None:
    """Detector control: the pattern must FIRE on the bad token and be SILENT on real ones."""
    unit = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )["work_units"][0]
    v = schemas.work_unit_validator("normative")
    bad = {**unit, "tool_permissions": ["mcp__a__b,mcp__c__d"]}
    assert list(v.iter_errors(bad)), "comma-packed tool token was accepted"
    for good in (
        "mcp__codex__codex-reply",
        "mcp__search-hub__* (read-only retrieval)",
        "Bash:python",
        "Write(command-center/research/**)",
        "Read",
    ):
        assert not list(v.iter_errors({**unit, "tool_permissions": [good]})), (
            f"rejected a real token: {good}"
        )


# ------------------------------------------------------------- defaults semantics


def test_defaults_block_is_optional_not_load_bearing() -> None:
    doc = json.loads(
        (EXAMPLES / "catalog-no-defaults.json").read_text(encoding="utf-8")
    )
    assert "defaults" not in doc
    assert not list(schemas.catalog_validator().iter_errors(doc))
    audit = resolve.defaults_are_load_bearing(doc)
    assert audit["load_bearing"] is False


def test_real_catalog_defaults_block_is_not_load_bearing() -> None:
    catalog_path = schemas.REPO_ROOT / "command-center" / "WORK-UNIT-CATALOG.json"
    if not catalog_path.is_file():  # pragma: no cover - environment guard
        pytest.skip(f"catalog not present at {catalog_path}")
    catalog = schemas.load_json(catalog_path)
    audit = resolve.defaults_are_load_bearing(catalog)
    assert audit["defaults_present"] is True
    assert audit["load_bearing"] is False, audit["fields_units_depend_on"]


def test_defaults_leaning_unit_is_rejected_raw_and_completed_when_resolved() -> None:
    doc = json.loads(
        (EXAMPLES / "catalog-defaults-only.json").read_text(encoding="utf-8")
    )
    lean = doc["work_units"][0]
    v = schemas.work_unit_validator("structural")
    assert list(v.iter_errors(lean)), (
        "raw contract accepted a unit that leans on defaults"
    )
    res = resolve.resolve_unit(lean, doc["defaults"])
    assert res.used_defaults
    assert not list(v.iter_errors(res.unit)), schemas.error_summary(
        v.iter_errors(res.unit)
    )


def test_resolver_refuses_to_default_identity_and_intent_fields() -> None:
    doc = json.loads(
        (EXAMPLES / "catalog-defaults-only.json").read_text(encoding="utf-8")
    )
    res = resolve.resolve_unit(doc["work_units"][1], doc["defaults"])
    assert res.refused == ["output_path"]
    assert "output_path" not in res.unit
    assert list(schemas.work_unit_validator("structural").iter_errors(res.unit))


# ------------------------------------------------------------------- the DSL examples


@pytest.mark.parametrize(
    "name", ["wf-minimal.json", "wf-full-coverage.json", "wf-spec-stopping-rules.json"]
)
def test_example_workflow_is_schema_valid(name: str) -> None:
    doc = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    errs = schemas.error_summary(schemas.workflow_validator().iter_errors(doc), limit=8)
    assert not errs, errs


@pytest.mark.parametrize(
    "name", ["wf-minimal.json", "wf-full-coverage.json", "wf-spec-stopping-rules.json"]
)
def test_example_workflow_has_no_semantic_violations(name: str) -> None:
    doc = json.loads((EXAMPLES / name).read_text(encoding="utf-8"))
    results = semantics.check_workflow(doc)
    hard = [r.to_json() for r in results if r.severity == "violation" and r.violations]
    assert not hard, hard


def test_inline_work_unit_in_the_dsl_uses_the_same_contract_as_the_catalog() -> None:
    doc = json.loads((EXAMPLES / "wf-full-coverage.json").read_text(encoding="utf-8"))
    unit = doc["stages"][0]["work_unit"]
    for profile in ("structural", "normative", "strict"):
        errs = schemas.error_summary(
            schemas.work_unit_validator(profile).iter_errors(unit)
        )
        assert not errs, f"{profile}: {errs}"


# ----------------------------------------------------------------- capability map


def test_every_mandated_capability_is_covered() -> None:
    report = capabilities.check_coverage()
    assert report["mandated"] >= 20, report["mandated"]
    assert report["mandated"] == report["mandated_covered"], report["uncovered"]


def test_capability_map_covers_every_spec_phrase() -> None:
    """The 20 capabilities the task/spec enumerate must all be present by id."""
    required = {
        "stages",
        "roles",
        "gates",
        "tools",
        "typed_params",
        "subworkflows",
        "dynamic_fanout",
        "barriers",
        "loops_with_convergence",
        "human_checkpoints",
        "retries",
        "repair_loops",
        "resume",
        "deterministic_replay",
        "artifact_caching",
        "dry_run",
        "cost_estimate",
        "model_routing",
        "failure_policy",
        "export_import",
    }
    have = {c["id"] for c in capabilities.load_capability_map()["capabilities"]}
    assert required <= have, sorted(required - have)


def test_pointer_resolver_control() -> None:
    """Verify the detector: the pointer resolver must FAIL on a known-absent pointer."""
    doc = {"a": {"b": [1, 2]}}
    assert capabilities.resolve_pointer(doc, "/a/b/1") == 2
    with pytest.raises(capabilities.PointerError):
        capabilities.resolve_pointer(doc, "/a/zzz")
    with pytest.raises(capabilities.PointerError):
        capabilities.resolve_pointer(doc, "/a/b/9")


# --------------------------------------------------------------- mutation battery


def _battery():
    base = json.loads((EXAMPLES / "wf-full-coverage.json").read_text(encoding="utf-8"))
    return mutations.run_battery(base)


def test_mutation_battery_base_document_is_clean() -> None:
    report = _battery()
    assert report["base_document_valid"], report["base_schema_errors"]
    assert not report["base_semantic_violations"], report["base_semantic_violations"]


def test_no_mutation_survives() -> None:
    report = _battery()
    assert not report["survivors"], report["survivors"]


def test_every_mutation_is_caught_by_its_declared_layer() -> None:
    report = _battery()
    wrong = [r for r in report["results"] if not r["caught_by_declared_layer"]]
    assert not wrong, [
        (r["id"], r["declared_layer"], r["schema_errors"], r["new_semantic_violations"])
        for r in wrong
    ]


def test_mutation_battery_covers_every_mandated_capability() -> None:
    covered = {m.capability for m in mutations.MUTATIONS}
    mandated = {
        c["id"]
        for c in capabilities.load_capability_map()["capabilities"]
        if c.get("mandated")
    }
    assert mandated <= covered, sorted(mandated - covered)


def test_semantic_rules_have_unique_ids_and_fire_on_a_broken_document() -> None:
    doc = json.loads((EXAMPLES / "wf-full-coverage.json").read_text(encoding="utf-8"))
    results = semantics.check_workflow(doc)
    ids = [r.rule for r in results]
    assert len(ids) == len(set(ids)), ids
    # duplicate stage id: DSL-SEM-001 must fire
    broken = json.loads(json.dumps(doc))
    broken["stages"][1]["id"] = broken["stages"][0]["id"]
    fired = {r.rule for r in semantics.check_workflow(broken) if r.violations}
    assert "DSL-SEM-001" in fired, fired


def test_stage_graph_cycle_is_detected() -> None:
    doc = json.loads((EXAMPLES / "wf-full-coverage.json").read_text(encoding="utf-8"))
    broken = json.loads(json.dumps(doc))
    broken["stages"][0]["depends_on"] = ["owner-review"]
    fired = {
        r.rule: len(r.violations)
        for r in semantics.check_workflow(broken)
        if r.violations
    }
    assert fired.get("DSL-SEM-003", 0) > 0, fired
