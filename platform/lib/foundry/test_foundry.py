"""Tests for workflow-scout and workflow-forge.

Structure follows the detector discipline this program is built on: for every predicate that can
say "no", there is a case where it MUST say "yes" and a case where it MUST say "no". A probe that
is silent in both states measures nothing, so a one-sided test of a detector is not a test.

The hazard-detector and capability-probe suites are parametrised over the FULL vocabularies, so
adding a capability to the capability map or a hazard to the model without a working detector
fails here rather than shipping as a decoration.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from foundry import bench, forge, mechanisms, registry, scout
from foundry.model import (
    BENEFIT_AXES,
    COST_DIMENSIONS,
    Candidate,
    FUSION_STRATEGIES,
    Goal,
    HAZARD_IDS,
    LICENSE_TIERS,
    capabilities,
    classify_license,
    mandated_capabilities,
)

REPO_ROOT = Path(__file__).resolve().parents[3]


# ------------------------------------------------------------------ fixtures


def _minimal_workflow(wid: str = "wf.min") -> dict:
    """The smallest document the DSL schema accepts. Deliberately capability-poor."""
    return {
        "dsl_version": "1.0.0",
        "id": wid,
        "name": "minimal",
        "version": "1.0.0",
        "stages": [{"id": "only", "kind": "task", "work_unit_ref": "AAA-0001"}],
    }


def _rich_workflow(wid: str = "wf.rich") -> dict:
    """A document that exercises every hazard mitigation and most capabilities."""
    return {
        "dsl_version": "1.0.0",
        "id": wid,
        "name": "rich",
        "version": "1.0.0",
        "description": "x" * 120,
        "params": {"items": {"type": "array", "description": "the things to process"}},
        "roles": {
            "worker": {
                "description": "does the work",
                "independence": "independent",
                "tool_permissions": ["Read"],
            },
            "checker": {
                "description": "checks the work",
                "independence": "independent",
                "cross_vendor_required": True,
                "tool_permissions": ["Read"],
            },
            "owner": {"description": "the human owner", "authority": "owner"},
        },
        "tool_policy": {
            "default": "deny",
            "allow": ["Read", "Write"],
            "network": "none",
            "source_policy": {
                "treat_fetched_content_as_data": True,
                "require_provenance": True,
            },
        },
        "model_routing": {"default": {"model": "opus", "vendor": "anthropic"}},
        "gates": {
            "done": {
                "predicate": "completion-predicate-v1",
                "conditions_required": [1, 2, 3],
                "on_fail": "repair",
                "blocking": True,
                "evidence_required": True,
            }
        },
        "stages": [
            {
                "id": "spread",
                "kind": "fanout",
                "title": "fan out over the items",
                "over": {"source": "param", "ref": "items", "item_var": "item"},
                "max_concurrency": 4,
                "body": [
                    {
                        "id": "one",
                        "kind": "task",
                        "title": "process one item with a known-broken control probe",
                        "role": "worker",
                        "tool_permissions": ["Read"],
                        "work_unit_ref": "AAA-0001",
                    }
                ],
            },
            {
                "id": "join",
                "kind": "barrier",
                "title": "fan back in",
                "depends_on": ["spread"],
                "checkpoint": True,
                "barrier": {"mode": "all", "on_partial": "proceed-with-quarantine"},
                "produces": [
                    {
                        "path": "command-center/out/rich.json",
                        "schema_ref": "platform/schema/receipt.schema.json",
                        "min_bytes": 256,
                        "register_in_manifest": True,
                        "consumers": ["check"],
                    }
                ],
            },
            {
                "id": "loop",
                "kind": "loop",
                "title": "refine until converged",
                "depends_on": ["join"],
                "loop_var": "round",
                "convergence": {
                    "max_iterations": 5,
                    "no_progress_rounds": 2,
                    "metrics": [{"name": "score", "direction": "increase"}],
                    "converged_when": "score >= 1",
                },
                "body": [
                    {
                        "id": "refine",
                        "kind": "task",
                        "title": "refine",
                        "role": "worker",
                        "work_unit_ref": "AAA-0002",
                    }
                ],
            },
            {
                "id": "fix",
                "kind": "repair_loop",
                "title": "repair with an independent verify",
                "depends_on": ["loop"],
                "target": ["join"],
                "max_attempts": 3,
                "verify": {
                    "id": "verify-fix",
                    "kind": "task",
                    "title": "verify",
                    "role": "checker",
                    "work_unit_ref": "AAA-0003",
                },
            },
            {
                "id": "check",
                "kind": "gate",
                "title": "the completion gate",
                "depends_on": ["fix"],
                "gate_ref": "done",
            },
            {
                "id": "ask-owner",
                "kind": "human_checkpoint",
                "title": "owner signs off on the irreversible step",
                "depends_on": ["check"],
                "prompt": "Approve the irreversible publish?",
                "approval_mode": "owner-only",
                "on_timeout": "escalate",
                # the schema requires a bound whenever on_timeout is declared: an escalation
                # policy with no timeout can never fire
                "timeout_seconds": 86400,
            },
            {
                "id": "call-child",
                "kind": "subworkflow",
                "title": "delegate to a child workflow",
                "depends_on": ["ask-owner"],
                "workflow": {"workflow_id": "child"},
            },
        ],
        "subworkflows": {"child": {"workflow_id": "child", "version_range": ">=1.0.0"}},
        "stopping_rules": [
            {"id": "enough", "expression": "score >= 1 AND no_progress_rounds >= 2"}
        ],
        "retry_policy": {
            "strategy": "two-strikes-then-pivot",
            "max_attempts": 2,
            "pivot": {"after_attempts": 2, "enumerate_alternatives_min": 2},
        },
        "failure_policy": {
            "on_failure": "degrade-loudly",
            "terminal_state_required": True,
            "never_silent": True,
            "preserve_partial_artifact": True,
        },
        "resume": {
            "enabled": True,
            "checkpoint_store": "command-center/ckpt",
            "idempotency_key_from": ["workflow_id", "stage_id"],
            "stale_checkpoint_seconds": 3600,
            "on_stale": "warn-and-resume",
        },
        # every one of these blocks carries the fields the schema conditionally REQUIRES once the
        # capability is claimed (a deterministic-replay claim needs a seed, a journal, a recorded
        # field set and a verify mode, or the claim is decorative). The first version of this
        # fixture omitted them and the real DSL gate rejected it - which is the gate working.
        "replay": {
            "deterministic": True,
            "seed": 7,
            "journal_path": "command-center/replay/rich.jsonl",
            "record": ["params", "inputs", "tool_calls"],
            "verify": "hash-equal",
            "forbid_nondeterministic_sources": ["clock", "random", "network"],
        },
        "cache": {
            "enabled": True,
            "key_from": ["inputs_hash"],
            "store": "command-center/cache",
            "verify_integrity": True,
        },
        "dry_run": {
            "supported": True,
            "emits": ["plan", "estimate"],
            "side_effect_free": True,
            "forbid_tools": ["Write"],
        },
        "estimate": {"basis": "static-declared", "confidence": "likely"},
        "portability": {
            "export": {
                "format": "json",
                "redact_secrets": True,
                "includes": ["definition", "lineage"],
            },
            "import": {
                "validate_against": "platform/schema/workflow-dsl.schema.json",
                "on_version_mismatch": "reject",
            },
        },
        "lineage": {
            "derived_from": [
                {"source": "seed", "relation": "REBUILD-FROM-SPEC", "credit": "owner"}
            ],
            "decomposable_back_to_sources": True,
            "rollback_to": ["seed@1.0.0"],
        },
        "outputs": {
            "result": {
                "path": "command-center/out/rich.json",
                "schema_ref": "platform/schema/receipt.schema.json",
            }
        },
    }


@pytest.fixture(scope="module")
def real_blueprints() -> list[Candidate]:
    cands = [c for c in registry.load_dsl_candidates() if c.dsl_doc]
    if len(cands) < 2:
        pytest.skip("the executable blueprint corpus is not populated yet")
    return sorted(cands, key=lambda c: c.id)


# --------------------------------------------------------------- vocabularies


def test_every_capability_map_id_has_a_structural_probe():
    missing = set(capabilities()) - set(mechanisms._CAPABILITY_PROBES)
    assert not missing, f"capability ids with no probe: {sorted(missing)}"


def test_every_capability_has_declared_tokens():
    missing = [c for c in capabilities() if not mechanisms._DECLARED_TOKENS.get(c)]
    assert not missing, f"capabilities with no lexical evidence tokens: {missing}"


def test_every_hazard_has_exactly_one_detector():
    assert set(mechanisms.HAZARD_DETECTORS) == set(HAZARD_IDS)


def test_benefit_axes_and_cost_dimensions_are_disjoint():
    assert not (set(BENEFIT_AXES) & set(COST_DIMENSIONS))


def test_mandated_capabilities_are_a_subset_of_all():
    assert mandated_capabilities() <= set(capabilities())


# ----------------------------------------------- capability probes, both states


@pytest.mark.parametrize("cap", list(capabilities()))
def test_capability_probe_fires_on_rich_and_is_silent_on_minimal(cap):
    """The both-states control for all 24 capability probes.

    ``stages`` and ``work_unit_binding`` are the two the minimal document legitimately has - a
    document with no stages is not a workflow - so those are asserted in the one direction that
    is meaningful.
    """
    rich = mechanisms.structural_capabilities(_rich_workflow())
    minimal = mechanisms.structural_capabilities(_minimal_workflow())
    if cap in ("stages", "work_unit_binding"):
        assert rich[cap] is True and minimal[cap] is True
        return
    assert rich[cap] is True, f"{cap} should be detected in the rich document"
    assert minimal[cap] is False, f"{cap} must NOT be detected in the minimal document"


@pytest.mark.parametrize("hazard", list(HAZARD_IDS))
def test_hazard_detector_fires_on_mitigated_and_not_on_bare(hazard):
    """The both-states control for all 16 hazard detectors."""
    assert mechanisms.HAZARD_DETECTORS[hazard](_rich_workflow()) is True, (
        f"{hazard} detector did not fire on a document that mitigates it"
    )
    assert mechanisms.HAZARD_DETECTORS[hazard](_minimal_workflow()) is False, (
        f"{hazard} detector fired on a document with no mitigation - it measures nothing"
    )


@pytest.mark.parametrize(
    "hazard,mutate",
    [
        (
            "straggler-work-silently-dropped",
            lambda d: d["stages"][1]["barrier"].pop("on_partial"),
        ),
        ("unbounded-retry-grind", lambda d: d["retry_policy"].pop("max_attempts")),
        (
            "unbounded-loop",
            lambda d: d["stages"][2]["convergence"].pop("max_iterations"),
        ),
        (
            "silent-failure",
            lambda d: d["failure_policy"].update(
                {"terminal_state_required": None, "never_silent": None}
            ),
        ),
        (
            "secret-value-in-export",
            lambda d: d["portability"]["export"].update({"redact_secrets": False}),
        ),
        (
            "untrusted-fetched-content-executed",
            lambda d: d["tool_policy"]["source_policy"].pop(
                "treat_fetched_content_as_data"
            ),
        ),
        ("stale-checkpoint-resumed", lambda d: d["resume"].pop("on_stale")),
        (
            "tool-privilege-escalation",
            lambda d: d["tool_policy"].update({"default": "allow"}),
        ),
        (
            "irreversible-action-without-human",
            lambda d: d["stages"][5].update({"on_timeout": "proceed"}),
        ),
        ("no-rollback-path", lambda d: d["lineage"].pop("rollback_to")),
        (
            "unverifiable-claim",
            lambda d: d["gates"]["done"].update({"evidence_required": False}),
        ),
        ("total-loss-on-freeze", lambda d: d["resume"].update({"enabled": False})),
        ("cost-blowout", lambda d: d.pop("estimate")),
        (
            "non-deterministic-replay",
            lambda d: d["replay"].update(
                {"forbid_nondeterministic_sources": ["network"]}
            ),
        ),
    ],
)
def test_hazard_detector_flips_when_its_exact_mitigation_is_removed(hazard, mutate):
    """MUTATION test: break precisely the field the detector claims to read.

    Stronger than the rich-vs-minimal control above, which a detector could pass by accident
    (the minimal document is missing everything). Here only ONE field changes, so a detector
    that stays True is reading something other than what it claims.
    """
    doc = _rich_workflow()
    assert mechanisms.HAZARD_DETECTORS[hazard](doc) is True
    mutate(doc)
    assert mechanisms.HAZARD_DETECTORS[hazard](doc) is False, (
        f"{hazard} detector survived the removal of its own mitigation"
    )


def test_text_corpus_excludes_the_description_field():
    """A hazard must not become 'covered' by a sentence in the workflow blurb."""
    doc = _minimal_workflow()
    doc["description"] = (
        "we use two independent signals and a known-broken control probe"
    )
    assert mechanisms._h_single_signal(doc) is False
    assert mechanisms._h_both_states(doc) is False


# ------------------------------------------------------------ license tiering


@pytest.mark.parametrize(
    "text,expected",
    [
        ("MIT", "copy-permitted-permissive"),
        ("Apache-2.0", "copy-permitted-permissive"),
        ("BSD-3-Clause", "copy-permitted-permissive"),
        ("GPL-3.0-only", "mechanism-only-copyleft"),
        ("AGPL-3.0", "mechanism-only-copyleft"),
        ("CC-BY-SA-4.0", "mechanism-only-share-alike"),
        (
            "no license declared -- all rights reserved (owner-authored private estate)",
            "copy-permitted-owner",
        ),
        ("no license declared", "mechanism-only-unlicensed-third-party"),
        ("", "unknown-needs-probe"),
        ("some bespoke commercial terms", "unknown-needs-probe"),
    ],
)
def test_license_classification(text, expected):
    assert classify_license(text) == expected


def test_every_license_tier_is_reachable_from_some_input():
    reached = {
        classify_license(t)
        for t in (
            "MIT",
            "owner-authored private estate, no license declared",
            "GPL-2.0",
            "CC-BY-SA",
            "no license declared",
            "",
        )
    }
    assert reached == set(LICENSE_TIERS)


def test_explicit_grant_outranks_the_no_license_phrase():
    """These records often carry BOTH an SPDX id and 'no LICENSE file' prose in one blob."""
    blob = "MIT | MEASURED: no LICENSE/LICENSE.md blob exists at 07f465f3"
    assert classify_license(blob) == "copy-permitted-permissive"


# --------------------------------------------------------- provenance probing


def test_provenance_probe_both_states(tmp_path):
    """The detector control: it must resolve a known-present path AND refuse a known-absent one."""
    present = tmp_path / "here.json"
    present.write_text("{}", encoding="utf-8")
    ok, probe = registry.probe_anchor(str(present))
    assert ok is True and "True" in probe
    bad, probe2 = registry.probe_anchor(str(tmp_path / "nope.json"))
    assert bad is False and "False" in probe2


@pytest.mark.parametrize(
    "anchor,kind",
    [
        ("C:/Users/x/y/SKILL.md", "abs-path"),
        ("C:\\Users\\x\\y\\SKILL.md:2", "abs-path"),
        ("07f465f37d49:skills/x/SKILL.md", "git-rev"),
        ("platform/schema/receipt.schema.json", "repo-relative"),
        ("agents-live", "token"),
        ("", "absent"),
    ],
)
def test_anchor_classification(anchor, kind):
    assert registry.classify_anchor(anchor) == kind


def test_unresolvable_anchor_kinds_are_not_checked_rather_than_absent():
    """Reporting 'this probe cannot decide' as 'does not exist' is the failure we keep paying for."""
    for anchor in ("07f465f3:skills/x/SKILL.md", "agents-live", ""):
        resolved, probe = registry.probe_anchor(anchor)
        assert resolved is None
        assert "NOT-CHECKED" in probe


def test_line_suffix_is_stripped_before_the_filesystem_probe(tmp_path):
    p = tmp_path / "with-lines.md"
    p.write_text("a\nb\n", encoding="utf-8")
    assert registry.probe_anchor(f"{p}:2")[0] is True


# ---------------------------------------------------- registry normalization


def test_registry_loads_every_shape_and_skips_the_manifest_row():
    rows = list(registry.iter_registry_rows())
    assert rows, "no registry rows found"
    assert all("_manifest" not in r for r, _ in rows)
    files = {src for _, src in rows}
    assert len(files) == 5, f"expected 5 registry files, saw {sorted(files)}"


def test_registry_candidates_have_stable_unique_ids():
    cands = registry.load_registry_candidates()
    ids = [c.id for c in cands]
    assert len(ids) == len(set(ids))
    assert "<no-id>" not in ids


def test_normalize_handles_all_three_provenance_field_spellings():
    for row, expect in (
        ({"id": "a", "provenance": {"anchor": "x/y.json"}}, "x/y.json"),
        ({"id": "b", "provenance": {"primary_anchor": "p/q.json"}}, "p/q.json"),
        ({"id": "c", "primary_anchor": "t/u.json"}, "t/u.json"),
    ):
        assert registry.normalize_row(row, "test.json").provenance_anchor == expect


def test_normalize_handles_license_as_string_and_as_object():
    s = registry.normalize_row({"id": "a", "license": "MIT"}, "t.json")
    o = registry.normalize_row(
        {"id": "b", "license": {"spdx": "MIT", "declared": "MIT"}}, "t.json"
    )
    assert s.license_tier == o.license_tier == "copy-permitted-permissive"


def test_population_summary_partitions_the_tristate_exactly():
    cands = registry.load_all()
    s = registry.population_summary(cands)
    assert (
        s["provenance_resolved_true"]
        + s["provenance_resolved_false"]
        + s["provenance_not_checked"]
        == s["total"]
    )
    assert s["registry_rows"] + s["executable_dsl_blueprints"] == s["total"]


def test_dsl_candidates_are_discriminated_by_dsl_version_not_filename():
    """The workflows directory also holds *-STATUS.json sidecars from sibling lanes."""
    for c in registry.load_dsl_candidates():
        assert c.dsl_doc is not None and "dsl_version" in c.dsl_doc


# ------------------------------------------------------------ mechanism algebra


def test_semantic_diff_is_exact_set_algebra():
    a = mechanisms.MechanismProfile(
        "a", mechanisms.STRUCTURAL, {"x": True, "y": True, "z": False}, {}
    )
    b = mechanisms.MechanismProfile(
        "b", mechanisms.STRUCTURAL, {"x": True, "y": False, "z": True}, {}
    )
    d = mechanisms.semantic_diff(a, b)
    assert d["shared_capabilities"] == ["x"]
    assert d["only_a"] == ["y"] and d["only_b"] == ["z"]
    # the reported value is rounded to 4dp on purpose (report stability), so compare with an
    # absolute tolerance rather than the default relative one
    assert d["capability_jaccard"] == pytest.approx(1 / 3, abs=1e-4)
    assert d["complementary"] is True


def test_collapse_duplicates_collapses_identical_and_keeps_distinct():
    p = lambda i, caps: mechanisms.MechanismProfile(  # noqa: E731
        i, mechanisms.STRUCTURAL, {c: c in caps for c in ("x", "y")}, {}
    )
    res = mechanisms.collapse_duplicates([p("a", {"x"}), p("b", {"x"}), p("c", {"y"})])
    assert res["group_count"] == 2 and res["collapsed"] == 1
    assert ["a", "b"] in res["groups_with_duplicates"]


def test_declared_profile_never_claims_hazard_coverage():
    """Prose cannot prove a mitigation, so a DECLARED profile must report zero hazards."""
    cand = Candidate(
        id="x",
        name="x",
        source_file="t.json",
        task_fit="uses a barrier and a fan-in with resume and rollback",
    )
    prof = mechanisms.profile(cand)
    assert prof.derivation == mechanisms.DECLARED
    assert prof.covered_hazards == set()
    assert prof.structural_only is False


def test_stage_mechanism_map_covers_every_stage():
    doc = _rich_workflow()
    smap = mechanisms.stage_mechanism_map(doc)
    all_ids = {str(st.get("id")) for _, st in mechanisms.iter_stages(doc)}
    assert set(smap) == all_ids
    assert all(v for v in smap.values())


# -------------------------------------------------------------------- benchmark


def test_default_cases_are_well_formed_and_discriminating():
    for c in bench.DEFAULT_CASES:
        assert c.validate() == []
    demanded_caps = {x for c in bench.DEFAULT_CASES for x in c.required_capabilities}
    demanded_haz = {x for c in bench.DEFAULT_CASES for x in c.hazards}
    assert len(demanded_caps) >= 15
    assert demanded_haz == set(HAZARD_IDS), (
        "the case library must exercise every hazard or some detector is never used"
    )


def test_a_case_that_demands_nothing_is_rejected():
    assert bench.Case("empty", "t", (), ()).validate()


def test_rich_beats_minimal_on_every_axis():
    cases = list(bench.DEFAULT_CASES)
    rich = bench.benchmark(_rich_workflow(), cases)
    minimal = bench.benchmark(_minimal_workflow(), cases)
    for axis in BENEFIT_AXES:
        assert rich.axes_mean[axis] > minimal.axes_mean[axis], axis


def test_axes_respond_to_removing_a_single_mitigation():
    """A scoring function that cannot go down is not measuring anything."""
    cases = list(bench.DEFAULT_CASES)
    base = bench.benchmark(_rich_workflow(), cases).axes_mean
    doc = _rich_workflow()
    doc["resume"]["enabled"] = False
    after = bench.benchmark(doc, cases).axes_mean
    assert after["recovery"] < base["recovery"]
    assert after["coverage"] < base["coverage"]


def test_the_dsl_gate_is_the_real_validator():
    valid = bench.benchmark(_rich_workflow(), list(bench.DEFAULT_CASES))
    assert valid.schema_valid and valid.semantic_violations == 0 and valid.gate_ok
    broken = _rich_workflow()
    broken["stages"][4]["gate_ref"] = "does-not-exist"
    bad = bench.benchmark(broken, list(bench.DEFAULT_CASES))
    assert bad.semantic_violations >= 1 and bad.gate_ok is False


def test_cost_vector_counts_stages_but_is_not_an_axis():
    cost = bench.cost_vector(_rich_workflow())
    assert cost["stage_count"] >= 6
    assert set(cost) == set(COST_DIMENSIONS)
    assert not set(cost) & set(BENEFIT_AXES)


# ------------------------------------------------------------------ certification


def _result(wid: str, **axes) -> bench.BenchResult:
    return bench.BenchResult(
        workflow_id=wid,
        per_case=[],
        axes_mean={a: axes.get(a, 0.5) for a in BENEFIT_AXES},
        cost={k: 1 for k in COST_DIMENSIONS},
        schema_valid=True,
        semantic_violations=0,
    )


def test_certify_accepts_a_genuine_improvement():
    cert = bench.certify(
        _result("f", coverage=0.7), [_result("a"), _result("b")], decomposes_back=True
    )
    assert cert.verdict == "CERTIFIED" and cert.accepted
    assert "coverage" in cert.improvements


def test_certify_rejects_when_no_axis_improves():
    cert = bench.certify(
        _result("f"), [_result("a"), _result("b")], decomposes_back=True
    )
    assert cert.verdict == "REJECTED"
    assert any("no-axis-improved" in r for r in cert.reasons)


def test_certify_rejects_a_bigger_workflow_that_improves_nothing():
    """The spec sentence, as a test: more stages is not an acceptance reason."""
    fused = _result("f")
    fused.cost = {**fused.cost, "stage_count": 99}
    cert = bench.certify(fused, [_result("a"), _result("b")], decomposes_back=True)
    assert cert.verdict == "REJECTED"
    assert cert.cost_delta["stage_count"] == 98
    assert any(
        "more stages is NOT an acceptance reason"
        in r.replace("a larger stage count", "more stages is")
        or "no-axis-improved" in r
        for r in cert.reasons
    )


def test_certify_rejects_a_regression_even_with_an_improvement():
    cert = bench.certify(
        _result("f", coverage=0.9, usability=0.1),
        [_result("a"), _result("b")],
        decomposes_back=True,
    )
    assert cert.verdict == "REJECTED"
    assert "usability" in cert.regressions


def test_certify_rejects_a_fusion_that_does_not_decompose():
    cert = bench.certify(
        _result("f", coverage=0.9), [_result("a")], decomposes_back=False
    )
    assert cert.verdict == "REJECTED"
    assert any("decompose" in r for r in cert.reasons)


def test_certify_rejects_a_fused_document_that_fails_the_dsl_gate():
    fused = _result("f", coverage=0.9)
    fused.schema_valid = False
    cert = bench.certify(fused, [_result("a")], decomposes_back=True)
    assert cert.verdict == "REJECTED"
    assert any("DSL gate" in r for r in cert.reasons)


def test_certify_rejects_with_no_sources():
    assert bench.certify(_result("f"), []).verdict == "REJECTED"


def test_certify_rejects_gratuitous_stages():
    cert = bench.certify(
        _result("f", coverage=0.9),
        [_result("a")],
        decomposes_back=True,
        gratuitous=["d1.freeloader"],
    )
    assert cert.verdict == "REJECTED"
    assert any("gratuitous-cost" in r for r in cert.reasons)


def test_gratuitous_stages_finds_a_freeloader_and_spares_a_contributor():
    """Both states of the ablation gate on one document."""
    doc = _rich_workflow()
    doc["stages"].append(
        {
            "id": "freeloader",
            "kind": "task",
            "title": "adds nothing measurable",
            "role": "worker",
            "work_unit_ref": "AAA-0009",
            "depends_on": ["ask-owner"],
        }
    )
    cases = list(bench.DEFAULT_CASES)
    gratis = bench.gratuitous_stages(doc, cases, ["freeloader", "ask-owner"])
    assert "freeloader" in gratis, "a stage that changes no axis was not detected"
    assert "ask-owner" not in gratis, (
        "the human checkpoint IS load-bearing for two hazards"
    )


# ------------------------------------------------------------------------ goals


def test_goal_validation_rejects_unknown_vocabulary():
    problems = Goal(
        text="x", required_capabilities=["not-a-cap"], hazards=["not-a-hazard"]
    ).validate()
    assert len(problems) == 2


def test_goal_validation_rejects_an_empty_goal():
    assert Goal(text="   ").validate()


def test_goal_roundtrips_through_json():
    g = Goal(text="t", required_capabilities=["barriers"], hazards=["silent-failure"])
    assert Goal.from_json(json.loads(json.dumps(g.to_json()))).to_json() == g.to_json()


# ------------------------------------------------------------------------ scout


def test_tokenizer_drops_stopwords_and_short_tokens():
    toks = scout.tokenize("The workflow MUST fan-out to a barrier")
    assert "the" not in toks and "must" not in toks and "workflow" not in toks
    assert "fan-out" in toks and "barrier" in toks


def test_search_ranks_a_capability_match_above_a_non_match():
    want = _rich_workflow("wf.match")
    unwanted = _minimal_workflow("wf.nomatch")
    cands = [
        Candidate(
            id="nomatch",
            name="n",
            source_file="t",
            dsl_doc=unwanted,
            license_text="MIT",
            license_tier="copy-permitted-permissive",
            provenance_resolved=True,
        ),
        Candidate(
            id="match",
            name="m",
            source_file="t",
            dsl_doc=want,
            license_text="MIT",
            license_tier="copy-permitted-permissive",
            provenance_resolved=True,
        ),
    ]
    hits = scout.search(
        Goal(text="barrier fanout", required_capabilities=["barriers"]), cands
    )
    assert hits[0].candidate.id == "match"
    assert hits[-1].candidate.id == "nomatch"


def test_search_is_deterministic():
    cands = registry.load_all()
    g = Goal(text="fan out and fan back in", required_capabilities=["barriers"])
    a = [h.candidate.id for h in scout.search(g, cands, top=15)]
    b = [h.candidate.id for h in scout.search(g, cands, top=15)]
    assert a == b


def test_capability_rarity_ranks_a_rare_capability_above_a_universal_one():
    profs = [
        mechanisms.MechanismProfile(
            str(i), mechanisms.STRUCTURAL, {"stages": True, "barriers": i == 0}, {}
        )
        for i in range(10)
    ]
    rarity = scout.capability_rarity(profs)
    assert rarity["barriers"] > rarity["stages"]


def test_a_non_copyable_license_is_excluded_not_merely_downranked():
    cand = Candidate(
        id="gpl",
        name="g",
        source_file="t",
        dsl_doc=_rich_workflow(),
        license_text="GPL-3.0",
        license_tier="mechanism-only-copyleft",
        provenance_resolved=True,
    )
    goal = Goal(text="x", required_capabilities=["barriers"])
    reasons = scout.verify_candidate(cand, goal)
    assert reasons and "not in the goal allowlist" in reasons[0]
    rec = scout.recommend(goal, scout.search(goal, [cand]))
    assert rec["primary"] in ("CLEAN-ROOM-REIMPLEMENT", "REBUILD-FROM-SPEC")


def test_an_unresolved_provenance_anchor_is_excluded():
    cand = Candidate(
        id="ghost",
        name="g",
        source_file="t",
        dsl_doc=_rich_workflow(),
        license_tier="copy-permitted-owner",
        provenance_resolved=False,
        provenance_probe="os.path.exists(...) -> False",
    )
    assert scout.verify_candidate(cand, Goal(text="x"))


def test_require_executable_excludes_a_prose_row():
    cand = Candidate(
        id="prose",
        name="p",
        source_file="t",
        license_tier="copy-permitted-owner",
        provenance_resolved=True,
    )
    assert scout.verify_candidate(cand, Goal(text="x", require_executable=True))


def test_recommend_says_build_when_nothing_covers_the_goal():
    cand = Candidate(
        id="thin",
        name="t",
        source_file="t",
        dsl_doc=_minimal_workflow(),
        license_tier="copy-permitted-owner",
        provenance_resolved=True,
    )
    goal = Goal(
        text="x", required_capabilities=["barriers", "repair_loops", "subworkflows"]
    )
    rec = scout.recommend(goal, scout.search(goal, [cand]))
    assert any(p["disposition"] == "REBUILD-FROM-SPEC" for p in rec["proposals"])


def test_recommend_says_merge_for_two_complementary_candidates():
    a = _rich_workflow("wf.a")
    for key in ("stages",):  # strip the barrier from a so the two are complementary
        a[key] = [s for s in a[key] if s["id"] != "join"]
    a["stages"][0]["id"] = "spread"
    b = _minimal_workflow("wf.b")
    b["stages"] = [
        {
            "id": "join",
            "kind": "barrier",
            "title": "join",
            "barrier": {"mode": "all", "on_partial": "fail"},
        }
    ]
    cands = [
        Candidate(
            id="wf.a",
            name="a",
            source_file="t",
            dsl_doc=a,
            license_tier="copy-permitted-owner",
            provenance_resolved=True,
        ),
        Candidate(
            id="wf.b",
            name="b",
            source_file="t",
            dsl_doc=b,
            license_tier="copy-permitted-owner",
            provenance_resolved=True,
        ),
    ]
    goal = Goal(text="x", required_capabilities=["barriers", "repair_loops"])
    rec = scout.recommend(goal, scout.search(goal, cands))
    assert any(p["disposition"] in ("MERGE", "COMPOSE") for p in rec["proposals"])


def test_scout_report_is_byte_stable_for_the_same_inputs():
    cands = registry.load_all()
    g = Goal(text="resume a long program", required_capabilities=["resume"])
    r1 = scout.scout_report(g, cands, top=5)
    r2 = scout.scout_report(g, cands, top=5)
    assert json.dumps(r1, sort_keys=True) == json.dumps(r2, sort_keys=True)
    assert "generated_at" not in json.dumps(r1)


def test_scout_report_carries_the_derivation_honesty_note():
    r = scout.scout_report(Goal(text="x"), registry.load_all(), top=2)
    assert "declared" in r["honesty"]["derivation_note"]
    assert "NOT-CHECKED" in r["honesty"]["provenance_tristate"]


def test_scout_cli_population_and_vocab_exit_zero(capsys):
    assert scout.main(["population"]) == 0
    assert "SUCCESS:scout-population" in capsys.readouterr().out
    assert scout.main(["vocab"]) == 0
    assert "SUCCESS:scout-vocab" in capsys.readouterr().out


def test_scout_cli_rejects_a_malformed_goal(capsys):
    assert scout.main(["search", "--goal-text", "x", "--require", "nope"]) == 2
    assert "FAILED:scout-search" in capsys.readouterr().err


def test_scout_cli_search_runs_end_to_end(capsys):
    assert (
        scout.main(
            [
                "search",
                "--goal-text",
                "fan out and rejoin",
                "--require",
                "barriers",
                "--top",
                "3",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "SUCCESS:scout-search" in out and "recommendation:" in out


# ------------------------------------------------------------------------ forge


def test_fuse_rejects_an_unknown_strategy():
    with pytest.raises(ValueError):
        forge.fuse(_rich_workflow("a"), _rich_workflow("b"), strategy="telepathy")


def test_fused_document_passes_the_real_dsl_gate():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    fusion = forge.fuse(a, b)
    valid, violations, errors = bench._run_dsl_gate(fusion.doc)
    assert valid, errors
    assert violations == 0


def test_fusion_is_deterministic():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    one = json.dumps(forge.fuse(a, b).doc, sort_keys=True)
    two = json.dumps(forge.fuse(copy.deepcopy(a), copy.deepcopy(b)).doc, sort_keys=True)
    assert one == two


def test_fusion_preserves_lineage_credit_and_rollback():
    fusion = forge.fuse(_rich_workflow("wf.a"), _rich_workflow("wf.b"))
    lin = fusion.doc["lineage"]
    assert {d["source"] for d in lin["derived_from"]} == {"wf.a", "wf.b"}
    assert all(d["relation"] == "MERGE" for d in lin["derived_from"])
    assert all(d.get("credit") for d in lin["derived_from"])
    assert lin["decomposable_back_to_sources"] is True
    assert len(lin["rollback_to"]) == 2


def test_tool_policy_is_merged_not_replaced():
    """Regression: the donor's policy used to REPLACE the base's, orphaning the base's tools."""
    a = _rich_workflow("wf.a")
    a["tool_policy"]["allow"] = ["Read", "OnlyInA"]
    b = _rich_workflow("wf.b")
    b["tool_policy"]["allow"] = ["Read", "OnlyInB"]
    b["tool_policy"]["require_owner_approval"] = ["Bash"]
    fusion = forge.fuse(a, b)
    allow = set(fusion.doc["tool_policy"]["allow"])
    assert {"OnlyInA", "OnlyInB"} <= allow


