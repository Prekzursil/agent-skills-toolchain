"""Whole-set conformance for blueprint range bp-4 (document-order 37-48 of the 96 built-ins).

Every assertion here is mechanical. Where a check reports an ABSENCE ("no unresolved reference",
"no near-duplicate"), a companion control feeds it a known-bad input and requires it to fail -
a check that is silent in both states measures nothing.
"""

from __future__ import annotations

import copy
import json

import bp4_testkit as K
import pytest
from jsonschema import Draft202012Validator

DOCS = K.load_all()

#: Measured max pairwise Jaccard over the twelve = 0.200 (2026-08-10). The threshold sits above
#: that and far below the renamed-clone control at 1.000, so the check has room in both
#: directions and is not tuned to the sample.
DISTINCTNESS_CEILING = 0.35


# ------------------------------------------------------------------ the set exists and validates


def test_all_twelve_documents_exist_on_disk() -> None:
    missing = [wid for wid in K.BP4_IDS if not K.path_for(wid).is_file()]
    assert not missing, f"declared but absent: {missing}"
    assert len(K.BP4_IDS) == 12


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_document_is_schema_valid(workflow_id: str) -> None:
    assert K.schema_errors(DOCS[workflow_id]) == []


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_document_has_zero_semantic_violations(workflow_id: str) -> None:
    assert K.semantic_violations(DOCS[workflow_id]) == []


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_document_has_zero_semantic_advisories(workflow_id: str) -> None:
    """Advisories do not gate the CLI, but a council rule the sibling parser rejects is a defect."""
    assert K.semantic_advisories(DOCS[workflow_id]) == []


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_schema_validator_is_armed_on_this_document(workflow_id: str) -> None:
    """Both-states control, same document: an unknown top-level key must be REJECTED.

    This is the control for `test_document_is_schema_valid`. Without it, a validator that
    accepted everything would produce the same green result.
    """
    broken = K.mutant(DOCS[workflow_id], lambda d: d.update({"totally_unknown_key": 1}))
    assert K.schema_errors(broken) != []


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_semantic_checker_is_armed_on_this_document(workflow_id: str) -> None:
    """Both-states control: a dangling depends_on must be caught by DSL-SEM-002."""

    def break_it(doc: dict) -> None:
        doc["stages"][0] = dict(doc["stages"][0])
        doc["stages"][0]["depends_on"] = ["no-such-stage"]

    assert K.semantic_violations(K.mutant(DOCS[workflow_id], break_it)) != []


# --------------------------------------------------------------------------- references resolve


def test_every_work_unit_ref_resolves_to_a_catalogued_unit() -> None:
    known = K.catalog_ids()
    unresolved = [
        (wid, ref)
        for wid, doc in DOCS.items()
        for ref in K.work_unit_refs(doc)
        if ref not in known
    ]
    assert not unresolved, f"phantom work-unit references: {unresolved}"


def test_work_unit_ref_detector_catches_a_phantom() -> None:
    """Control for the check above: a deliberately bogus ref must be reported."""
    known = K.catalog_ids()
    broken = K.mutant(
        DOCS["per-unit-four-phase-pipeline"],
        lambda d: K.find_stage_mut(d, "validate").update({"work_unit_ref": "ZZZ-9999"}),
    )
    assert [ref for ref in K.work_unit_refs(broken) if ref not in known] == ["ZZZ-9999"]


def test_the_set_actually_uses_work_unit_refs() -> None:
    """A resolver check over an empty reference list would pass vacuously."""
    total = sum(len(K.work_unit_refs(doc)) for doc in DOCS.values())
    assert total >= 24, f"only {total} work-unit references across twelve blueprints"


def test_every_schema_reference_resolves_and_compiles() -> None:
    unresolved: list[tuple[str, str]] = []
    checked: set[str] = set()
    for wid, doc in DOCS.items():
        for ref in K.schema_references(doc):
            path = K.resolve_schema_reference(ref)
            if path is None:
                unresolved.append((wid, ref))
                continue
            if str(path) in checked:
                continue
            checked.add(str(path))
            Draft202012Validator.check_schema(
                json.loads(path.read_text(encoding="utf-8"))
            )
    assert not unresolved, f"unloadable schema references: {unresolved}"
    assert len(checked) >= 20, (
        f"only {len(checked)} distinct schema documents referenced"
    )


def test_schema_reference_detector_catches_a_missing_file() -> None:
    """Control: a reference to a file that does not exist must not resolve."""
    assert (
        K.resolve_schema_reference("command-center/schema/no-such-artifact.schema.json")
        is None
    )
    assert K.resolve_schema_reference("platform/schema/receipt.schema.json") is not None


