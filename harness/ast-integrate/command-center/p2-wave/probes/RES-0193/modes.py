"""Twelve Phase-2 research modes for RES-0193.

_USER-PROMPTS.md:10702-10715 is not on this Linux worktree. The roster is
reconstructed from catalog citations of those lines plus adjacent RES-2
units that name the modes. Reconstruction is labeled; this is not a claim
the markdown file was read.
"""
from __future__ import annotations

from typing import Any

# citation_status:
#   cited    — catalog quotes this name against a 107xx line
#   inferred — reconstructed to fill 10702-10715 to twelve modes
MODES: list[dict[str, Any]] = [
    {
        "id": "systematic_literature_review",
        "label": "systematic literature review",
        "spec_anchor": "_USER-PROMPTS.md:10702 (reconstructed; file absent)",
        "catalog_support": "RES-0192 title/tests: systematic vs rapid review",
        "citation_status": "inferred",
    },
    {
        "id": "rapid_review",
        "label": "rapid review",
        "spec_anchor": "_USER-PROMPTS.md:10703 (reconstructed; file absent)",
        "catalog_support": "RES-0192 title/tests: rapid protocol miss-set",
        "citation_status": "inferred",
    },
    {
        "id": "broad_landscape_scan",
        "label": "broad landscape scan",
        "spec_anchor": "_USER-PROMPTS.md:10704",
        "catalog_support": "RES-0192 inputs: 10704-10705 (broad landscape scan, targeted question answering)",
        "citation_status": "cited",
    },
    {
        "id": "targeted_question_answering",
        "label": "targeted question answering",
        "spec_anchor": "_USER-PROMPTS.md:10705",
        "catalog_support": "RES-0192 inputs: 10704-10705 (broad landscape scan, targeted question answering)",
        "citation_status": "cited",
    },
    {
        "id": "citation_chasing",
        "label": "citation chasing",
        "spec_anchor": "_USER-PROMPTS.md:10706 (reconstructed; file absent)",
        "catalog_support": "gap between 10705 targeted QA and 10707 contradiction hunt",
        "citation_status": "inferred",
    },
    {
        "id": "contradiction_hunt",
        "label": "contradiction hunt",
        "spec_anchor": "_USER-PROMPTS.md:10707",
        "catalog_support": "RES-0147 inputs: 10707 (contradiction hunt)",
        "citation_status": "cited",
    },
    {
        "id": "negative_result_hunt",
        "label": "negative-result hunt",
        "spec_anchor": "_USER-PROMPTS.md:10708",
        "catalog_support": "RES-0148 inputs: 10708 (negative-result hunt)",
        "citation_status": "cited",
    },
    {
        "id": "counterevidence_search",
        "label": "counterevidence search",
        "spec_anchor": "_USER-PROMPTS.md:10700 / 10709 (reconstructed; file absent)",
        "catalog_support": "RES-0147/RES-0187 inputs: 10700 (counterevidence to every major conclusion)",
        "citation_status": "cited",
    },
    {
        "id": "gem_hunt",
        "label": "gem hunt",
        "spec_anchor": "_USER-PROMPTS.md:10712",
        "catalog_support": "RES-0137 inputs: 10712 (gem hunt)",
        "citation_status": "cited",
    },
    {
        "id": "source_quality_audit",
        "label": "source-quality audit",
        "spec_anchor": "_USER-PROMPTS.md:10713",
        "catalog_support": "RES-0144/AUD spec_anchor: 10713 (source-quality audit)",
        "citation_status": "cited",
    },
    {
        "id": "freshness_revalidation_audit",
        "label": "freshness/revalidation audit",
        "spec_anchor": "_USER-PROMPTS.md:10714",
        "catalog_support": "RES-0180 inputs: 10714 (freshness/revalidation audit)",
        "citation_status": "cited",
    },
    {
        "id": "legal_license_review",
        "label": "legal and license review",
        "spec_anchor": "_USER-PROMPTS.md:10715",
        "catalog_support": "RES-0135 inputs: 10715 (legal and licence review)",
        "citation_status": "cited",
    },
]


def mode_ids() -> list[str]:
    return [row["id"] for row in MODES]


def by_id() -> dict[str, dict[str, Any]]:
    return {row["id"]: row for row in MODES}
