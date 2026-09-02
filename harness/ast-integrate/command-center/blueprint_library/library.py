"""Registered distinct blueprints. Size must match the derived taxonomy total."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

LIBRARY: list[dict[str, Any]] = [
    {
        "id": "deep-research",
        "title": "Deep research loop",
        "category": "research",
        "kind": "research-loop",
        "inputs": ["question", "corpus"],
        "outputs": ["memo", "citations"],
        "stages": ["retrieve", "cluster", "write"],
        "invariants": ["citation-required"],
        "failure_modes": ["hallucinated-source"],
    },
    {
        "id": "repo-map",
        "title": "Repo map",
        "category": "research",
        "kind": "graph-index",
        "inputs": ["tree"],
        "outputs": ["map"],
        "stages": ["walk", "rank"],
        "invariants": ["no-embedding-required"],
        "failure_modes": ["oversized-map"],
    },
    {
        "id": "lit-triage",
        "title": "Literature triage",
        "category": "research",
        "kind": "triage",
        "inputs": ["papers"],
        "outputs": ["keep-drop"],
        "stages": ["screen", "adjudicate"],
        "invariants": ["two-reviewer"],
        "failure_modes": ["single-screener"],
    },
    {
        "id": "typed-adapter",
        "title": "Typed adapter",
        "category": "engineering",
        "kind": "adapter",
        "inputs": ["envelope"],
        "outputs": ["command"],
        "stages": ["validate", "dispatch"],
        "invariants": ["schema-bound"],
        "failure_modes": ["silent-drop"],
    },
    {
        "id": "cache-key",
        "title": "Artifact cache key",
        "category": "engineering",
        "kind": "cache",
        "inputs": ["spec", "artifacts"],
        "outputs": ["key"],
        "stages": ["canonicalise", "hash"],
        "invariants": ["clock-free"],
        "failure_modes": ["stale-hit"],
    },
    {
        "id": "pathconv-guard",
        "title": "MSYS path conversion guard",
        "category": "engineering",
        "kind": "argv-guard",
        "inputs": ["argv"],
        "outputs": ["argv"],
        "stages": ["classify", "scope-env"],
        "invariants": ["revision-intact"],
        "failure_modes": ["global-nopathconv"],
    },
    {
        "id": "council-jury",
        "title": "Jury topology",
        "category": "governance",
        "kind": "topology",
        "inputs": ["ballots"],
        "outputs": ["finding"],
        "stages": ["brief", "vote", "tally"],
        "invariants": ["tally-not-prose"],
        "failure_modes": ["reinjection"],
    },
    {
        "id": "owner-override",
        "title": "Owner override log",
        "category": "governance",
        "kind": "override",
        "inputs": ["roster", "directive"],
        "outputs": ["seats"],
        "stages": ["compose", "apply"],
        "invariants": ["reason-required"],
        "failure_modes": ["silent-ignore"],
    },
    {
        "id": "both-states",
        "title": "Both-states detector",
        "category": "verification",
        "kind": "control",
        "inputs": ["good", "broken"],
        "outputs": ["verdict"],
        "stages": ["observe", "classify"],
        "invariants": ["silent-then-fire"],
        "failure_modes": ["silent-in-both"],
    },
    {
        "id": "schema-ref",
        "title": "Schema $ref retrieve",
        "category": "verification",
        "kind": "schema",
        "inputs": ["document"],
        "outputs": ["errors"],
        "stages": ["retrieve", "validate"],
        "invariants": ["disk-only"],
        "failure_modes": ["unresolvable"],
    },
    {
        "id": "uninstall-safety",
        "title": "Uninstall collateral guard",
        "category": "operations",
        "kind": "uninstall",
        "inputs": ["inventory"],
        "outputs": ["report"],
        "stages": ["snapshot", "remove", "verify"],
        "invariants": ["unrelated-intact"],
        "failure_modes": ["path-escape"],
    },
    {
        "id": "publish-portability",
        "title": "Portable publish gate",
        "category": "operations",
        "kind": "publish",
        "inputs": ["names"],
        "outputs": ["status"],
        "stages": ["lint", "pack"],
        "invariants": ["rule-quoted"],
        "failure_modes": ["reserved-name"],
    },
]


def paraphrase(entry: dict[str, Any], new_id: str) -> dict[str, Any]:
    clone = deepcopy(entry)
    clone["id"] = new_id
    clone["title"] = f"{entry.get('title', '')} (reworded)"
    clone["blurb"] = f"rewritten prose for {new_id}"
    return clone


def distinct_mutant(entry: dict[str, Any], new_id: str) -> dict[str, Any]:
    clone = deepcopy(entry)
    clone["id"] = new_id
    stages = list(clone.get("stages") or [])
    stages.append("fork-stage")
    clone["stages"] = stages
    clone["kind"] = str(clone.get("kind") or "x") + "-fork"
    return clone