def test_tool_policy_takes_the_stricter_scalar():
    a = _rich_workflow("wf.a")
    a["tool_policy"].update({"default": "allow", "network": "full"})
    b = _rich_workflow("wf.b")
    b["tool_policy"].update({"default": "deny", "network": "none"})
    fusion = forge.fuse(a, b)
    assert fusion.doc["tool_policy"]["default"] == "deny"
    assert fusion.doc["tool_policy"]["network"] == "none"


def test_a_denied_tool_conflict_is_reported_not_silently_dropped():
    a = _rich_workflow("wf.a")
    a["tool_policy"]["deny"] = ["WebFetch"]
    b = _rich_workflow("wf.b")
    b["tool_policy"]["allow"] = ["Read", "Write", "WebFetch"]
    fusion = forge.fuse(a, b)
    conflicts = [c for c in fusion.conflicts if c["namespace"] == "tool_policy"]
    assert conflicts and conflicts[0]["id"] == "WebFetch"
    assert "WebFetch" in fusion.doc["tool_policy"]["deny"], (
        "the stricter posture must survive"
    )


def test_role_and_gate_collisions_are_renamed_and_recorded():
    a = _rich_workflow("wf.a")
    b = _rich_workflow("wf.b")
    b["roles"]["worker"] = {
        "description": "a DIFFERENT worker",
        "tool_permissions": ["Read"],
    }
    fusion = forge.fuse(a, b)
    assert any(
        c["namespace"] == "roles" and c["id"] == "worker" for c in fusion.conflicts
    )
    assert "d1.worker" in fusion.doc["roles"]


