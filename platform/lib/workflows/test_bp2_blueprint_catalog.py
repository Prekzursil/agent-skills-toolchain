"""Conformance suite for blueprints 13-24 (bp-2): all twelve, every layer.

Scope note: this module asserts over ``bp2_common.BP2_IDS`` (an explicit list of twelve), NOT
over a glob of ``platform/workflows``. Sibling units are writing that directory concurrently;
a glob would go red on another agent's in-flight file and report a defect that is not ours.

Every assertion here is answerable by an exact algorithm - schema validation, set membership,
counting, fingerprint comparison - so none of it is delegated to judgement.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bp2_common as C  # noqa: E402

ALL_IDS = sorted(C.BP2_IDS)

#: the spec floor: at least 40 of 96 blueprints are flagship with full end-to-end tests
SPEC_FLAGSHIP_NUMERATOR = 40
SPEC_FLAGSHIP_DENOMINATOR = 96


# ------------------------------------------------------------------ existence and identity


def test_all_twelve_files_exist() -> None:
    missing = [bid for bid in ALL_IDS if not C.path_for(bid).is_file()]
    assert not missing, f"declared but absent on disk: {missing}"


def test_exactly_twelve_blueprints_declared() -> None:
    assert len(C.BP2_IDS) == 12, (
        "the unit range is blueprints 13-24 inclusive = 12 documents; a different count means "
        "the range was mis-resolved or a design collapsed without being reported"
    )


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_document_id_matches_its_filename_key(bp_id: str) -> None:
    assert C.load(bp_id)["id"] == bp_id


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_declares_dsl_version_and_semver(bp_id: str) -> None:
    doc = C.load(bp_id)
    assert doc["dsl_version"].startswith("1."), doc["dsl_version"]
    assert doc["version"] == "1.0.0", doc["version"]


# --------------------------------------------------------------------- the four layers


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_validates_against_the_workflow_dsl_schema(bp_id: str) -> None:
    errs = C.schema_errors(C.load(bp_id))
    assert not errs, f"{bp_id} schema errors: {errs}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_zero_semantic_violations(bp_id: str) -> None:
    violations, _ = C.semantic(C.load(bp_id))
    assert not violations, f"{bp_id} semantic violations: {violations}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_zero_semantic_advisories(bp_id: str) -> None:
    """DSL-SEM-014 cross-checks council stopping text against the councilspec grammar.

    Kept at ZERO rather than merely low: the two grammars are not co-extensive (``custom:x``
    parses under councilspec but is a DSL-SEM-007 VIOLATION in wfdsl, and an enum comparison
    needs a registry-legal token), so a clean advisory count is the evidence that every council
    stopping rule sits in the intersection both implementations accept.
    """
    _, advisories = C.semantic(C.load(bp_id))
    assert not advisories, f"{bp_id} advisories: {advisories}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_every_schema_ref_resolves_and_compiles(bp_id: str) -> None:
    """A declared-but-dangling output_schema is the exact P1 the substrate unit closed."""
    bad = C.schema_ref_failures(C.load(bp_id))
    assert not bad, f"{bp_id} unresolvable schema refs: {bad}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_declares_at_least_one_schema_ref(bp_id: str) -> None:
    refs = set(C.iter_schema_refs(C.load(bp_id)))
    assert refs, f"{bp_id} declares no schema_ref at all, so nothing it emits is checkable"


# ------------------------------------------------------------------- required DSL blocks


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_carries_params_roles_stages_gates_tools_stopping_failure(bp_id: str) -> None:
    doc = C.load(bp_id)
    assert doc.get("params"), "typed parameters are required"
    assert doc.get("roles"), "roles are required"
    assert doc.get("stages"), "stages are required"
    assert doc.get("gates"), "gates are required"
    assert doc.get("tool_policy"), "a tool policy is required"
    assert doc.get("stopping_rules"), "explicit stopping rules are required"
    assert doc.get("failure_policy"), "a failure policy is required"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_tool_policy_is_deny_by_default(bp_id: str) -> None:
    policy = C.load(bp_id)["tool_policy"]
    assert policy.get("default", "deny") == "deny", (
        "an allowlist policy that defaults to allow is how a redactor leaks; deny-by-default "
        "is the estate rule and the schema's own default"
    )


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_failure_policy_requires_a_terminal_state(bp_id: str) -> None:
    fp = C.load(bp_id)["failure_policy"]
    assert fp.get("terminal_state_required") is True
    assert fp.get("never_silent") is True


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_every_stage_has_a_bounded_timeout_or_inherits_one(bp_id: str) -> None:
    """An unbounded stage is how a cohort deadlocks on one hung agent."""
    doc = C.load(bp_id)
    from wfdsl import semantics as S

    unbounded = []
    for path, st in S.iter_stages(doc):
        if st.get("kind") == "gate":
            continue  # a gate is an evaluation, not a dispatch
        if "timeout_seconds" not in st:
            unbounded.append(f"{path}:{st.get('id')}")
    assert not unbounded, f"{bp_id} stages with no timeout: {unbounded}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_every_fanout_bounds_its_concurrency_and_item_count(bp_id: str) -> None:
    doc = C.load(bp_id)
    from wfdsl import semantics as S

    for path, st in S.iter_stages(doc):
        if st.get("kind") != "fanout":
            continue
        assert isinstance(st.get("max_concurrency"), int), f"{path} unbounded concurrency"
        assert isinstance(st.get("max_items"), int), f"{path} unbounded item count"
        assert st.get("barrier"), f"{path} has no barrier, so stragglers are dropped silently"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_every_loop_is_bounded(bp_id: str) -> None:
    doc = C.load(bp_id)
    from wfdsl import semantics as S

    for path, st in S.iter_stages(doc):
        if st.get("kind") != "loop":
            continue
        conv = st.get("convergence") or {}
        assert isinstance(conv.get("max_iterations"), int), f"{path} unbounded loop"
        assert conv.get("no_progress_rounds"), f"{path} has no anti-grind exit"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_dry_run_is_supported_and_side_effect_free(bp_id: str) -> None:
    dr = C.load(bp_id).get("dry_run") or {}
    assert dr.get("supported") is True, "every workflow must be dry-runnable"
    if dr.get("side_effect_free", True):
        assert dr.get("forbid_tools"), "a side-effect-free dry run must name the forbidden tools"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_export_never_carries_a_secret_value(bp_id: str) -> None:
    export = ((C.load(bp_id).get("portability") or {}).get("export")) or {}
    assert export.get("redact_secrets") is True


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_lineage_is_declared_and_decomposable(bp_id: str) -> None:
    lineage = C.load(bp_id).get("lineage") or {}
    assert lineage.get("derived_from"), "a blueprint with no lineage cannot be credited or rolled back"
    assert lineage.get("decomposable_back_to_sources") is True


# --------------------------------------------------------------------- worked examples


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_worked_examples_validate_against_the_blueprints_own_params(bp_id: str) -> None:
    problems = C.worked_example_errors(C.load(bp_id))
    assert not problems, f"{bp_id} worked-example problems: {problems}"


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_has_a_positive_and_a_negative_control_worked_example(bp_id: str) -> None:
    """A worked example that only shows the happy path documents nothing falsifiable.

    Asserted on the EXPLICIT ``arm`` field, not on a substring of the terminal state. An
    earlier version of this test sniffed the terminal string for "FAIL" and went red on three
    blueprints whose negative control legitimately ends in SUCCESS - a design council degrading
    to four personas, a rubric capping instead of averaging, and a grill declining to grill.
    The detector was the defect there, not the blueprints; a question with an exact answer
    should not be answered by a heuristic.
    """
    examples = C.worked_examples(C.load(bp_id))
    assert len(examples) >= 2, f"{bp_id} has {len(examples)} worked example(s), expected >= 2"
    arms = [str(e.get("arm", "")) for e in examples]
    assert "positive" in arms, f"{bp_id} declares no positive arm: {arms}"
    assert "negative-control" in arms, f"{bp_id} declares no negative-control arm: {arms}"
    assert all(a in {"positive", "negative-control"} for a in arms), arms
    terminals = [str(e.get("expected_terminal_state", "")) for e in examples]
    assert all(terminals), f"{bp_id} has a worked example with no terminal state"


# ------------------------------------------------------- categories, flagship, distinctness


@pytest.mark.parametrize("bp_id", ALL_IDS)
def test_categories_come_from_the_spec_vocabulary(bp_id: str) -> None:
    cats = set(C.load(bp_id).get("categories") or [])
    assert cats, f"{bp_id} declares no category"
    unknown = cats - C.SPEC_CATEGORIES
    assert not unknown, f"{bp_id} declares non-spec categories {unknown}"


def test_category_span_is_reported_honestly() -> None:
    """This RANGE covers five of the six spec categories; engineering-and-reliability is not
    one of them, because cards 13-24 are the brainstorm, council and requirements families.
    The test pins the measured span so a later edit cannot quietly claim six.
    """
    covered: set[str] = set()
    for bp_id in ALL_IDS:
        covered |= set(C.load(bp_id).get("categories") or [])
    assert covered <= C.SPEC_CATEGORIES
    assert covered == {
        "research-and-evidence",
        "security-governance-and-risk",
        "product-design-and-strategy",
        "data-science-knowledge-and-creative-work",
        "collective-intelligence-and-meta-workflows",
    }, sorted(covered)
    assert "engineering-and-reliability" not in covered


def test_flagship_flag_matches_the_declared_flagship_set() -> None:
    for bp_id in ALL_IDS:
        expected = bp_id in C.FLAGSHIP_IDS
        assert C.load(bp_id).get("flagship", False) is expected, bp_id


def test_flagship_share_meets_the_spec_floor() -> None:
    n = len(ALL_IDS)
    floor = math.ceil(n * SPEC_FLAGSHIP_NUMERATOR / SPEC_FLAGSHIP_DENOMINATOR)
    assert len(C.FLAGSHIP_IDS) >= floor, (
        f"{len(C.FLAGSHIP_IDS)} flagship of {n}; the spec floor of "
        f"{SPEC_FLAGSHIP_NUMERATOR}/{SPEC_FLAGSHIP_DENOMINATOR} pro-rates to {floor}"
    )


def test_every_flagship_has_its_own_end_to_end_test_module() -> None:
    here = Path(__file__).resolve().parent
    missing = []
    for bp_id in sorted(C.FLAGSHIP_IDS):
        module = here / f"test_{bp_id.replace('-', '_')}.py"
        if not module.is_file():
            missing.append(module.name)
    assert not missing, f"flagship blueprints with no test module: {missing}"


def test_all_twelve_are_structurally_distinct() -> None:
    """MECHANICAL distinctness. A catalog of near-duplicates manufactures false coverage, and
    an exact algorithm answers this better than judgement does: two documents sharing a
    fingerprint are structurally interchangeable = a renamed copy.
    """
    seen: dict[str, str] = {}
    collisions: list[tuple[str, str]] = []
    for bp_id in ALL_IDS:
        key = C.fingerprint_key(C.load(bp_id))
        if key in seen:
            collisions.append((seen[key], bp_id))
        seen[key] = bp_id
    assert not collisions, f"structurally identical blueprints: {collisions}"
    assert len(seen) == len(ALL_IDS)


def test_each_blueprint_states_why_it_is_not_a_duplicate() -> None:
    for bp_id in ALL_IDS:
        x = C.load(bp_id).get("x_extensions") or {}
        assert str(x.get("distinct_mechanism", "")).strip(), f"{bp_id}: no distinct_mechanism"
        assert (
            len(str(x.get("not_a_duplicate_because", "")).strip()) >= 60
        ), f"{bp_id}: not_a_duplicate_because is missing or too thin to be checkable"


def test_blueprint_indices_are_exactly_thirteen_through_twenty_four() -> None:
    indices = sorted(
        int((C.load(bp_id).get("x_extensions") or {})["blueprint_index"]) for bp_id in ALL_IDS
    )
    assert indices == list(range(13, 25)), indices


def test_each_blueprint_anchors_its_design_card() -> None:
    for bp_id in ALL_IDS:
        x = C.load(bp_id).get("x_extensions") or {}
        card = str(x.get("design_card", ""))
        anchor = str(x.get("design_card_anchor", ""))
        assert card.startswith("BP-"), f"{bp_id}: design_card={card!r}"
        assert "09-WORKFLOW-BLUEPRINT-LIBRARY.md:" in anchor, f"{bp_id}: anchor={anchor!r}"


def test_each_blueprint_records_its_unverified_residual() -> None:
    """Every design card carries an UNVERIFIED claim; dropping it on the way into the DSL
    would be an overclaim even though the code is fine."""
    for bp_id in ALL_IDS:
        x = C.load(bp_id).get("x_extensions") or {}
        assert "UNVERIFIED" in str(x.get("unverified", "")), f"{bp_id}: no UNVERIFIED residual"


def test_each_blueprint_states_its_contraindications() -> None:
    for bp_id in ALL_IDS:
        x = C.load(bp_id).get("x_extensions") or {}
        assert len(x.get("contraindications") or []) >= 2, bp_id


# ----------------------------------------------------------- catalog-level mutation control


def test_the_distinctness_detector_fires_on_a_planted_duplicate() -> None:
    """BOTH-STATES control for the distinctness check itself.

    The passing run above proves nothing on its own: a fingerprint function that returned a
    constant per-document nonce would also report twelve distinct values. Here one blueprint's
    structure is overwritten with another's, and the detector MUST collide.
    """
    a = C.load("bp-cnc-01-five-persona-design-council")
    b = C.load("bp-cnc-03-semantic-entropy-escalation")
    assert C.fingerprint_key(a) != C.fingerprint_key(b), "good-state arm: these differ"

    clone = C.load("bp-cnc-03-semantic-entropy-escalation")
    for block in (
        "stages",
        "gates",
        "replay",
        "resume",
        "retry_policy",
        "failure_policy",
        "model_routing",
        "cache",
        "stopping_rules",
        "tool_policy",
        "subworkflows",
    ):
        if block in a:
            clone[block] = a[block]
        else:
            clone.pop(block, None)
    assert C.fingerprint_key(clone) == C.fingerprint_key(a), (
        "BROKEN-STATE ARM FAILED: a structural clone did not collide, so the fingerprint is "
        "keyed on something other than structure and the distinctness proof is worthless"
    )


def test_the_schema_ref_detector_fires_on_a_dangling_ref() -> None:
    """BOTH-STATES control for the schema-ref resolver check."""
    C.assert_mutation_caught(
        "bp-brn-02-diverge-then-converge",
        lambda d: d["outputs"]["shortlist"].__setitem__(
            "schema_ref", "command-center/schema/this-class-does-not-exist.schema.json"
        ),
        "schema_refs",
        what="point an output at a schema class that is not in the registry",
    )


def test_the_worked_example_detector_fires_on_a_bad_param() -> None:
    """BOTH-STATES control for the worked-example param compiler."""
    C.assert_mutation_caught(
        "bp-cnc-03-semantic-entropy-escalation",
        lambda d: d["x_extensions"]["worked_examples"][0]["params"].__setitem__(
            "entropy_threshold", 4.2
        ),
        "worked_examples",
        what="set a worked example's entropy_threshold above the declared maximum of 1.0",
    )


def test_the_semantic_detector_fires_on_an_undeclared_role() -> None:
    """BOTH-STATES control for the DSL semantic layer."""
    C.assert_mutation_caught(
        "bp-req-01-program-scale-extensive-grill",
        lambda d: d["stages"][0].__setitem__("role", "role-that-was-never-declared"),
        "semantic",
        what="reference a role that is not in the roles block (DSL-SEM-004)",
    )
