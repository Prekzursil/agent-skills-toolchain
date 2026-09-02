#!/usr/bin/env python3
"""Frozen 16 source classes and 12 research modes for RES-0128.

_USER-PROMPTS.md:10683-10715 is not on this worktree. The lists below are
reconstructed from catalog citations of those line ranges (IMP-0234..0237
research blueprints 1-12; IMP-0236 source-class note at 10696-10699;
source_policy examples; RES-0138/0141/0142 class names; retry ladder
official-doc -> source-code -> issue-tracker -> archive).

Coverage MUST use these ids. Adding a 17th class or 13th mode is a
detector failure, not extra credit.
"""
from __future__ import annotations

# 16 spec source classes (catalog: _USER-PROMPTS.md:10683-10715).
# Last three occupy the 10696-10699 "niche, multilingual, archival" citation.
SOURCE_CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "issue-tracker",
    "papers",
    "blogs",
    "practitioner-forums",
    "video-talk",
    "patents",
    "standards-regulatory",
    "package-registries",
    "mailing-lists",
    "changelogs",
    "public-tor",
    "niche",
    "multilingual",
    "archival",
)

# 12 spec research modes (catalog: _USER-PROMPTS.md:10702-10715 /
# IMP-0234..0236 "research blueprints 1-12").
RESEARCH_MODES: tuple[str, ...] = (
    "deep-research",
    "gem-hunt",
    "systematic-literature-review",
    "rapid-literature-review",
    "evidence-map",
    "fact-citation-audit",
    "official-doc-audit",
    "source-code-archaeology",
    "prior-art-patent",
    "standards-regulatory",
    "niche-forum",
    "multilingual",
)

assert len(SOURCE_CLASSES) == 16, len(SOURCE_CLASSES)
assert len(RESEARCH_MODES) == 12, len(RESEARCH_MODES)
assert len(set(SOURCE_CLASSES)) == 16
assert len(set(RESEARCH_MODES)) == 12

SENTINEL = (
    "SUCCESS:RES-0128 in the receipt AND a computed coverage table over "
    "16 classes and 12 modes plus a ranked blind-spot list where each "
    "entry is a draft unit definition"
)

# Aliases that may appear in emitted citation fields. Keys are spec ids.
CLASS_ALIASES: dict[str, tuple[str, ...]] = {
    "official-docs": (
        "official-docs",
        "official_docs",
        "official-doc",
        "official_doc",
        "docs",
    ),
    "source-code": (
        "source-code",
        "source_code",
        "code",
        "source-repo",
        "repository",
    ),
    "issue-tracker": (
        "issue-tracker",
        "issue_tracker",
        "issues",
        "issue-tracker-sourced",
    ),
    "papers": ("papers", "paper", "arxiv", "scholarly"),
    "blogs": ("blogs", "blog", "blog-post", "blog_post"),
    "practitioner-forums": (
        "practitioner-forums",
        "forums",
        "forum",
        "practitioner-forum",
    ),
    "video-talk": (
        "video-talk",
        "video_talk",
        "video/talk",
        "talk-transcript",
        "transcript",
    ),
    "patents": ("patents", "patent", "prior-art-patent", "prior_art"),
    "standards-regulatory": (
        "standards-regulatory",
        "standards",
        "regulatory",
        "rfc",
    ),
    "package-registries": (
        "package-registries",
        "package-registry",
        "npm",
        "pypi",
        "crates",
    ),
    "mailing-lists": ("mailing-lists", "mailing-list", "mailing_list"),
    "changelogs": ("changelogs", "changelog", "release-notes", "release_notes"),
    "public-tor": ("public-tor", "public_tor", "tor", "onion", "public-onion"),
    "niche": ("niche", "niche-forum", "niche_forum"),
    "multilingual": ("multilingual", "non-english", "non_english"),
    "archival": ("archival", "archive", "web-archive", "software-heritage"),
}