def test_artifact_path_collisions_are_rewritten():
    a = _rich_workflow("wf.a")
    b = _minimal_workflow("wf.b")
    b["stages"] = [
        {
            "id": "writer",
            "kind": "barrier",
            "title": "writes the same path",
            "barrier": {"mode": "all", "on_partial": "fail"},
            "produces": [
                {
                    "path": "command-center/out/rich.json",
                    "schema_ref": "platform/schema/receipt.schema.json",
                    "min_bytes": 1,
                    "consumers": ["x"],
                }
            ],
        }
    ]
    # `union` is used deliberately: best-of-breed would not graft this stage at all (the base
    # already has `barriers`), so the collision could never arise and the test would pass
    # vacuously - a test that cannot fail is not a test.
    fusion = forge.fuse(a, b, strategy="union")
    assert fusion.decomposition["artifact_path_rewrites"]
    paths = [
        p["path"]
        for _, st in mechanisms.iter_stages(fusion.doc)
        for p in (st.get("produces") or [])
    ]
    assert len(paths) == len(set(paths)), (
        "two stages must not write the same artifact path"
    )


def test_fusion_does_not_invent_ordering_edges():
    """Regression: donated stages used to be chained, adding edges the donor never had."""
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    fusion = forge.fuse(a, b)
    dec = forge.decompose(fusion.doc, {"wf.a": a, "wf.b": b})
    for src, check in dec["roundtrip"]["per_source"].items():
        assert check["undisclosed_edges"] == [], f"{src} gained an undisclosed edge"


