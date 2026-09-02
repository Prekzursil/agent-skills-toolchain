"""Conformance over ALL TWELVE blueprints owned by blueprints/bp-1 (cards 1-12 of 96).

Every assertion here is mechanical. The three that matter most for the brief's bar:

* ``test_no_two_blueprints_are_near_duplicates_by_mechanism`` computes set overlap over the
  declared mechanism signatures instead of asking a reader whether twelve documents "feel"
  distinct - LLM judgement on a mechanical comparison measured 86% accurate with every error
  pointing the unsafe way, so the comparison is code.
* ``test_committed_json_is_byte_identical_to_the_builder`` is the drift guard: a hand-edit to a
  generated blueprint would otherwise be invisible until someone re-ran the builder.
* the mutation controls assert GREEN-then-RED in one test, so a check that is silent in both
  states cannot pass here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
for _p in (str(HERE.parent), str(HERE)):
    if _p not in sys.path:  # pragma: no cover - import plumbing
        sys.path.insert(0, _p)

import bp1_testkit as K  # noqa: E402
from wfdsl import schemas, semantics  # noqa: E402

ALL_DOCS = {bp_id: K.load(bp_id) for bp_id in K.BP1_IDS}

#: the six spec-mandated coverage axes. The 96-blueprint SET must span all six; THIS unit owns
#: the research / gem-hunt / brainstorm head of the library, so it is expected to cover a
#: subset. The test asserts which subset, so a silent narrowing is visible.
EXPECTED_AXES = {
    "research-and-evidence",
    "collective-intelligence-and-meta",
    "security-governance-and-risk",
    "data-science-knowledge-and-creative",
}
AXES_NOT_IN_THIS_RANGE = {"engineering-and-reliability", "product-design-and-strategy"}


def test_exactly_twelve_blueprints_are_owned_by_this_unit():
    assert len(K.BP1_IDS) == 12
    assert len(set(K.BP1_IDS)) == 12


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_blueprint_is_schema_valid(bp_id: str):
    assert K.schema_errors(ALL_DOCS[bp_id]) == []


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_blueprint_has_zero_semantic_violations(bp_id: str):
    assert K.semantic_violations(ALL_DOCS[bp_id]) == []


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_worked_example_params_typecheck_and_plan_matches_the_declared_order(
    bp_id: str,
):
    doc = ALL_DOCS[bp_id]
    ex = K.example(doc)
    plan = K.plan_from_example(doc)
    assert plan.stage_order == ex["expected_stage_order"]
    assert sorted(plan.skipped) == sorted(ex.get("expected_skipped", []))
    if "expected_max_parallel" in ex:
        assert plan.max_parallel == ex["expected_max_parallel"]
    if "expected_gate_ids" in ex:
        assert sorted(s.stage_id for s in plan.gates) == sorted(ex["expected_gate_ids"])


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_a_required_param_cannot_be_omitted(bp_id: str):
    """Typed params are load-bearing: dropping a required one must raise, not default."""
    doc = ALL_DOCS[bp_id]
    required = [
        name for name, spec in (doc.get("params") or {}).items() if spec.get("required")
    ]
    assert required, (
        f"{bp_id} declares no required param; its inputs are then unconstrained"
    )
    ex = K.example(doc)
    for name in required:
        params = {k: v for k, v in ex["params"].items() if k != name}
        with pytest.raises(K.D.ParamError):
            K.D.plan_workflow(doc, params, ex.get("facts", {}))


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_a_wrongly_typed_param_is_rejected(bp_id: str):
    doc = ALL_DOCS[bp_id]
    ex = K.example(doc)
    specs = doc.get("params") or {}
    target = next(
        (
            n
            for n, s in specs.items()
            if s.get("type") in {"integer", "number"} and n in ex["params"]
        ),
        None,
    )
    if target is None:
        pytest.skip(f"{bp_id} binds no numeric param in its worked example")
    params = dict(ex["params"])
    params[target] = "not-a-number"
    with pytest.raises(K.D.ParamError):
        K.D.plan_workflow(doc, params, ex.get("facts", {}))


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_every_declared_schema_reference_resolves_and_compiles(bp_id: str):
    doc = ALL_DOCS[bp_id]
    refs = K.declared_schema_refs(doc)
    assert refs, f"{bp_id} declares no schema reference; its artifacts are then untyped"
    for ref in refs:
        validator = K.resolve_schema_ref(ref)
        assert validator is not None, f"{bp_id}: {ref} resolved to nothing"


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_every_requested_tool_is_permitted_by_the_policy(bp_id: str):
    """Second, independent signal on DSL-SEM-011: this walk also covers inline work units."""
    assert K.D.denied_tool_requests(ALL_DOCS[bp_id]) == []


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_the_tool_policy_is_load_bearing_not_decorative(bp_id: str):
    """An allowlist that permits everything requested is theatre; prove it can refuse."""
    doc = ALL_DOCS[bp_id]
    policy = doc["tool_policy"]
    assert policy["default"] == "deny"
    assert policy.get("deny"), f"{bp_id} denies nothing explicitly"
    K.both_states(
        doc,
        lambda d: d["stages"][0].setdefault("tool_permissions", []).append("Bash"),
        K.is_conformant,
        f"{bp_id}: adding an out-of-policy tool to a stage",
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_no_unbounded_loop_fanout_or_checkpoint(bp_id: str):
    assert K.D.unbounded_constructs(ALL_DOCS[bp_id]) == []


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_declared_stopping_rule_controls_hold_in_both_states(bp_id: str):
    doc = ALL_DOCS[bp_id]
    controls = K.example(doc)["stopping_rule_controls"]
    assert controls, f"{bp_id} declares no stopping-rule control"
    for control in controls:
        K.stopping_both_states(doc, control)


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_every_inline_work_unit_carries_all_nineteen_fields(bp_id: str):
    doc = ALL_DOCS[bp_id]
    validator = schemas.work_unit_validator("structural")
    units = K.work_units(doc)
    assert units, (
        f"{bp_id} has no inline work unit; its task stages are then unexecutable"
    )
    for uid, unit in units.items():
        errs = schemas.error_summary(validator.iter_errors(unit), limit=4)
        assert errs == [], f"{bp_id}/{uid}: {errs}"


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_every_work_unit_sentinel_names_its_own_id(bp_id: str):
    """SEM-002 applied to the INLINE units - the rule 96 catalog units violate."""
    for uid, unit in K.work_units(ALL_DOCS[bp_id]).items():
        assert f"SUCCESS:{uid}" in unit["completion_sentinel"]
        assert f"FAILED:{uid}" in unit["completion_sentinel"]


def test_work_unit_ids_are_unique_across_the_twelve():
    seen: dict[str, str] = {}
    for bp_id, doc in ALL_DOCS.items():
        for uid in K.work_units(doc):
            assert uid not in seen, f"{uid} declared in both {seen[uid]} and {bp_id}"
            seen[uid] = bp_id
    assert len(seen) >= 60


def test_work_unit_output_paths_are_unique_across_the_twelve():
    """SEM-004: two units writing one path race and lose work."""
    owners: dict[str, str] = {}
    for bp_id, doc in ALL_DOCS.items():
        for uid, unit in K.work_units(doc).items():
            path = unit["output_path"]
            assert path not in owners, (
                f"{path} claimed by {owners[path]} and {bp_id}/{uid}"
            )
            owners[path] = f"{bp_id}/{uid}"


def test_no_two_blueprints_are_near_duplicates_by_mechanism():
    """MECHANISM overlap, computed - not a reader's impression of distinctness."""
    sets = {bp_id: K.mechanism_set(doc) for bp_id, doc in ALL_DOCS.items()}
    for bp_id, tokens in sets.items():
        assert len(tokens) >= 5, f"{bp_id} declares only {len(tokens)} mechanisms"
    worst = (0.0, "", "")
    for i, a in enumerate(K.BP1_IDS):
        for b in K.BP1_IDS[i + 1 :]:
            overlap = K.jaccard(sets[a], sets[b])
            if overlap > worst[0]:
                worst = (overlap, a, b)
            assert sets[a] != sets[b], (
                f"{a} and {b} declare an IDENTICAL mechanism signature"
            )
            assert overlap <= 0.34, (
                f"{a} vs {b}: mechanism overlap {overlap:.2f} is too high - merge them or "
                f"split one, a catalog of near-duplicates manufactures false coverage. "
                f"shared={sorted(sets[a] & sets[b])}"
            )
    assert worst[0] <= 0.34, worst


