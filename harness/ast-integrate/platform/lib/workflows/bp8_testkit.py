"""Test support for blueprint range bp-8 (slots 85-96 of the 96 built-ins).

WHY THIS MODULE IMPORTS ``bp4_testkit`` INSTEAD OF RE-IMPLEMENTING IT
--------------------------------------------------------------------
The generic half of a blueprint testkit - load a document, ask ``wfdsl.schemas`` for its errors,
walk the stage tree depth-first, build a targeted mutant, fingerprint a document's MECHANISM as a
token set - is not bp-4-specific, and a second hand-written copy is exactly the "renamed copy"
defect this program is measuring in the blueprints themselves. So this module DELEGATES those to
``bp4_testkit`` and adds only what is bp-8's own: the slot->card->id->flagship table, accessors
for the ``x_extensions`` blocks the bp-8 documents carry (mechanism / benchmark_cases /
worked_examples / not_a_duplicate_because / unverified), and a fan-out accessor.

The coupling is deliberate and LOUD, not silent: ``test_bp8_testkit_dependency`` asserts every
delegated symbol is present and callable, so if a sibling reshapes ``bp4_testkit`` this suite
fails with a named reason instead of quietly measuring nothing. There is deliberately NO
try/except fallback - a fallback implementation that behaves slightly differently is the
both-states hazard (a probe that passes in both states) this program exists to avoid.
"""

from __future__ import annotations

from typing import Any, Mapping

import bp4_testkit as _K

# --------------------------------------------------------------- delegated generic helpers
REPO_ROOT = _K.REPO_ROOT
WORKFLOW_DIR = _K.WORKFLOW_DIR
CATALOG_PATH = _K.CATALOG_PATH
SPEC_CATEGORIES = _K.SPEC_CATEGORIES

path_for = _K.path_for
load = _K.load
catalog_ids = _K.catalog_ids
schema_errors = _K.schema_errors
semantic_violations = _K.semantic_violations
semantic_advisories = _K.semantic_advisories
stages = _K.stages
stage = _K.stage
stage_ids = _K.stage_ids
top_level_stage_ids = _K.top_level_stage_ids
assert_precedes = _K.assert_precedes
gate = _K.gate
inline_work_units = _K.inline_work_units
schema_references = _K.schema_references
resolve_schema_reference = _K.resolve_schema_reference
mechanism_tokens = _K.mechanism_tokens
jaccard = _K.jaccard
pairwise_similarity = _K.pairwise_similarity
mutant = _K.mutant
find_stage_mut = _K.find_stage_mut
raises_assertion = _K.raises_assertion

#: Every generic symbol this module leans on. ``test_bp8_testkit_dependency`` walks it.
DELEGATED = (
    "path_for",
    "load",
    "schema_errors",
    "semantic_violations",
    "stages",
    "stage",
    "stage_ids",
    "top_level_stage_ids",
    "assert_precedes",
    "gate",
    "inline_work_units",
    "schema_references",
    "resolve_schema_reference",
    "mechanism_tokens",
    "jaccard",
    "pairwise_similarity",
    "mutant",
    "find_stage_mut",
    "raises_assertion",
)

# ------------------------------------------------------------------------------ the range

#: (slot over the 96 built-ins, source design card, workflow id, flagship)
BP8_RANGE: tuple[tuple[int, str, str, bool], ...] = (
    (85, "BP-DOC-04", "shared-grounding-pack-emission", False),
    (86, "BP-DOC-05", "memory-temporal-validity-curation", False),
    (87, "BP-REL-01", "pr-shepherd-to-merge", True),
    (88, "BP-REL-02", "pre-pr-surface-check", True),
    (89, "BP-REL-03", "anchor-checked-per-file-deploy", True),
    (90, "BP-REL-04", "marketplace-publication-governance", False),
    (91, "BP-REL-05", "dual-tree-plumbing-mirror", False),
    (92, "BP-MNT-01", "live-to-repo-drift-reconcile", True),
    (93, "BP-MNT-02", "firing-path-revalidation", True),
    (94, "BP-MNT-03", "detector-truncation-audit", True),
    (95, "BP-MNT-04", "scheduled-task-liveness-census", True),
    (96, "BP-MNT-05", "skill-plugin-portfolio-stocktake", False),
)

#: The six domains the spec requires the 96 to span, and the ALTERNATE slug each is written with
#: somewhere in this corpus. MEASURED 2026-08-10 over all 97 DSL documents: two of the six domains
#: carry two spellings - `data-science-knowledge-and-creative` (12 docs) vs
#: `...-creative-work` (5), and `collective-intelligence-and-meta` (17) vs `...-meta-workflows` (9).
#: `workflow-dsl.schema.json` types `categories` as a bare slug array with no enum, so nothing
#: rejects either form, and the two sibling testkits DISAGREE about which is canonical:
#: `bp2_common.SPEC_CATEGORIES` pins the `-work`/`-workflows` pair while
#: `bp4_testkit.SPEC_CATEGORIES` pins the short pair, and each unit's tests assert its own.
#: This unit deliberately does NOT pick a winner - that is an orchestrator decision, and
#: unilaterally rewriting 2 of the 13 drifted documents would leave two spellings in place while
#: manufacturing the appearance of consistency. Instead the drift is normalised HERE, so a
#: span-of-six claim cannot false-negative on a spelling.
CATEGORY_ALIASES: dict[str, str] = {
    "data-science-knowledge-and-creative-work": "data-science-knowledge-and-creative",
    "collective-intelligence-and-meta-workflows": "collective-intelligence-and-meta",
}


