"""Set-level properties of the bp-3 range: validity, MECHANICAL distinctness, and honest counts.

The distinctness check is the important one. "No placeholders and no renamed copies" is not
assertable by reading prose, so it is computed: a fingerprint is built from each blueprint's
stage-kind multiset plus its gate expressions plus its stopping expressions. Two renamed copies
of one blueprint collide on that fingerprint; two genuinely different decision procedures do not.
"""

from __future__ import annotations

import json
from collections import Counter

import pytest

from bp3_testkit import (
    SHARED_DIR,
    WORKFLOW_DIR,
    assert_contract_valid,
    gate_expressions,
    stage_ids,
    stages,
    stopping_expressions,
    worked_example,
)

#: The twelve, in the design document's order (doc-order 25-36 of 96).
BP_IDS = [
    "bp-req-03.evpi-gated-clarification",
    "bp-req-04.assumption-ledger-elicitation",
    "bp-req-05.intent-to-prd-with-reviewer",
    "bp-arc-01.architecture-tournament",
    "bp-arc-02.architect-to-editor-split-build",
    "bp-arc-03.anti-overfit-architecture-audit",
    "bp-arc-04.failure-domain-mapping-workshop",
    "bp-arc-05.vendor-neutral-workflow-spec-emission",
    "bp-pln-01.mechanical-plan-lint-then-adversarial-trio",
    "bp-pln-02.file-disjoint-work-unit-decomposition",
    "bp-pln-03.multi-pr-stacking-order-planner",
    "bp-pln-04.resume-safe-program-checkpointing",
]

SHARED_IDS = ["shared.pairwise-overlap-matrix", "shared.write-as-you-go-artifact"]


def _docs():
    out = {}
    for bp in BP_IDS:
        out[bp] = json.loads((WORKFLOW_DIR / f"{bp}.workflow.json").read_text(encoding="utf-8"))
    return out


def test_all_twelve_blueprints_are_on_disk():
    """SCOPE: platform/workflows/ is SHARED with sibling blueprint ranges, so this asserts that
    this range's twelve are present - never that the directory contains only twelve. Asserting
    exclusivity of a shared directory would fail on a sibling's unrelated, correct work."""
    on_disk = {p.name for p in WORKFLOW_DIR.glob("*.json")}
    missing = [f"{b}.workflow.json" for b in BP_IDS if f"{b}.workflow.json" not in on_disk]
    assert missing == [], f"bp-3 blueprints absent from {WORKFLOW_DIR}: {missing}"
    assert len(BP_IDS) == 12


def test_no_bp3_id_collides_with_any_other_blueprint_in_the_shared_directory():
    """A duplicate workflow id across ranges would make two blueprints unaddressable."""
    ours = set(BP_IDS) | set(SHARED_IDS)
    theirs: dict[str, str] = {}
    for path in list(WORKFLOW_DIR.glob("*.json")) + list(SHARED_DIR.glob("*.json")):
        if path.name.endswith(".workflow.json") and path.stem.replace(".workflow", "") in ours:
            continue
        if path.name.endswith(".subworkflow.json") and path.stem.replace(".subworkflow", "") in ours:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if isinstance(doc, dict) and isinstance(doc.get("id"), str):
            theirs[doc["id"]] = path.name
    collisions = sorted(ours & set(theirs))
    assert collisions == [], f"id collision with a sibling range: {[(c, theirs[c]) for c in collisions]}"


def test_both_shared_subworkflows_are_on_disk():
    on_disk = {p.name for p in SHARED_DIR.glob("*.subworkflow.json")}
    missing = [f"{s}.subworkflow.json" for s in SHARED_IDS if f"{s}.subworkflow.json" not in on_disk]
    assert missing == [], f"shared subworkflows absent from {SHARED_DIR}: {missing}"


@pytest.mark.parametrize("bp_id", BP_IDS + SHARED_IDS)
def test_every_document_satisfies_both_contract_layers(bp_id):
    path = WORKFLOW_DIR / f"{bp_id}.workflow.json"
    if not path.is_file():
        path = SHARED_DIR / f"{bp_id}.subworkflow.json"
    assert_contract_valid(json.loads(path.read_text(encoding="utf-8")))


def _fingerprint(doc) -> tuple:
    """A mechanism fingerprint: stage-kind shape + gate predicates + stopping predicates."""
    kinds = tuple(sorted(Counter(str(s.get("kind")) for s in stages(doc)).items()))
    gates = tuple(sorted(gate_expressions(doc).values()))
    stops = tuple(sorted(json.dumps(e, sort_keys=True) for e in stopping_expressions(doc)))
    return (kinds, gates, stops)


def test_no_two_blueprints_share_a_mechanism_fingerprint():
    """The mechanical form of 'no renamed copies'."""
    seen: dict[tuple, str] = {}
    for bp, doc in _docs().items():
        fp = _fingerprint(doc)
        assert fp not in seen, f"{bp} is mechanically indistinguishable from {seen[fp]}"
        seen[fp] = bp
    assert len(seen) == 12