def test_union_grafts_more_stages_than_best_of_breed():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    u = forge.fuse(a, b, strategy="union")
    bob = forge.fuse(a, b, strategy="best-of-breed")
    assert len(u.doc["stages"]) > len(bob.doc["stages"])


def test_decompose_refutes_a_document_with_no_lineage_record():
    res = forge.decompose(_rich_workflow())
    assert res["verdict"] == "REFUTED" and res["ok"] is False
    assert "decomposition" in res["reason"]


def test_decompose_is_not_checked_without_the_original_sources():
    fusion = forge.fuse(_rich_workflow("wf.a"), _rich_workflow("wf.b"))
    res = forge.decompose(fusion.doc)
    assert res["roundtrip"]["verdict"] == "NOT-CHECKED"
    assert res["verdict"] == "PARTIAL"


def test_decompose_confirms_against_the_real_sources():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    fusion = forge.fuse(a, b)
    res = forge.decompose(fusion.doc, {"wf.a": a, "wf.b": b})
    assert res["roundtrip"]["verdict"] == "CONFIRMED"
    assert res["unattributed_stages"] == []
    assert set(res["per_source"]) == {"wf.a", "wf.b"}


def test_decompose_refutes_when_a_stage_loses_its_attribution():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    fusion = forge.fuse(a, b)
    doc = copy.deepcopy(fusion.doc)
    doc["x_extensions"]["foundry"]["decomposition"]["stage_origin"].pop("check")
    res = forge.decompose(doc, {"wf.a": a, "wf.b": b})
    assert res["verdict"] == "REFUTED" and "check" in res["unattributed_stages"]