def canonical_categories(doc: Mapping[str, Any]) -> set[str]:
    """A document's categories with the measured spelling drift folded onto the six domains."""
    return {CATEGORY_ALIASES.get(c, c) for c in (doc.get("categories") or [])}


BP8_IDS: tuple[str, ...] = tuple(row[2] for row in BP8_RANGE)
BP8_FLAGSHIP: tuple[str, ...] = tuple(row[2] for row in BP8_RANGE if row[3])
BP8_SLOTS: tuple[int, ...] = tuple(row[0] for row in BP8_RANGE)


def load_all() -> dict[str, dict[str, Any]]:
    return {wid: load(wid) for wid in BP8_IDS}


# ---------------------------------------------------------------- bp-8 document accessors


def blueprint_meta(doc: Mapping[str, Any]) -> Mapping[str, Any]:
    meta = ((doc.get("x_extensions") or {}).get("blueprint")) or {}
    assert meta, f"{doc.get('id')!r} carries no x_extensions.blueprint block"
    return meta


def ext(doc: Mapping[str, Any], key: str) -> Any:
    """One ``x_extensions`` block, asserted present - an absent block is a defect, not None."""
    blocks = doc.get("x_extensions") or {}
    assert key in blocks, (
        f"{doc.get('id')!r} has no x_extensions.{key}; have {sorted(blocks)}"
    )
    return blocks[key]


def worked_examples(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    examples = ext(doc, "worked_examples")
    assert isinstance(examples, list) and examples, (
        "at least one worked example is required"
    )
    return examples


def benchmark_cases(doc: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cases = ext(doc, "benchmark_cases")
    assert isinstance(cases, list) and cases, "at least one benchmark case is required"
    return cases


def fanout(doc: Mapping[str, Any], stage_id: str) -> Mapping[str, Any]:
    st = stage(doc, stage_id)
    assert st.get("kind") == "fanout", (
        f"{stage_id!r} is kind={st.get('kind')!r}, not a fanout"
    )
    return st


def barrier(doc: Mapping[str, Any], stage_id: str) -> Mapping[str, Any]:
    spec = fanout(doc, stage_id).get("barrier")
    assert isinstance(spec, Mapping), f"fan-out {stage_id!r} declares no barrier"
    return spec


def depends_on(doc: Mapping[str, Any], stage_id: str) -> list[str]:
    return list(stage(doc, stage_id).get("depends_on") or [])


def gate_for_stage(doc: Mapping[str, Any], stage_id: str) -> Mapping[str, Any]:
    """Resolve a ``kind: gate`` stage to the gate it enforces.

    A gate stage carries either an inline ``gate`` object or a ``gate_ref`` naming an entry in the
    document's ``gates`` map. Resolving through the STAGE rather than reading ``gates[name]``
    directly is what makes the check load-bearing: a gate declared in the map but never wired to a
    stage blocks nothing, and reading the map alone cannot tell the two apart.
    """
    st = stage(doc, stage_id)
    assert st.get("kind") == "gate", (
        f"{stage_id!r} is kind={st.get('kind')!r}, not a gate"
    )
    inline = st.get("gate")
    if isinstance(inline, Mapping):
        return inline
    ref = st.get("gate_ref")
    assert isinstance(ref, str) and ref, (
        f"gate stage {stage_id!r} has neither gate nor gate_ref"
    )
    return gate(doc, ref)


def stopping_rule(doc: Mapping[str, Any], rule_id: str) -> Mapping[str, Any]:
    for rule in doc.get("stopping_rules") or []:
        if isinstance(rule, Mapping) and rule.get("id") == rule_id:
            return rule
    have = [
        r.get("id") for r in (doc.get("stopping_rules") or []) if isinstance(r, Mapping)
    ]
    raise AssertionError(
        f"stopping rule {rule_id!r} not declared in {doc.get('id')!r}; have {have}"
    )


def routes_for(doc: Mapping[str, Any], when_substring: str) -> list[Mapping[str, Any]]:
    routing = doc.get("model_routing") or {}
    return [
        r for r in (routing.get("routes") or []) if when_substring in str(r.get("when"))
    ]


def assert_rejects_fire_and_forget(spec: Mapping[str, Any]) -> None:
    """A barrier must reject the two receipt strings that measured as a total work loss.

    cross-vendor-dispatch rule 1 / fan-out-contract B2: a digest saying "started in the
    background" or "Check /codex:status" is a RECEIPT, never a result, and accepting one is how a
    completed job's finding gets discarded unread.
    """
    patterns = [str(p) for p in (spec.get("reject_result_matching") or [])]
    for needle in ("started in the background", "Check /codex:status"):
        assert any(needle in p for p in patterns), f"barrier does not reject {needle!r}"
    assert spec.get("verify_artifact_exists") is True, (
        "a barrier must Test-Path the contracted artifact; a digest is a claim, not a receipt"
    )
