"""DISJOINT-plus-shared-core evidence partitions for SYN-0008.

Shared core is given to every synthesizer. Each disjoint class is given to
exactly one synthesizer. Coverage is computed: an evidence class that reaches
zero agents is a harness failure, not a synthesis.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "fixtures" / "evidence"

# Catalog inputs named as evidence classes. Upstream SYN-0001 / SYN-0005 /
# B08–B11 artifacts are absent on this worktree; these files stand in and
# are labelled as such inside the JSON.
EVIDENCE_FILES: dict[str, str] = {
    "syn0001": "syn0001-hierarchy.json",
    "syn0005": "syn0005-decision-trace.json",
    "B08": "B08-phase10.json",
    "B09": "B09-phase11.json",
    "B10": "B10-phase12.json",
    "B11": "B11-phase13.json",
}

SHARED_CLASSES: tuple[str, ...] = ("syn0001", "syn0005", "B11")
DISJOINT_ASSIGNMENT: dict[str, tuple[str, ...]] = {
    "syn8-anthropic-opus": ("B08",),
    "syn8-openai-gpt": ("B09",),
    "syn8-google-gemini": ("B10",),
}

AGENTS: tuple[dict[str, str], ...] = (
    {
        "id": "syn8-anthropic-opus",
        "vendor": "anthropic",
        "model": "opus",
        "lens": "cause-hierarchy",
    },
    {
        "id": "syn8-openai-gpt",
        "vendor": "openai",
        "model": "gpt",
        "lens": "decision-trace",
    },
    {
        "id": "syn8-google-gemini",
        "vendor": "google",
        "model": "gemini",
        "lens": "mutation-bucket",
    },
)

EXCLUSIVE_TOKENS: dict[str, str] = {
    "syn0001": "SYN8-SHARED-CORE-HIERARCHY",
    "syn0005": "SYN8-SHARED-CORE-TRACE",
    "B08": "SYN8-B08-ONLY-MUTANT-CORPUS",
    "B09": "SYN8-B09-ONLY-CITATION-AUDIT",
    "B10": "SYN8-B10-ONLY-REPRO-MATRIX",
    "B11": "SYN8-SHARED-B11-PHASE13",
}


def evidence_path(cls: str) -> Path:
    name = EVIDENCE_FILES[cls]
    return EVIDENCE / name


def classes_for(agent_id: str) -> list[str]:
    disjoint = list(DISJOINT_ASSIGNMENT[agent_id])
    return list(SHARED_CLASSES) + disjoint


def partition_manifest(agent: dict[str, str], sandbox_files: list[str]) -> dict[str, Any]:
    agent_id = agent["id"]
    return {
        "agent_id": agent_id,
        "vendor": agent["vendor"],
        "model": agent["model"],
        "lens": agent["lens"],
        "shared_classes": list(SHARED_CLASSES),
        "disjoint_classes": list(DISJOINT_ASSIGNMENT[agent_id]),
        "evidence_files": list(sandbox_files),
        "allow_read": list(sandbox_files),
    }


def coverage(manifests: list[dict[str, Any]]) -> dict[str, Any]:
    classes = list(EVIDENCE_FILES.keys())
    agents_per: dict[str, list[str]] = {c: [] for c in classes}
    for man in manifests:
        held = set(man.get("shared_classes") or []) | set(
            man.get("disjoint_classes") or []
        )
        agent_id = str(man.get("agent_id") or "")
        for cls in held:
            if cls in agents_per:
                agents_per[cls].append(agent_id)
    zero = [c for c, agents in agents_per.items() if not agents]
    return {
        "evidence_classes": classes,
        "agents_per_class": agents_per,
        "zero_agent_classes": zero,
        "shared_core": list(SHARED_CLASSES),
        "disjoint_assignment": {k: list(v) for k, v in DISJOINT_ASSIGNMENT.items()},
    }


def tokens_expected(agent_id: str) -> set[str]:
    return {EXCLUSIVE_TOKENS[c] for c in classes_for(agent_id)}


def tokens_forbidden(agent_id: str) -> set[str]:
    held = tokens_expected(agent_id)
    return set(EXCLUSIVE_TOKENS.values()) - held
