"""The four IMP-0236 research blueprints as typed workflow documents."""
from __future__ import annotations

from typing import Any

from contract import distinctness, validate_blueprint
from taxonomy import BLUEPRINT_EVIDENCE_CLASSES, BLUEPRINT_SOURCE_CLASSES

_CAP_KEYS = (
    "harvest_patent",
    "harvest_standards",
    "harvest_forum",
    "harvest_multilingual",
    "tag_evidence_class",
    "record_translation_provenance",
    "distinct_confidence_path",
    "source_policy_gate",
)


def _caps(**flags: bool) -> dict[str, bool]:
    out = {k: False for k in _CAP_KEYS}
    out["tag_evidence_class"] = True
    out["source_policy_gate"] = True
    out.update(flags)
    return out


def _bp(
    *,
    bid: str,
    title: str,
    stages: list[dict[str, str]],
    fixture: str,
    preset_id: str,
    preset_params: dict[str, Any],
    smoke_id: str,
    caps: dict[str, bool],
    max_claims: int,
) -> dict[str, Any]:
    return {
        "id": bid,
        "title": title,
        "source_classes": sorted(BLUEPRINT_SOURCE_CLASSES[bid]),
        "evidence_classes": sorted(BLUEPRINT_EVIDENCE_CLASSES[bid]),
        "typed_workflow": {
            "kind": "Workflow",
            "id": f"wf.{bid}",
            "stages": stages,
        },
        "runnable_example": {
            "id": f"ex.{bid}.hermetic",
            "fixture": fixture,
            "working_language": "en",
        },
        "preset": {
            "id": preset_id,
            "params": preset_params,
        },
        "stopping_rules": {
            "max_claims": max_claims,
            "halt_on": ["source-policy-denied", "missing-evidence-class"],
        },
        "smoke_test": {
            "id": smoke_id,
            "probe": "command-center/p2-wave/probes/IMP-0236/probe1_evidence_class_coverage.py",
        },
        "capability_vector": caps,
    }


def library() -> dict[str, dict[str, Any]]:
    items = [
        _bp(
            bid="prior-art-patent",
            title="Prior-art / patent harvest",
            stages=[
                {"id": "gate", "kind": "source-policy-gate"},
                {"id": "extract", "kind": "patent-extract"},
                {"id": "tag", "kind": "require-evidence-class"},
                {"id": "stop", "kind": "evaluate-stopping"},
            ],
            fixture="patent-family.json",
            preset_id="uspto-family-scan",
            preset_params={"jurisdiction": "US", "include_family": True},
            smoke_id="smoke.prior-art-patent",
            caps=_caps(harvest_patent=True),
            max_claims=50,
        ),
        _bp(
            bid="standards-regulatory",
            title="Standards / regulatory harvest",
            stages=[
                {"id": "gate", "kind": "source-policy-gate"},
                {"id": "extract", "kind": "standards-extract"},
                {"id": "tag", "kind": "require-evidence-class"},
                {"id": "stop", "kind": "evaluate-stopping"},
            ],
            fixture="iso-standard.json",
            preset_id="iso-normative-pass",
            preset_params={"split_normative_informative": True},
            smoke_id="smoke.standards-regulatory",
            caps=_caps(harvest_standards=True),
            max_claims=50,
        ),
        _bp(
            bid="niche-forum",
            title="Niche / forum harvest",
            stages=[
                {"id": "gate", "kind": "source-policy-gate"},
                {"id": "extract", "kind": "forum-extract"},
                {"id": "tag", "kind": "require-evidence-class"},
                {"id": "stop", "kind": "evaluate-stopping"},
            ],
            fixture="forum-thread.json",
            preset_id="anecdote-vs-docs",
            preset_params={"anecdote_class": "practitioner_anecdote"},
            smoke_id="smoke.niche-forum",
            caps=_caps(harvest_forum=True),
            max_claims=50,
        ),
        _bp(
            bid="multilingual",
            title="Multilingual harvest with translation provenance",
            stages=[
                {"id": "gate", "kind": "source-policy-gate"},
                {"id": "extract", "kind": "multilingual-extract"},
                {"id": "tag", "kind": "require-evidence-class"},
                {"id": "provenance", "kind": "record-translation"},
                {"id": "stop", "kind": "evaluate-stopping"},
            ],
            fixture="multilingual-pack.json",
            preset_id="native-vs-translated",
            preset_params={
                "working_language": "en",
                "translated_path": "translated-provisional",
            },
            smoke_id="smoke.multilingual",
            caps=_caps(
                harvest_multilingual=True,
                record_translation_provenance=True,
                distinct_confidence_path=True,
            ),
            max_claims=50,
        ),
    ]
    lib = {bp["id"]: bp for bp in items}
    for bp in lib.values():
        validate_blueprint(bp)
    dist = distinctness(lib.values())
    if not dist["distinct"]:
        raise RuntimeError(f"blueprint fingerprints collide: {dist['collisions']}")
    return lib


def as_list() -> list[dict[str, Any]]:
    lib = library()
    return [lib[k] for k in sorted(lib)]
