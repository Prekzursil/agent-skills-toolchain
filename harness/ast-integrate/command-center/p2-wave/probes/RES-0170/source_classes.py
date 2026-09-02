#!/usr/bin/env python3
"""Frozen 16 source-class register for RES-0170.

_USER-PROMPTS.md:10681-10717 is absent on this worktree. The list is
reconstructed from catalog citations (source_policy examples, research
blueprints 1-15, retry-policy source-route, video/talk vs blog-post vs
official-docs). It is a named reconstruction, not a recovered spec page.
A class not in this closed set cannot increment coverage.
"""
from __future__ import annotations

# Catalog reconstruction of the 16 Phase-2 source classes.
SOURCE_CLASSES: tuple[str, ...] = (
    "official-docs",
    "source-code",
    "papers",
    "issue-tracker",
    "niche-forum",
    "archival",
    "blog-post",
    "video-talk",
    "multilingual",
    "prior-art-patent",
    "standards-regulatory",
    "public-tor",
    "changelog",
    "mailing-list",
    "practitioner-anecdote",
    "wikipedia-secondary",
)

SOURCE_CLASS_SET = frozenset(SOURCE_CLASSES)

DERIVATION = {
    "user_prompts_path": "_USER-PROMPTS.md",
    "user_prompts_present": False,
    "claimed_spec_lines": "10681-10717",
    "method": (
        "Closed 16-class set reconstructed from WORK-UNIT-CATALOG.json "
        "citations of those lines (source_policy official-docs/code/papers/"
        "forums/archival/public-tor; blueprints prior-art-patent, "
        "standards-regulatory, niche-forum, multilingual, archival; "
        "retry-policy official-doc -> source-code -> issue-tracker -> archive; "
        "RES-0108 video/talk vs blog-post vs official-docs; changelog and "
        "mailing-list as dated surfaces; practitioner-anecdote as the "
        "niche-forum evidence subclass promoted to a class so the set has "
        "16 named members; wikipedia-secondary as the remaining catalog "
        "secondary-source class)."
    ),
    "count": len(SOURCE_CLASSES),
    "residual": (
        "If _USER-PROMPTS.md:10683-10700 is later mounted and names a "
        "different 16, this register must be rebound and the six artifacts "
        "rescored. Until then the metric uses this frozen list and says so."
    ),
}


def is_registered(name: str) -> bool:
    return (name or "").strip() in SOURCE_CLASS_SET