def test_the_fingerprint_detector_can_actually_collide():
    """Control: prove the distinctness check is not vacuous by feeding it two identical docs."""
    docs = _docs()
    one = docs["bp-pln-02.file-disjoint-work-unit-decomposition"]
    assert _fingerprint(one) == _fingerprint(json.loads(json.dumps(one)))


def test_the_two_overlap_matrix_callers_are_not_near_duplicates():
    """PLN-02 and PLN-03 share a PRIMITIVE by reference; their decision procedures differ."""
    docs = _docs()
    pln02 = docs["bp-pln-02.file-disjoint-work-unit-decomposition"]
    pln03 = docs["bp-pln-03.multi-pr-stacking-order-planner"]

    # both reference the SAME shared subworkflow rather than each carrying a copy
    for doc in (pln02, pln03):
        assert "shared.pairwise-overlap-matrix" in (doc.get("subworkflows") or {})
    # ...and their gates, stopping rules and stage sets are disjoint in substance
    assert set(gate_expressions(pln02).values()).isdisjoint(gate_expressions(pln03).values())
    assert set(stage_ids(pln02)) != set(stage_ids(pln03))
    assert _fingerprint(pln02) != _fingerprint(pln03)


def test_every_declared_distinguishing_mechanism_is_unique():
    claims = {}
    for bp, doc in _docs().items():
        claim = (doc.get("x_extensions") or {}).get("distinguishing_mechanism")
        assert claim, f"{bp} declares no distinguishing mechanism"
        assert claim not in claims, f"{bp} repeats {claims[claim]}'s distinctness claim verbatim"
        claims[claim] = bp


def test_every_blueprint_carries_the_seven_mandated_elements():
    """typed params, stages, roles, gates, tools, stopping rules, failure policy - plus an example."""
    for bp, doc in _docs().items():
        assert doc.get("params"), f"{bp}: no typed params"
        assert all("type" in spec for spec in doc["params"].values()), f"{bp}: an untyped param"
        assert doc.get("stages"), f"{bp}: no stages"
        assert doc.get("roles"), f"{bp}: no roles"
        assert doc.get("gates"), f"{bp}: no gates"
        assert doc.get("tool_policy", {}).get("allow"), f"{bp}: no tool allowlist"
        assert doc["tool_policy"].get("default") == "deny", f"{bp}: tool policy is not deny-by-default"
        assert doc.get("stopping_rules"), f"{bp}: no explicit stopping rule"
        assert doc.get("failure_policy", {}).get("on_failure"), f"{bp}: no failure policy"
        assert doc["failure_policy"]["terminal_state_required"] is True, f"{bp}: silence is permitted"
        assert doc.get("dry_run", {}).get("supported") is True, f"{bp}: not dry-runnable"
        worked_example(doc)  # raises with a precise message when absent or incomplete


def test_flagship_count_and_matching_test_files():
    docs = _docs()
    flagship = [bp for bp, doc in docs.items() if doc.get("flagship")]
    assert len(flagship) == 12, "every blueprint in this range is flagship"
    here = WORKFLOW_DIR.parents[0] / "lib" / "workflows"
    if not here.is_dir():  # running from the package dir itself
        here = (WORKFLOW_DIR.parents[1] / "platform" / "lib" / "workflows")
    for bp in flagship:
        slug = bp.split(".")[0].replace("-", "_")
        expected = here / f"test_{slug}.py"
        assert expected.is_file(), f"flagship {bp} has no end-to-end test at {expected}"


def test_category_span_is_reported_honestly_not_padded():
    """This range spans FOUR of the spec's six categories. Mislabelling to hit six would be
    manufactured coverage: doc-order 25-36 is exactly requirements + architecture + planning."""
    cats = set()
    for doc in _docs().values():
        assert doc.get("categories"), f"{doc.get('id')}: no category"
        cats.update(doc["categories"])
    assert cats == {
        "product-design-and-strategy",
        "security-governance-and-risk",
        "engineering-and-reliability",
        "collective-intelligence-and-meta",
    }
    assert "research-and-evidence" not in cats
    assert "data-science-knowledge-and-creative" not in cats


def test_no_blueprint_declares_a_measured_estimate_it_cannot_name():
    """basis=historical-measured requires naming the runs. No run of these exists, so none claims it."""
    for bp, doc in _docs().items():
        est = doc.get("estimate") or {}
        if est.get("basis") in ("historical-measured", "hybrid"):
            assert est.get("measurement_source"), f"{bp} claims measured data with no source"
        else:
            assert est.get("basis") == "static-declared", f"{bp}: unexpected estimate basis"


def test_secret_handling_and_export_redaction_hold_everywhere():
    for bp, doc in _docs().items():
        export = (doc.get("portability") or {}).get("export") or {}
        assert export.get("redact_secrets") is True, f"{bp}: export does not redact secrets"
        for name, spec in (doc.get("params") or {}).items():
            if spec.get("type") == "secret_ref":
                assert spec.get("secret") is True and "default" not in spec, f"{bp}.{name}"