MODE_ALIASES: dict[str, tuple[str, ...]] = {
    "deep-research": ("deep-research", "deep_research", "deep-research-blueprint"),
    "gem-hunt": ("gem-hunt", "gem_hunt", "gem-hunt-lead"),
    "systematic-literature-review": (
        "systematic-literature-review",
        "systematic_literature_review",
        "slr",
    ),
    "rapid-literature-review": (
        "rapid-literature-review",
        "rapid_literature_review",
        "rapid-review",
    ),
    "evidence-map": ("evidence-map", "evidence_map", "evidence-mapping"),
    "fact-citation-audit": (
        "fact-citation-audit",
        "fact_citation_audit",
        "citation-audit",
    ),
    "official-doc-audit": ("official-doc-audit", "official_doc_audit"),
    "source-code-archaeology": (
        "source-code-archaeology",
        "source_code_archaeology",
        "code-archaeology",
    ),
    "prior-art-patent": ("prior-art-patent", "prior_art_patent", "patent-search"),
    "standards-regulatory": (
        "standards-regulatory",
        "standards_regulatory",
        "standards-review",
    ),
    "niche-forum": ("niche-forum", "niche_forum", "niche-forum-sweep"),
    "multilingual": ("multilingual", "multilingual-sweep"),
}

# Catalog-plan keyword hints. Used ONLY for the diagnostic planned column,
# never as cited coverage.
CLASS_PLAN_HINTS: dict[str, tuple[str, ...]] = {
    "official-docs": ("official doc", "official-docs", "plugin.json", "docs page"),
    "source-code": ("source code", "source-code", "github", "mcp__github"),
    "issue-tracker": ("issue tracker", "issue-tracker", "issue-tracker-sourced"),
    "papers": ("arxiv", "paper-search", "scholarly", "papers"),
    "blogs": ("blog-post", "blog post", "blogs"),
    "practitioner-forums": ("forum", "practitioner"),
    "video-talk": ("video/talk", "talk transcript", "transcript"),
    "patents": ("patent", "prior-art"),
    "standards-regulatory": ("standards/regulatory", "rfc ", "regulatory"),
    "package-registries": ("npm ", "pypi", "packagist", "crates.io"),
    "mailing-lists": ("mailing list", "mailing-list"),
    "changelogs": ("changelog", "release notes"),
    "public-tor": ("tor/", "onion", "public-tor"),
    "niche": ("niche",),
    "multilingual": ("multilingual", "non-english", "non-English"),
    "archival": ("archival", "web.archive", "softwareheritage", "wayback"),
}

MODE_PLAN_HINTS: dict[str, tuple[str, ...]] = {
    "deep-research": ("deep-research", "deep research"),
    "gem-hunt": ("gem-hunt", "gem hunt", "gem-hunt-lead"),
    "systematic-literature-review": ("systematic literature", "systematic-literature"),
    "rapid-literature-review": ("rapid literature", "rapid-literature"),
    "evidence-map": ("evidence-map", "evidence map", "evidence-map"),
    "fact-citation-audit": ("citation-audit", "fact-citation"),
    "official-doc-audit": ("official-doc-audit", "doc audit"),
    "source-code-archaeology": ("archaeology", "source-code-archaeology"),
    "prior-art-patent": ("prior-art", "patent"),
    "standards-regulatory": ("standards-regulatory", "standards/regulatory"),
    "niche-forum": ("niche-forum", "niche/forum"),
    "multilingual": ("multilingual",),
}

# Fields that count as an actual citation of a source class.
CITED_CLASS_KEYS: frozenset[str] = frozenset(
    {
        "source_classes_cited",
        "cited_source_classes",
        "source_class",
        "cited_source_class",
        "used_source_classes",
        "source_classes_used",
    }
)

CITED_MODE_KEYS: frozenset[str] = frozenset(
    {
        "research_modes_used",
        "cited_research_modes",
        "research_mode",
        "cited_research_mode",
        "used_research_modes",
        "research_modes_cited",
    }
)

# Plan/policy fields that MUST NOT count as coverage.
PLAN_KEYS: frozenset[str] = frozenset(
    {
        "planned_source_classes",
        "planned_research_modes",
        "source_classes",
        "research_modes",
        "allowed_source_classes",
        "source_policy",
        "inputs",
        "tool_permissions",
        "question_or_target",
        "title",
    }
)

# Container keys whose children may carry citations.
CITATION_CONTAINERS: frozenset[str] = frozenset(
    {
        "citations",
        "sources",
        "source_lineage",
        "claims",
        "evidence",
        "cited",
        "used_sources",
        "rails",
        "captures",
        "fetches",
        "snapshots",
        "lineage",
    }
)