def test_decompose_recovers_the_original_stage_ids():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    # the base must LACK the capability the donor stage carries, or best-of-breed correctly
    # declines to graft it and this test would assert on an empty donation
    a["stages"] = [s for s in a["stages"] if s["id"] != "call-child"]
    a.pop("subworkflows")
    b["stages"] = [
        {
            "id": "unique-donor-stage",
            "kind": "subworkflow",
            "title": "t",
            "workflow": {"workflow_id": "child"},
        }
    ]
    fusion = forge.fuse(a, b)
    res = forge.decompose(fusion.doc, {"wf.a": a, "wf.b": b})
    donor = res["per_source"]["wf.b"]
    assert donor["original_stage_ids"] == ["unique-donor-stage"]
    assert donor["fused_stage_ids"] == ["d1.unique-donor-stage"]
    assert "subworkflows" in donor["contributed_capabilities"]


def test_fuse_and_certify_returns_a_terminal_verdict():
    out = forge.fuse_and_certify(_rich_workflow("wf.a"), _rich_workflow("wf.b"))
    assert out["certification"]["verdict"] in ("CERTIFIED", "REJECTED")
    assert out["doc"]["x_extensions"]["foundry"]["certification"][
        "stage_count_is_not_an_axis"
    ]


def test_forge_cli_strategies_lists_every_strategy(capsys):
    assert forge.main(["strategies"]) == 0
    out = capsys.readouterr().out
    for s in FUSION_STRATEGIES:
        assert s in out


