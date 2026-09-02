"""Fixture workflows for IMP-0184.

W has internally unique stage fingerprints (required for union(w,w)==w rather
than union(w,w)==collapse(w)). A and B share one structurally identical
ingest stage and each carry a unique capability the other lacks.
"""
from __future__ import annotations

from coverage import TAXONOMY
from fingerprint import internally_unique_stages, stage_fingerprint


def _ingest(stage_id: str) -> dict:
    return {
        "id": stage_id,
        "kind": "ingest",
        "roles": ["collector"],
        "gates": {"all": [{"atom": "input.nonempty"}]},
        "tools": ["fs.read"],
        "inputs": ["path"],
        "outputs": ["blob"],
        "capabilities": ["research.web"],
    }


def workflow_w() -> dict:
    return {
        "id": "wf-self",
        "stages": [
            _ingest("ingest"),
            {
                "id": "analyze",
                "kind": "analyze",
                "roles": ["analyst"],
                "gates": {"all": [{"atom": "confidence>=0.7"}]},
                "tools": ["llm.complete"],
                "inputs": ["blob"],
                "outputs": ["findings"],
                "capabilities": ["research.cite"],
            },
            {
                "id": "stop",
                "kind": "gate",
                "roles": ["controller"],
                "gates": {
                    "any": [
                        {"atom": "budget.exhausted"},
                        {"atom": "confidence>=0.9"},
                    ]
                },
                "tools": ["clock"],
                "inputs": ["findings"],
                "outputs": ["halt"],
                "capabilities": ["gate.budget"],
            },
        ],
        "edges": [
            {"from": "ingest", "to": "analyze"},
            {"from": "analyze", "to": "stop"},
        ],
    }


def workflow_a() -> dict:
    return {
        "id": "wf-parent-a",
        "stages": [
            _ingest("ingest-a"),
            {
                "id": "review",
                "kind": "review",
                "roles": ["adversary"],
                "gates": {"all": [{"atom": "findings.present"}]},
                "tools": ["diff.semantic"],
                "inputs": ["blob"],
                "outputs": ["verdict"],
                "capabilities": ["review.adversarial"],
            },
        ],
        "edges": [{"from": "ingest-a", "to": "review"}],
    }


def workflow_b() -> dict:
    return {
        "id": "wf-parent-b",
        "stages": [
            _ingest("ingest-b"),
            {
                "id": "emit",
                "kind": "emit",
                "roles": ["builder"],
                "gates": {"all": [{"atom": "schema.valid"}]},
                "tools": ["fs.write"],
                "inputs": ["blob"],
                "outputs": ["artifact"],
                "capabilities": ["build.emit"],
            },
        ],
        "edges": [{"from": "ingest-b", "to": "emit"}],
    }


def shared_ingest_fps_match() -> bool:
    return stage_fingerprint(_ingest("ingest-a")) == stage_fingerprint(_ingest("ingest-b"))


def fixtures_ok() -> None:
    for name, wf in (("w", workflow_w()), ("a", workflow_a()), ("b", workflow_b())):
        if not internally_unique_stages(wf):
            raise AssertionError(f"fixture {name} has internal duplicate stages")
        ids = [s["id"] for s in wf["stages"]]
        if len(ids) != len(set(ids)):
            raise AssertionError(f"fixture {name} has duplicate stage ids")
    if not shared_ingest_fps_match():
        raise AssertionError("A/B ingest stages are not structurally identical")
    if TAXONOMY["version"] != "1.0.0":
        raise AssertionError("taxonomy version unexpected")