# ------------------------------------------------------------------- required capability surface


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_declares_the_full_required_surface(workflow_id: str) -> None:
    doc = DOCS[workflow_id]
    for block in (
        "params",
        "roles",
        "tool_policy",
        "gates",
        "stages",
        "stopping_rules",
        "retry_policy",
        "failure_policy",
        "estimate",
        "portability",
        "lineage",
        "outputs",
        "x_extensions",
    ):
        assert doc.get(block), f"{workflow_id} is missing a non-empty {block!r}"
    assert doc["params"], "typed parameters are mandated"
    assert doc["gates"], "gates are mandated"
    assert len(doc["stopping_rules"]) >= 2, (
        "an explicit stopping rule set needs alternatives"
    )


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_declares_a_worked_example_and_contraindications(workflow_id: str) -> None:
    ext = DOCS[workflow_id]["x_extensions"]
    example = ext.get("worked_example")
    assert isinstance(example, dict) and len(example) >= 4, (
        f"{workflow_id}: a worked example needs concrete steps, not a sentence"
    )
    contra = ext.get("contraindications")
    assert isinstance(contra, list) and len(contra) >= 2, (
        f"{workflow_id}: at least two contraindications - a blueprint that fits everything fits nothing"
    )
    assert ext.get("distinctive_mechanism"), (
        f"{workflow_id}: no mechanism claim to test against"
    )


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_tool_policy_denies_by_default(workflow_id: str) -> None:
    policy = DOCS[workflow_id]["tool_policy"]
    assert policy.get("default") == "deny"
    assert policy.get("allow"), (
        "a deny-by-default policy with no allowlist can run nothing"
    )


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_failure_policy_is_terminal_and_never_silent(workflow_id: str) -> None:
    failure = DOCS[workflow_id]["failure_policy"]
    assert failure.get("terminal_state_required") is True
    assert failure.get("never_silent") is True
    assert failure.get("classify_as"), "an unclassified failure cannot be routed"


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_inline_work_unit_sentinel_names_its_own_unit(workflow_id: str) -> None:
    """The catalog rule SEM-002 applied to the DSL's inline units."""
    units = K.inline_work_units(DOCS[workflow_id])
    assert units, (
        f"{workflow_id} carries no inline work unit, so its 19-field contract is untested"
    )
    for unit in units:
        assert f"SUCCESS:{unit['id']}" in unit["completion_sentinel"]
        assert len(unit["tests_required"]) >= 2
        assert len(unit["evidence_requirement"]) >= 20


def test_inline_work_unit_sentinel_check_is_armed() -> None:
    """Control: a sentinel naming a DIFFERENT unit must be rejected."""

    def break_it(doc: dict) -> None:
        unit = K.find_stage_mut(doc, "measure-surface")["work_unit"]
        unit["completion_sentinel"] = (
            "SUCCESS:XXX-0000 emitted when the artifact exists"
        )

    broken = K.mutant(DOCS["stale-mega-pr-reconcile"], break_it)
    unit = K.inline_work_units(broken)[0]
    assert f"SUCCESS:{unit['id']}" not in unit["completion_sentinel"]


@pytest.mark.parametrize("workflow_id", K.BP4_IDS)
def test_inline_work_unit_validates_against_the_work_unit_contract(
    workflow_id: str,
) -> None:
    """The DSL must not invent a second unit shape: the inline unit is the catalog's own."""
    validator = K.__dict__["_schemas"].work_unit_validator("structural")
    for unit in K.inline_work_units(DOCS[workflow_id]):
        assert list(validator.iter_errors(unit)) == [], unit["id"]


# ------------------------------------------------------------------------------- distinctness


def test_pairwise_mechanism_distinctness() -> None:
    rows = K.pairwise_similarity(DOCS)
    worst, left, right = rows[0]
    assert worst < DISTINCTNESS_CEILING, (
        f"{left} and {right} share {worst:.3f} of their mechanism tokens - merge or split them"
    )


def test_distinctness_detector_fires_on_a_renamed_clone() -> None:
    """The control that makes the previous test meaningful.

    A copy of one blueprint with a new id, name and description - the exact 'renamed copy' the
    spec forbids - must score 1.0, so the check is proven able to fail.
    """
    original = DOCS["silent-disarm-hunt"]
    clone = copy.deepcopy(original)
    clone["id"] = "silent-disarm-hunt-clone"
    clone["name"] = "A differently named sweep of the same shape"
    clone["description"] = (
        "Entirely different prose describing entirely the same mechanism."
    )
    clone["tags"] = ["renamed", "copy"]
    score = K.jaccard(K.mechanism_tokens(original), K.mechanism_tokens(clone))
    assert score == pytest.approx(1.0)
    assert score >= DISTINCTNESS_CEILING


