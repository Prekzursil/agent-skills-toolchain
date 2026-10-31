"""Register research blueprints 5-8. Distinct fingerprints; six-element contract."""
from __future__ import annotations

from typing import Any

from research.blueprints.contract import REQUIRED_ELEMENTS, register_blueprint
from research.blueprints.workflow import (
    distinct_fingerprints,
    stage,
    typed_workflow,
)

BLUEPRINT_IDS = (
    "evidence-map",
    "fact-citation-audit",
    "official-doc-audit",
    "source-code-archaeology",
)

PROBE1 = "command-center/p2-wave/probes/IMP-0235/probe1_dead_citation.py"
PROBE2 = "command-center/p2-wave/probes/IMP-0235/probe2_blob_vs_crlf.py"


def _bp(
    *,
    bid: str,
    title: str,
    stages: list[dict[str, Any]],
    fixture: str,
    preset_id: str,
    preset_params: dict[str, Any],
    stopping: dict[str, Any],
    smoke_id: str,
    smoke_probe: str,
    caps: dict[str, bool],
) -> dict[str, Any]:
    return {
        "id": bid,
        "title": title,
        "typed_workflow": typed_workflow(f"wf.{bid}", stages, max_stages=12),
        "runnable_example": {
            "id": f"ex.{bid}.hermetic",
            "fixture": fixture,
            "working_language": "en",
        },
        "preset": {"id": preset_id, "params": preset_params},
        "stopping_rules": stopping,
        "smoke_test": {"id": smoke_id, "probe": smoke_probe},
        "capability_vector": caps,
    }


def evidence_map_blueprint() -> dict[str, Any]:
    return _bp(
        bid="evidence-map",
        title="Evidence map with coverage-hole scoring",
        stages=[
            stage("ingest", "claim-ingest", inputs=["claims"], outputs=["claims"]),
            stage("link", "link-evidence", inputs=["claims", "evidence"], outputs=["map"]),
            stage("holes", "score-coverage-holes", inputs=["map"], outputs=["holes"]),
        ],
        fixture="command-center/p2-wave/probes/IMP-0235/fixtures/live-source.txt",
        preset_id="coverage-holes",
        preset_params={"require_evidence_ids": True},
        stopping={"max_claims": 200, "halt_on": ["empty-map"]},
        smoke_id="smoke.evidence-map",
        smoke_probe=PROBE1,
        caps={
            "map_claims_to_evidence": True,
            "score_coverage_holes": True,
            "audit_citations": False,
            "audit_official_docs": False,
            "read_git_blob": False,
        },
    )


def fact_citation_audit_blueprint() -> dict[str, Any]:
    return _bp(
        bid="fact-citation-audit",
        title="Fact/citation audit (unfetchable is UNRESOLVED)",
        stages=[
            stage("collect", "collect-citations", inputs=["report"], outputs=["citations"]),
            stage("fetch", "fetch-citation-body", inputs=["citations"], outputs=["bodies"]),
            stage(
                "resolve",
                "resolve-or-unresolved",
                inputs=["citations", "bodies"],
                outputs=["verdicts"],
            ),
        ],
        fixture="command-center/p2-wave/probes/IMP-0235/fixtures/live-source.txt",
        preset_id="dead-citation-unresolved",
        preset_params={"assume_unfetchable_valid": False},
        stopping={"max_citations": 500, "halt_on": ["fetch-error-storm"]},
        smoke_id="smoke.fact-citation-audit",
        smoke_probe=PROBE1,
        caps={
            "map_claims_to_evidence": False,
            "score_coverage_holes": False,
            "audit_citations": True,
            "never_assume_unfetchable_valid": True,
            "audit_official_docs": False,
            "read_git_blob": False,
        },
    )


def official_doc_audit_blueprint() -> dict[str, Any]:
    return _bp(
        bid="official-doc-audit",
        title="Official-document audit against an allowlist",
        stages=[
            stage("allow", "load-official-allowlist", inputs=["policy"], outputs=["allowlist"]),
            stage("fetch", "fetch-official-doc", inputs=["docs", "allowlist"], outputs=["bodies"]),
            stage("quote", "confirm-quoted-span", inputs=["docs", "bodies"], outputs=["verdicts"]),
        ],
        fixture="command-center/p2-wave/probes/IMP-0235/fixtures/live-source.txt",
        preset_id="allowlist-only",
        preset_params={"unlisted_is_unresolved": True},
        stopping={"max_docs": 100, "halt_on": ["empty-allowlist"]},
        smoke_id="smoke.official-doc-audit",
        smoke_probe=PROBE1,
        caps={
            "map_claims_to_evidence": False,
            "score_coverage_holes": False,
            "audit_citations": False,
            "audit_official_docs": True,
            "require_allowlist": True,
            "read_git_blob": False,
        },
    )


def source_code_archaeology_blueprint() -> dict[str, Any]:
    return _bp(
        bid="source-code-archaeology",
        title="Source-code archaeology via git cat-file -p",
        stages=[
            stage("locate", "locate-revision-path", inputs=["rev", "path"], outputs=["spec"]),
            stage("blob", "cat-file-blob", inputs=["spec"], outputs=["bytes"]),
            stage("refuse", "refuse-archive-recipe", inputs=["recipe"], outputs=["gate"]),
        ],
        fixture="control.txt",
        preset_id="cat-file-not-archive",
        preset_params={"recipe": "git cat-file -p", "forbid": "git archive"},
        stopping={"max_paths": 50, "halt_on": ["archive-recipe"]},
        smoke_id="smoke.source-code-archaeology",
        smoke_probe=PROBE2,
        caps={
            "map_claims_to_evidence": False,
            "score_coverage_holes": False,
            "audit_citations": False,
            "audit_official_docs": False,
            "read_git_blob": True,
            "refuse_git_archive": True,
        },
    )


def library() -> dict[str, dict[str, Any]]:
    items = [
        evidence_map_blueprint(),
        fact_citation_audit_blueprint(),
        official_doc_audit_blueprint(),
        source_code_archaeology_blueprint(),
    ]
    lib = {bp["id"]: bp for bp in items}
    for bp in lib.values():
        rec = register_blueprint(bp)
        if not rec["ok"]:
            raise RuntimeError(f"blueprint {bp['id']} failed contract: {rec}")
        missing = [e for e in REQUIRED_ELEMENTS if e not in bp]
        if missing:
            raise RuntimeError(f"blueprint {bp['id']} missing {missing}")
    if set(lib) != set(BLUEPRINT_IDS):
        raise RuntimeError(f"registered ids {sorted(lib)} != {list(BLUEPRINT_IDS)}")
    if not distinct_fingerprints(lib.values()):
        raise RuntimeError("blueprint fingerprints collide; four names, one body")
    return lib


def registered() -> set[str]:
    return set(library())
