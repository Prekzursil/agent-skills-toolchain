"""Range-wide conformance and DISTINCTNESS suite for bp-8 (slots 85-96 of the 96 built-ins).

This module is the mechanical half of the unit: everything here is an exact algorithm over the
twelve documents - set membership, pairwise Jaccard over mechanism token sets, file existence,
table-vs-disk equality - because a mechanical comparison handed to judgement measured 86% accurate
with 100% of its errors pointing the unsafe way. The per-blueprint FLAGSHIP suites
(``test_<id>.py``) carry the judgement-shaped assertions about each mechanism.

The distinctness check ships with its own both-states control: a synthetic pair built by copying
one document must score above the threshold, proving the screen can see a renamed copy at all.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import bp8_testkit as K
import pytest

DOCS: dict[str, dict[str, Any]] = K.load_all()
HERE = Path(__file__).resolve().parent

#: pairs at or above this mechanism-token similarity are near-duplicates and must be merged
NEAR_DUPLICATE_THRESHOLD = 0.72

#: the spec's flagship floor: >= 40 of the 96 built-ins carry full end-to-end tests
SPEC_FLAGSHIP_NUMERATOR = 40
SPEC_FLAGSHIP_DENOMINATOR = 96


# ------------------------------------------------------------------- the testkit dependency


def test_bp8_testkit_dependency_is_present_and_shaped() -> None:
    """A LOUD check on the delegated helpers, so a reshaped sibling module cannot go unnoticed."""
    for name in K.DELEGATED:
        fn = getattr(K, name, None)
        assert callable(fn), f"delegated helper {name!r} is missing or not callable"


def test_the_mutation_kit_actually_detects_a_change() -> None:
    """Control on the control: ``mutant`` must produce a different document, and not in place."""
    doc = DOCS["detector-truncation-audit"]
    before = json.dumps(doc, sort_keys=True)
    broken = K.mutant(doc, lambda d: d["gates"].pop("population-defined"))
    assert "population-defined" not in broken["gates"]
    assert json.dumps(doc, sort_keys=True) == before, (
        "mutant() mutated the shipped document"
    )
    assert K.raises_assertion(lambda d: K.gate(d, "population-defined"), broken)
    assert not K.raises_assertion(lambda d: K.gate(d, "population-defined"), doc), (
        "the helper must be SILENT on the healthy document, or it measures nothing"
    )


# ------------------------------------------------------------------ table versus what is on disk


@pytest.mark.parametrize(
    "slot,card,wid,flagship", K.BP8_RANGE, ids=[r[2] for r in K.BP8_RANGE]
)
def test_the_range_table_matches_the_document_on_disk(
    slot: int, card: str, wid: str, flagship: bool
) -> None:
    doc = DOCS[wid]
    meta = K.blueprint_meta(doc)
    assert doc["id"] == wid
    assert meta["slot"] == slot
    assert meta["of"] == SPEC_FLAGSHIP_DENOMINATOR
    assert meta["design_card"] == card, (
        "a blueprint must name the design card it was built from"
    )
    assert doc.get("flagship") is flagship
    assert meta.get("flagship") is flagship, (
        "the two flagship declarations must agree, or one of them is decoration"
    )


def test_the_twelve_slots_are_exactly_85_to_96() -> None:
    assert sorted(K.BP8_SLOTS) == list(range(85, 97))
    assert len(set(K.BP8_IDS)) == 12, "two entries share a workflow id"


def test_no_other_document_claims_a_slot_in_this_range() -> None:
    """A slot collision would make two blueprints the same one of the 96."""
    claims: dict[int, list[str]] = {}
    for path in sorted(K.WORKFLOW_DIR.glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - non-DSL artifacts live here too
            continue
        if not isinstance(doc, dict) or "dsl_version" not in doc:
            continue
        slot = ((doc.get("x_extensions") or {}).get("blueprint") or {}).get("slot")
        if isinstance(slot, int) and 85 <= slot <= 96:
            claims.setdefault(slot, []).append(path.name)
    assert sorted(claims) == list(range(85, 97)), f"slots claimed: {sorted(claims)}"
    for slot, files in claims.items():
        assert len(files) == 1, f"slot {slot} is claimed by {files}"


# --------------------------------------------------------------------------- conformance


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_every_document_is_schema_valid_and_violation_free(wid: str) -> None:
    doc = DOCS[wid]
    assert K.schema_errors(doc) == []
    assert K.semantic_violations(doc) == []
    assert K.semantic_advisories(doc) == []


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_every_schema_reference_resolves_on_disk(wid: str) -> None:
    refs = K.schema_references(DOCS[wid])
    assert refs, "a blueprint that declares no typed output has no contract to hold it"
    unresolved = [
        r
        for r in refs
        if not r.startswith(("http://", "https://"))
        and K.resolve_schema_reference(r) is None
    ]
    assert unresolved == [], (
        f"{wid} names schema files that do not exist: {sorted(set(unresolved))}"
    )


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_no_gate_is_declared_but_never_enforced(wid: str) -> None:
    """An orphaned gate reads exactly like an enforced one and blocks nothing.

    Measured on this range: ``anchor-checked-per-file-deploy`` shipped ``anchor-present`` as
    ``blocking: true, on_fail: fail`` with no stage pointing at it, and both the schema layer and
    ``wfdsl.semantics`` reported it clean. This is the range-wide form of that check.
    """
    doc = DOCS[wid]
    enforced = {
        str(st.get("gate_ref"))
        for _, st in K.stages(doc)
        if st.get("kind") == "gate" and st.get("gate_ref")
    }
    declared = set(doc.get("gates") or {})
    assert declared - enforced == set(), (
        f"{wid}: unenforced gates {sorted(declared - enforced)}"
    )
    assert enforced - declared == set(), (
        f"{wid}: dangling gate_refs {sorted(enforced - declared)}"
    )


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_every_document_carries_the_required_authoring_blocks(wid: str) -> None:
    doc = DOCS[wid]
    for block in (
        "params",
        "roles",
        "tool_policy",
        "gates",
        "stages",
        "stopping_rules",
        "retry_policy",
        "failure_policy",
        "outputs",
    ):
        assert doc.get(block), f"{wid} is missing {block}"
    assert doc["tool_policy"]["default"] == "deny", (
        "an allow-by-default tool policy is not a policy"
    )
    assert doc["failure_policy"]["terminal_state_required"] is True
    assert doc["failure_policy"]["never_silent"] is True
    K.worked_examples(doc)
    K.benchmark_cases(doc)
    assert K.ext(doc, "mechanism"), (
        "a blueprint must state the mechanism it is not a copy of"
    )
    assert K.ext(doc, "not_a_duplicate_because"), (
        "distinctness must be argued per document"
    )
    assert K.ext(doc, "contraindications"), (
        "a blueprint that fits everything fits nothing"
    )


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_every_stopping_rule_has_a_terminal_disposition(wid: str) -> None:
    dispositions = {"complete", "escalate", "emit-partial", "abandon", "repair"}
    rules = DOCS[wid]["stopping_rules"]
    assert rules, f"{wid} declares no stopping rule"
    for rule in rules:
        assert rule["on_stop"] in dispositions, f"{wid}/{rule['id']}: {rule['on_stop']}"
    assert any(r["on_stop"] == "complete" for r in rules), (
        f"{wid} can never terminate successfully - every rule escalates or degrades"
    )


@pytest.mark.parametrize("wid", K.BP8_IDS)
def test_every_inline_work_unit_is_uniquely_identified(wid: str) -> None:
    units = K.inline_work_units(DOCS[wid])
    ids = [str(u["id"]) for u in units]
    assert ids, f"{wid} declares no inline work unit"
    assert len(set(ids)) == len(ids), f"{wid} reuses a work-unit id: {ids}"
    for unit in units:
        assert unit.get("output_schema"), (
            f"{wid}/{unit['id']} emits an untyped artifact"
        )
        assert unit.get("completion_sentinel", "").startswith("SUCCESS:"), (
            f"{wid}/{unit['id']} has no terminal-state sentinel"
        )
        assert unit["id"] in unit["completion_sentinel"], (
            f"{wid}/{unit['id']} sentinel does not name its own unit"
        )


def test_work_unit_ids_are_unique_across_the_whole_range() -> None:
    seen: dict[str, str] = {}
    for wid in K.BP8_IDS:
        for unit in K.inline_work_units(DOCS[wid]):
            uid = str(unit["id"])
            assert uid not in seen, f"{uid} declared in both {seen.get(uid)} and {wid}"
            seen[uid] = wid
    assert len(seen) >= 12, "fewer inline units than blueprints means one declares none"


# ----------------------------------------------------------------------------- distinctness


def test_no_pair_in_the_range_is_a_near_duplicate_by_mechanism() -> None:
    rows = K.pairwise_similarity(DOCS)
    assert len(rows) == 66, (
        f"expected 66 unordered pairs over 12 documents, got {len(rows)}"
    )
    offenders = [
        (round(s, 3), a, b) for s, a, b in rows if s >= NEAR_DUPLICATE_THRESHOLD
    ]
    assert offenders == [], (
        f"near-duplicate pairs at/above {NEAR_DUPLICATE_THRESHOLD}: {offenders}"
    )


def test_the_distinctness_screen_detects_a_planted_renamed_copy() -> None:
    """Both-states control on the screen itself: a copy under a new name must score at the ceiling."""
    original = DOCS["detector-truncation-audit"]
    renamed = json.loads(json.dumps(original))
    renamed["id"] = "detector-truncation-audit-copy"
    renamed["name"] = "A completely different sounding name"
    renamed["description"] = "Prose rewritten from scratch so no wording is shared."
    renamed["tags"] = ["totally", "different", "words"]
    score = K.jaccard(K.mechanism_tokens(original), K.mechanism_tokens(renamed))
    assert score == 1.0, (
        f"a mechanism-identical copy scored {score}; the screen is reading prose, not mechanism"
    )
    assert score >= NEAR_DUPLICATE_THRESHOLD


def test_the_distinctness_screen_is_not_saturated():
    """Negative half of the control: the real pairs must land well below the threshold."""
    rows = K.pairwise_similarity(DOCS)
    top = rows[0][0]
    assert top < NEAR_DUPLICATE_THRESHOLD
    assert top > 0.0, "an all-zero screen would pass vacuously and measure nothing"


def test_no_two_documents_share_a_gate_expression_set() -> None:
    """A distinct mechanism means distinct decision points, not just a distinct stage graph."""
    signatures: dict[frozenset[str], str] = {}
    for wid, doc in DOCS.items():
        sig = frozenset(str(g.get("expression")) for g in doc["gates"].values())
        assert sig not in signatures, (
            f"{wid} and {signatures[sig]} gate on identical expressions"
        )
        signatures[sig] = wid


# -------------------------------------------------------------------------------- coverage


def test_the_range_declares_categories_from_the_spec_six() -> None:
    covered: set[str] = set()
    for doc in DOCS.values():
        cats = K.canonical_categories(doc)
        assert cats, f"{doc['id']} declares no category"
        assert cats <= K.SPEC_CATEGORIES, (
            f"{doc['id']} claims {sorted(cats - K.SPEC_CATEGORIES)}"
        )
        covered |= cats
    # This range is deliberately reliability-heavy (BP-REL-*/BP-MNT-*), so it spans three of the
    # six domains, not all six. The 96-wide span is a corpus property, asserted by the corpus-wide
    # instrument, not by a 12-document slice - claiming six here would be a false coverage claim.
    assert covered == {
        "engineering-and-reliability",
        "security-governance-and-risk",
        "data-science-knowledge-and-creative",
    }, sorted(covered)


def test_the_flagship_share_meets_the_prorated_spec_floor() -> None:
    import math

    n = len(K.BP8_IDS)
    floor = math.ceil(n * SPEC_FLAGSHIP_NUMERATOR / SPEC_FLAGSHIP_DENOMINATOR)
    actual = len(K.BP8_FLAGSHIP)
    assert actual >= floor, (
        f"{actual} flagship of {n}; the {SPEC_FLAGSHIP_NUMERATOR}/"
        f"{SPEC_FLAGSHIP_DENOMINATOR} floor pro-rates to {floor}"
    )


def test_every_flagship_has_its_own_end_to_end_test_module() -> None:
    missing = [
        wid
        for wid in K.BP8_FLAGSHIP
        if not (HERE / f"test_{wid.replace('-', '_')}.py").is_file()
    ]
    assert missing == [], f"flagship blueprints with no test module: {missing}"


def test_no_non_flagship_is_quietly_claiming_a_flagship_suite() -> None:
    """A test module for a non-flagship is fine; a non-flagship marked flagship is not."""
    for slot, _card, wid, flagship in K.BP8_RANGE:
        doc = DOCS[wid]
        assert doc["flagship"] is flagship, f"slot {slot} ({wid}) flagship flag drifted"


def test_the_stage_kind_vocabulary_is_genuinely_exercised() -> None:
    kinds: set[str] = set()
    for doc in DOCS.values():
        kinds |= {str(st.get("kind")) for _, st in K.stages(doc)}
    for needed in (
        "task",
        "gate",
        "fanout",
        "human_checkpoint",
        "repair_loop",
        "loop",
        "subworkflow",
    ):
        assert needed in kinds, f"the range never uses stage kind {needed!r}"