def test_every_blueprint_has_a_unique_id_and_filename() -> None:
    ids = [doc["id"] for doc in DOCS.values()]
    assert len(set(ids)) == len(ids)
    assert sorted(ids) == sorted(K.BP4_IDS)


def test_no_id_collides_with_another_range_in_the_shared_directory() -> None:
    """Eight agents write into one directory; a duplicated id would silently overwrite a peer."""
    seen: dict[str, str] = {}
    for path in sorted(K.WORKFLOW_DIR.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # pragma: no cover - a peer mid-write
            continue
        if not isinstance(doc, dict):  # a peer's report array, not a workflow document
            continue
        wid = doc.get("id")
        if not isinstance(wid, str) or "dsl_version" not in doc:
            continue
        assert wid not in seen, (
            f"id {wid!r} declared by both {seen[wid]} and {path.name}"
        )
        seen[wid] = path.name
    for wid in K.BP4_IDS:
        assert seen.get(wid) == f"{wid}.json"


# ------------------------------------------------------------------------- spec-level coverage


def test_flagship_share_meets_the_pro_rata_floor() -> None:
    """The spec wants >=40 of 96 flagship; 12/96 of 40 is 5, and this range declares 6."""
    declared = [wid for wid in K.BP4_IDS if DOCS[wid].get("flagship") is True]
    assert sorted(declared) == sorted(K.BP4_FLAGSHIP)
    assert len(declared) >= 5, f"only {len(declared)} flagship blueprints in this range"


def test_every_flagship_names_its_own_test_file() -> None:
    for wid in K.BP4_FLAGSHIP:
        named = DOCS[wid]["x_extensions"].get("flagship_test")
        assert named, f"{wid} is flagship but names no end-to-end test"
        assert (K.REPO_ROOT / named).is_file(), (
            f"{wid} names a test file that does not exist: {named}"
        )


def test_non_flagship_blueprints_do_not_claim_a_flagship_test() -> None:
    for wid in K.BP4_IDS:
        if wid in K.BP4_FLAGSHIP:
            continue
        assert DOCS[wid].get("flagship") is not True
        assert "flagship_test" not in DOCS[wid]["x_extensions"]


def test_categories_come_from_the_spec_vocabulary() -> None:
    used: set[str] = set()
    for wid, doc in DOCS.items():
        cats = doc.get("categories") or []
        assert cats, f"{wid} declares no category"
        used |= set(cats)
    assert used <= K.SPEC_CATEGORIES, (
        f"non-spec categories: {sorted(used - K.SPEC_CATEGORIES)}"
    )
    assert len(used) >= 4, (
        "a twelve-blueprint range concentrated in fewer than four domains"
    )


def test_the_set_exercises_every_stage_kind_the_dsl_defines() -> None:
    kinds = {st.get("kind") for doc in DOCS.values() for _, st in K.stages(doc)}
    assert K.ALL_STAGE_KINDS <= kinds, (
        f"unexercised stage kinds: {sorted(K.ALL_STAGE_KINDS - kinds)}"
    )


def test_lineage_records_the_source_card_for_every_blueprint() -> None:
    for position, card, wid, _flagship in K.BP4_RANGE:
        sources = [
            entry["source"]
            for entry in DOCS[wid]["lineage"]["derived_from"]
            if "source" in entry
        ]
        assert any(card in src for src in sources), (
            f"{wid} (doc-order {position}) does not cite its source card {card}"
        )
        assert any(
            entry["relation"] == "REBUILD-FROM-SPEC"
            for entry in DOCS[wid]["lineage"]["derived_from"]
        )


def test_secret_params_are_never_exportable() -> None:
    """DSL-SEM-013 in test form: a workflow with a secret param must redact on export."""
    holders = [
        wid
        for wid, doc in DOCS.items()
        if any(
            spec.get("secret") or spec.get("type") == "secret_ref"
            for spec in (doc.get("params") or {}).values()
        )
    ]
    assert holders, (
        "no blueprint in this range declares a secret reference, so the rule is untested"
    )
    for wid in holders:
        assert DOCS[wid]["portability"]["export"]["redact_secrets"] is True
        for name, spec in DOCS[wid]["params"].items():
            if spec.get("type") == "secret_ref":
                assert "default" not in spec, f"{wid}:{name} carries a literal default"