def test_the_distinctness_detector_can_actually_fail():
    """Control for the test above: two identical signatures MUST trip it."""
    sets = {bp_id: K.mechanism_set(doc) for bp_id, doc in ALL_DOCS.items()}
    a, b = K.BP1_IDS[0], K.BP1_IDS[1]
    assert K.jaccard(sets[a], sets[b]) <= 0.34
    assert (
        K.jaccard(sets[a], set(sets[a])) == 1.0
    )  # a signature vs itself trips the threshold


def test_flagship_count_meets_the_pro_rata_floor():
    """The spec wants >=40 of 96 flagship; 12/96 of 40 is 5, and this unit ships 6."""
    declared = {bp_id for bp_id, doc in ALL_DOCS.items() if doc.get("flagship")}
    assert declared == set(K.FLAGSHIP_IDS)
    assert len(declared) >= 5
    assert len(declared) == 6


@pytest.mark.parametrize("bp_id", K.FLAGSHIP_IDS)
def test_each_flagship_has_a_dedicated_end_to_end_test_file(bp_id: str):
    name = "test_" + bp_id.replace("-", "_") + ".py"
    assert (HERE / name).is_file(), f"flagship {bp_id} has no {name}"


def test_categories_cover_the_expected_axes_and_declare_what_this_range_does_not():
    seen: set[str] = set()
    for doc in ALL_DOCS.values():
        seen.update(doc.get("categories") or [])
    assert seen == EXPECTED_AXES, (
        f"axis drift: got {sorted(seen)}, expected {sorted(EXPECTED_AXES)}"
    )
    assert not (seen & AXES_NOT_IN_THIS_RANGE), (
        "cards 1-12 are the research / gem-hunt / brainstorm head of the library; labelling one "
        "of them engineering-and-reliability or product-design-and-strategy would be a "
        "mislabel, not coverage. Those axes belong to other ranges of the 96."
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_dry_run_is_supported_and_emits_what_it_promises(bp_id: str):
    doc = ALL_DOCS[bp_id]
    report = K.D.dry_run_report(
        doc, K.example(doc)["params"], K.example(doc).get("facts", {})
    )
    for promised in report["emits"]:
        key = {
            "permission-report": "permission_report",
            "artifact-diff": "artifact_contract",
        }.get(promised, promised)
        assert key in report, (
            f"{bp_id} promises to emit {promised!r} but the report has no {key!r}"
        )
    assert report["permission_report"]["requested_but_not_permitted"] == []
    assert report["unbounded_constructs"] == []
    assert doc["dry_run"]["forbid_tools"], (
        f"{bp_id} claims side-effect-free with nothing forbidden"
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_a_secret_param_value_never_reaches_the_dry_run_report(bp_id: str):
    doc = ALL_DOCS[bp_id]
    secrets = K.D.secret_param_names(doc)
    if not secrets:
        pytest.skip(f"{bp_id} declares no secret param")
    ex = K.example(doc)
    params = dict(ex["params"])
    canary = "sk-bp1-canary-value-do-not-log"
    for name in secrets:
        params[name] = canary
    blob = json.dumps(
        K.D.dry_run_report(doc, params, ex.get("facts", {})), ensure_ascii=True
    )
    assert canary not in blob
    for name in secrets:
        assert f"<secret_ref:{name}>" in blob


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_failure_policy_forbids_silence(bp_id: str):
    policy = ALL_DOCS[bp_id]["failure_policy"]
    assert policy["terminal_state_required"] is True
    assert policy["never_silent"] is True
    assert policy["classify_as"]


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_estimate_basis_is_not_a_measured_claim_nobody_measured(bp_id: str):
    """None of the twelve has ever been run, so a measured basis would be fabrication."""
    est = ALL_DOCS[bp_id]["estimate"]
    assert est["basis"] == "static-declared"
    assert "measurement_source" not in est


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_lineage_credits_its_sources_and_cites_the_design_card(bp_id: str):
    doc = ALL_DOCS[bp_id]
    sources = doc["lineage"]["derived_from"]
    assert len(sources) >= 2, f"{bp_id} claims fewer than two sources"
    assert any("09-WORKFLOW-BLUEPRINT-LIBRARY.md#" in s["source"] for s in sources)
    card = doc["x_extensions"]["blueprint_source"]["card"]
    assert any(card in s["source"] for s in sources)


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_every_blueprint_declares_a_contraindication_and_an_unverified_note(bp_id: str):
    ext = ALL_DOCS[bp_id]["x_extensions"]
    assert len(ext["contraindications"]) >= 2
    assert ext["unverified"], (
        f"{bp_id} claims no residual uncertainty; none of these twelve has ever been executed, "
        "so an empty UNVERIFIED list is an overclaim"
    )


# --------------------------------------------------------------- mutation controls


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_mutation_deleting_a_fanout_concurrency_cap_is_rejected(bp_id: str):
    doc = ALL_DOCS[bp_id]
    fanouts = [
        st for _p, st in semantics.iter_stages(doc) if st.get("kind") == "fanout"
    ]
    if not fanouts:
        pytest.skip(f"{bp_id} has no fanout stage")
    target = fanouts[0]["id"]

    def mutate(d):
        for _p, st in semantics.iter_stages(d):
            if st.get("id") == target:
                st.pop("max_concurrency", None)

    K.both_states(doc, mutate, K.is_conformant, f"{bp_id}: unbounded fan-out")


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_mutation_pointing_a_stage_role_at_an_undeclared_role_is_rejected(bp_id: str):
    def mutate(d):
        for st in d["stages"]:
            if st.get("role"):
                st["role"] = "role-that-does-not-exist"
                return
        d["stages"][0]["role"] = "role-that-does-not-exist"

    K.both_states(
        ALL_DOCS[bp_id], mutate, K.is_conformant, f"{bp_id}: undeclared stage role"
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_mutation_an_unparseable_stopping_expression_is_rejected(bp_id: str):
    def mutate(d):
        d["stopping_rules"][0]["expression"] = "consensus >= AND"

    K.both_states(
        ALL_DOCS[bp_id], mutate, K.is_conformant, f"{bp_id}: unparseable stopping rule"
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_mutation_a_dangling_depends_on_is_rejected(bp_id: str):
    def mutate(d):
        d["stages"][-1]["depends_on"] = ["stage-that-does-not-exist"]

    K.both_states(
        ALL_DOCS[bp_id], mutate, K.is_conformant, f"{bp_id}: dangling depends_on"
    )


@pytest.mark.parametrize("bp_id", K.BP1_IDS)
def test_mutation_reordering_a_dependency_changes_the_planned_order(bp_id: str):
    """The declared expected_stage_order is load-bearing, not decoration."""
    doc = ALL_DOCS[bp_id]
    expected = K.example(doc)["expected_stage_order"]

    def order_matches(d) -> bool:
        try:
            return K.plan_from_example(d).stage_order == expected
        except K.D.PlanError:
            return False

    def mutate(d):
        for st in reversed(d["stages"]):
            if st.get("depends_on"):
                st["depends_on"] = []
                return

    K.both_states(doc, mutate, order_matches, f"{bp_id}: dropping a dependency edge")


def test_committed_json_is_byte_identical_to_the_builder():
    """Drift guard: a hand-edit to a generated blueprint must be caught."""
    rc = K.B.main(["--check", "--out", str(K.WORKFLOW_DIR)])
    assert rc == 0, "at least one committed blueprint differs from bp1_build.py output"


def test_the_drift_guard_can_actually_fail(tmp_path: Path):
    """Control for the guard above: an empty output dir MUST make it report drift."""
    rc = K.B.main(["--check", "--out", str(tmp_path)])
    assert rc == 1