def test_forge_cli_requires_exactly_two_sources(capsys):
    assert forge.main(["fuse", "--source", "only-one.json"]) == 2
    assert "FAILED:forge-fuse" in capsys.readouterr().err


# --------------------------------------------------- integration on real inputs


def test_scout_finds_and_verifies_the_real_registry():
    cands = registry.load_all()
    assert len(cands) >= 100
    goal = Goal(
        text="fan out build units and fan back in without losing a straggler",
        required_capabilities=["dynamic_fanout", "barriers", "failure_policy"],
        hazards=["straggler-work-silently-dropped"],
    )
    report = scout.scout_report(goal, cands, top=5)
    assert report["search"]["hits"]
    assert report["recommendation"]["primary"]
    top = report["search"]["hits"][0]
    assert top["derivation"] == mechanisms.STRUCTURAL
    assert top["capability_fit"] > 0


def test_forge_fuses_two_real_blueprints_and_the_result_is_legal(real_blueprints):
    a, b = real_blueprints[0].dsl_doc, real_blueprints[1].dsl_doc
    out = forge.fuse_and_certify(a, b)
    cert = out["certification"]
    assert cert["verdict"] in ("CERTIFIED", "REJECTED")
    # whatever the verdict, the decomposition must be structurally complete
    assert out["decomposition"]["unattributed_stages"] == []
    if cert["accepted"]:
        assert (
            cert["fused"]["schema_valid"] and cert["fused"]["semantic_violations"] == 0
        )
        assert out["decomposition"]["roundtrip"]["verdict"] == "CONFIRMED"


