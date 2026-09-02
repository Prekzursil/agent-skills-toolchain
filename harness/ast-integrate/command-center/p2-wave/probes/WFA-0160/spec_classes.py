"""Enumerated 2A archaeology source classes for WFA-0160.

_USER-PROMPTS.md:10721 is not on this Linux worktree. The enumerated set is
reconstructed from catalog citations of that line (GitHub as a 2A source
class; search prior artifacts and transcripts) plus the sixteen WFA-0013
through WFA-0028 sweep units that are this bucket's operational search plan.
That reconstruction is labeled; it is not a claim the markdown file was read.
"""
from __future__ import annotations

from typing import Any

# Catalog-cited :10721 fragments plus the 2A sweep operationalization.
SPEC_SOURCE_CLASSES: list[dict[str, Any]] = [
    {
        "id": "repo-HEAD",
        "sweep_unit": "WFA-0013",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "repository at HEAD",
    },
    {
        "id": "remote-branches",
        "sweep_unit": "WFA-0014",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "remote branch",
    },
    {
        "id": "worktrees",
        "sweep_unit": "WFA-0015",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "worktree",
    },
    {
        "id": "releases-and-tags",
        "sweep_unit": "WFA-0016",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "releases and tags",
    },
    {
        "id": "deployed-skill-trees",
        "sweep_unit": "WFA-0017",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "skill trees",
    },
    {
        "id": "installed-plugins",
        "sweep_unit": "WFA-0018",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "installed plugins",
    },
    {
        "id": "prior-artifacts",
        "sweep_unit": "WFA-0019",
        "spec_anchor": "_USER-PROMPTS.md:10721 (search prior artifacts and transcripts)",
        "catalog_title_fragment": "Prompt One corpus",
    },
    {
        "id": "session-transcripts",
        "sweep_unit": "WFA-0020",
        "spec_anchor": "_USER-PROMPTS.md:10721 (search prior artifacts and transcripts)",
        "catalog_title_fragment": "executed-workflow runs",
    },
    {
        "id": "vendor-documentation",
        "sweep_unit": "WFA-0021",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "vendor documentation",
    },
    {
        "id": "abandoned-git-salvage",
        "sweep_unit": "WFA-0022",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "abandoned work",
    },
    {
        "id": "public-plugin-marketplaces",
        "sweep_unit": "WFA-0023",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "plugin marketplaces",
    },
    {
        "id": "github-code-search",
        "sweep_unit": "WFA-0024",
        "spec_anchor": "_USER-PROMPTS.md:10721 (GitHub named as a 2A source class)",
        "catalog_title_fragment": "GitHub",
    },
    {
        "id": "academic-literature",
        "sweep_unit": "WFA-0025",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "academic",
    },
    {
        "id": "practitioner-reports",
        "sweep_unit": "WFA-0026",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "practitioner",
    },
    {
        "id": "adjacent-runtimes",
        "sweep_unit": "WFA-0027",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "adjacent runtimes",
    },
    {
        "id": "niche-archival-non-english",
        "sweep_unit": "WFA-0028",
        "spec_anchor": "_USER-PROMPTS.md:10721 (reconstructed; file absent on this tree)",
        "catalog_title_fragment": "niche, non-English, archived",
    },
]


def spec_ids() -> list[str]:
    return [row["id"] for row in SPEC_SOURCE_CLASSES]


def by_sweep_unit() -> dict[str, dict[str, Any]]:
    return {row["sweep_unit"]: row for row in SPEC_SOURCE_CLASSES}