def test_the_certified_and_rejected_artifacts_on_disk_match_their_verdicts():
    """The shipped evidence must still say what the report says it says."""
    forged = REPO_ROOT / "platform" / "workflows" / "forged"
    if not forged.is_dir():
        pytest.skip("no forged artifacts on disk")
        return
    for report_path in sorted(forged.glob("*REPORT.json")):
        rep = json.loads(report_path.read_text(encoding="utf-8"))
        verdict = rep["certification"]["verdict"]
        assert verdict in ("CERTIFIED", "REJECTED")
        if report_path.name.startswith("REJECTED."):
            assert verdict == "REJECTED", (
                f"{report_path.name} claims REJECTED but is {verdict}"
            )
        else:
            assert verdict == "CERTIFIED", (
                f"{report_path.name} claims CERTIFIED but is {verdict}"
            )


def test_the_shipped_certified_workflow_still_validates():
    p = (
        REPO_ROOT
        / "platform"
        / "workflows"
        / "forged"
        / "fused.cnc07-arc05.workflow.json"
    )
    if not p.exists():
        pytest.skip("the certified example has not been emitted")
        return
    doc = json.loads(p.read_text(encoding="utf-8"))
    valid, violations, errors = bench._run_dsl_gate(doc)
    assert valid, errors
    assert violations == 0
    assert doc["lineage"]["decomposable_back_to_sources"] is True
    assert doc["x_extensions"]["foundry"]["certification"]["verdict"] == "CERTIFIED"


def test_tournament_prefers_the_cheapest_certified_entrant():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    b["stages"] = [
        {
            "id": "donor-sub",
            "kind": "subworkflow",
            "title": "t",
            "workflow": {"workflow_id": "child"},
        },
        {
            "id": "donor-spare",
            "kind": "task",
            "title": "spare",
            "role": "worker",
            "work_unit_ref": "AAA-0005",
        },
    ]
    b["subworkflows"] = {"child": {"workflow_id": "child", "version_range": ">=1.0.0"}}
    res = forge.tournament(a, b, cases=list(bench.DEFAULT_CASES))
    assert len(res["entrants"]) == len(FUSION_STRATEGIES)
    if res["winner"]:
        cheapest = min(
            r["stage_count"] for r in res["entrants"] if r["verdict"] == "CERTIFIED"
        )
        assert res["winner"]["stage_count"] == cheapest
        assert res["winner"]["gratuitous_stages"] == []


# ------------------------------------------------- D4: forged id collision (regression)
#
# Measured defect D4: `fused.dc5b5f0b10f7` was carried by THREE documents under
# platform/workflows/ - the CERTIFIED 9-stage best-of-breed fusion, a byte-identical
# duplicate of it, and the REJECTED 18-stage `union` of the same pair. A loader keyed on
# workflow id could therefore execute the rejected 18-stage union in place of the certified
# 9-stage fusion. Root cause: `_fused_id` derived the id from the source pair ALONE - not the
# strategy, not the resulting content, not the certification verdict.


WORKFLOWS_DIR = REPO_ROOT / "platform" / "workflows"


def _canonical_digest(doc: dict) -> str:
    """Digest of the PARSED document, canonicalised.

    Deliberately NOT a hash of the file bytes: git stores LF and Windows checks out CRLF, so a
    byte hash of a working-tree file is platform-dependent. Parsing first makes the digest
    depend on content alone.
    """
    return hashlib.sha256(
        json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _is_workflow_doc(doc: object) -> bool:
    return (
        isinstance(doc, dict)
        and isinstance(doc.get("id"), str)
        and bool(doc["id"])
        and "dsl_version" in doc
        and "stages" in doc
    )


def _verdict_of(doc: dict) -> str | None:
    foundry = (doc.get("x_extensions") or {}).get("foundry")
    if not isinstance(foundry, dict):
        return None
    cert = foundry.get("certification")
    return cert.get("verdict") if isinstance(cert, dict) else None


def _scan_workflow_ids(root: Path) -> dict:
    """Scan every *.json under `root` RECURSIVELY and report id-identity violations.

    Scope note: `rglob`, not a depth-1 walk. The D4 documents live in a `forged/`
    subdirectory, and a depth-1 scan reports a clean tree while the collision is live.
    """
    by_id: dict[str, dict[str, list[str]]] = {}
    verdicts: dict[str, set[str | None]] = {}
    docs = 0
    for path in sorted(root.rglob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return {"unparsable": f"{path}: {exc}"}
        if not _is_workflow_doc(doc):
            continue
        docs += 1
        rel = path.relative_to(root).as_posix()
        wid = str(doc["id"])
        by_id.setdefault(wid, {}).setdefault(_canonical_digest(doc), []).append(rel)
        verdicts.setdefault(wid, set()).add(_verdict_of(doc))

    return {
        "workflow_documents": docs,
        "distinct_ids": len(by_id),
        # (1) one id must never resolve to two DIFFERENT documents.
        "divergent_ids": {
            wid: groups for wid, groups in by_id.items() if len(groups) > 1
        },
        # (2) an id must never be shared by a CERTIFIED and a REJECTED document.
        "mixed_verdict_ids": {
            wid: sorted(v for v in vs if v)
            for wid, vs in verdicts.items()
            if "REJECTED" in vs and "CERTIFIED" in vs
        },
        # (3) a REJECTED document must be namespaced so it cannot be mistaken for certified.
        "unmarked_rejected_ids": sorted(
            wid
            for wid, vs in verdicts.items()
            if "REJECTED" in vs and not wid.startswith(f"{forge._REJECTED_ID_PREFIX}.")
        ),
        "unparsable": None,
    }


def test_no_workflow_id_resolves_to_two_different_documents():
    """The D4 gate, over the whole shipped corpus under platform/workflows/."""
    if not WORKFLOWS_DIR.is_dir():
        pytest.skip("platform/workflows is not present")
        return
    report = _scan_workflow_ids(WORKFLOWS_DIR)
    assert report["unparsable"] is None, report["unparsable"]
    # Fail closed: an empty walk means the detector checked nothing, which is a detector
    # failure, never a pass.
    assert report["workflow_documents"] > 0, "scanned no workflow documents"
    assert report["divergent_ids"] == {}, (
        "one workflow id resolves to two DIFFERENT documents, so a loader keyed on id cannot "
        f"tell them apart: {report['divergent_ids']}"
    )
    assert report["mixed_verdict_ids"] == {}, (
        f"an id is shared by a CERTIFIED and a REJECTED document: {report['mixed_verdict_ids']}"
    )
    assert report["unmarked_rejected_ids"] == [], (
        f"a REJECTED document carries an unnamespaced id: {report['unmarked_rejected_ids']}"
    )


def test_the_id_collision_gate_fires_on_a_seeded_collision(tmp_path):
    """Both-states control for the gate above.

    Without this, a green from `test_no_workflow_id_resolves_to_two_different_documents` is
    unfalsifiable: a scanner that silently matched nothing would also report clean.
    """
    good = _minimal_workflow("wf.alpha")
    (tmp_path / "a.json").write_text(json.dumps(good), encoding="utf-8")
    (tmp_path / "b.json").write_text(
        json.dumps(_minimal_workflow("wf.beta")), encoding="utf-8"
    )
    clean = _scan_workflow_ids(tmp_path)
    assert clean["workflow_documents"] == 2
    assert clean["divergent_ids"] == {}, "control tree must be clean BEFORE seeding"

    # Seed the exact D4 shape: same id, DIFFERENT content, in a subdirectory so the scan's
    # recursion is exercised too.
    (tmp_path / "forged").mkdir()
    collider = _minimal_workflow("wf.alpha")
    collider["stages"] = [
        *collider["stages"],
        {"id": "extra", "kind": "task", "work_unit_ref": "AAA-0002"},
    ]
    assert _canonical_digest(collider) != _canonical_digest(good)
    (tmp_path / "forged" / "collider.json").write_text(
        json.dumps(collider), encoding="utf-8"
    )
    seeded = _scan_workflow_ids(tmp_path)
    assert seeded["workflow_documents"] == 3
    assert "wf.alpha" in seeded["divergent_ids"], (
        "the gate did NOT fire on a seeded id collision, so it measures nothing"
    )
    assert len(seeded["divergent_ids"]["wf.alpha"]) == 2


def test_a_seeded_rejected_certified_id_clash_is_caught(tmp_path):
    """Second both-states control, for the verdict half of the gate."""
    certified = _minimal_workflow("wf.same")
    certified["x_extensions"] = {"foundry": {"certification": {"verdict": "CERTIFIED"}}}
    rejected = _minimal_workflow("wf.same")
    rejected["x_extensions"] = {"foundry": {"certification": {"verdict": "REJECTED"}}}
    (tmp_path / "c.json").write_text(json.dumps(certified), encoding="utf-8")
    (tmp_path / "r.json").write_text(json.dumps(rejected), encoding="utf-8")
    report = _scan_workflow_ids(tmp_path)
    assert report["mixed_verdict_ids"] == {"wf.same": ["CERTIFIED", "REJECTED"]}
    assert report["unmarked_rejected_ids"] == ["wf.same"]


def test_fused_id_separates_strategies_for_the_same_pair():
    """The direct D4 root cause: `union` and `best-of-breed` of ONE pair are two documents."""
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    ids = {
        strat: forge.fuse(a, b, strategy=strat, cases=list(bench.DEFAULT_CASES)).doc[
            "id"
        ]
        for strat in FUSION_STRATEGIES
    }
    assert len(set(ids.values())) == len(ids), f"two strategies produced one id: {ids}"


def test_fused_id_is_content_addressed_in_both_directions():
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    cases = list(bench.DEFAULT_CASES)
    first = forge.fuse(a, b, cases=cases).doc
    again = forge.fuse(a, b, cases=cases).doc
    # same content -> same id (`fuse` is pure; re-running must not churn identity)
    assert first["id"] == again["id"]
    assert forge.fusion_payload_digest(first) == forge.fusion_payload_digest(again)
    # different content -> different id
    mutated = copy.deepcopy(a)
    mutated["stages"] = [
        *mutated["stages"],
        {
            "id": "novel",
            "kind": "task",
            "title": "a stage that did not exist before",
            "role": "worker",
            "work_unit_ref": "AAA-0009",
        },
    ]
    changed = forge.fuse(mutated, b, cases=cases).doc
    assert changed["id"] != first["id"], "a content change did not change the id"


def test_a_rejected_fusion_can_never_carry_a_certified_id():
    """The D4 hazard, reproduced end-to-end through the real certifier."""
    a, b = _rich_workflow("wf.a"), _rich_workflow("wf.b")
    cases = list(bench.DEFAULT_CASES)
    seen: dict[str, str] = {}
    verdicts_seen: set[str] = set()
    for strat in FUSION_STRATEGIES:
        out = forge.fuse_and_certify(a, b, strategy=strat, cases=cases)
        wid, verdict = out["doc"]["id"], out["certification"]["verdict"]
        verdicts_seen.add(verdict)
        if verdict == "REJECTED":
            assert wid.startswith(f"{forge._REJECTED_ID_PREFIX}."), (
                f"{strat} was REJECTED but its id is not namespaced: {wid}"
            )
        else:
            assert not wid.startswith(f"{forge._REJECTED_ID_PREFIX}."), wid
        assert seen.get(wid, verdict) == verdict, (
            f"id {wid} carries both {seen.get(wid)} and {verdict}"
        )
        seen[wid] = verdict
        assert out["fused_id"] == wid, (
            "the report fused_id drifted from the document id"
        )
    # Guard the guard: if no strategy is ever REJECTED here, the namespacing branch above was
    # never exercised and this test would pass without measuring the hazard.
    assert "REJECTED" in verdicts_seen, (
        "no strategy was REJECTED, so the branch is untested"
    )


def test_every_fused_id_stays_within_the_schema_slug_cap():
    """`$defs/slug` caps `id` at 80 chars; the digest suffix must not push it over."""
    long_a = _rich_workflow("wf." + "a" * 70)
    long_b = _rich_workflow("wf." + "b" * 70)
    for strat in FUSION_STRATEGIES:
        doc = forge.fuse(
            long_a, long_b, strategy=strat, cases=list(bench.DEFAULT_CASES)
        ).doc
        assert len(doc["id"]) <= 80, (
            f"{strat}: id is {len(doc['id'])} chars: {doc['id']}"
        )
        assert forge._SLUG.match(doc["id"]), doc["id"]


def test_forged_documents_on_disk_carry_a_recomputable_id():
    """A stamped id is a claim; recomputing it from the document is the check."""
    forged = WORKFLOWS_DIR / "forged"
    if not forged.is_dir():
        pytest.skip("no forged artifacts emitted")
        return
    checked = 0
    for path in sorted(forged.glob("*.workflow.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        expected = forge.expected_fused_id(doc)
        if expected is None:
            continue
        checked += 1
        assert doc["id"] == expected, (
            f"{path.name}: id {doc['id']!r} does not match the id recomputed from its own "
            f"content, {expected!r}"
        )
    assert checked > 0, "no forged document was actually checked"
