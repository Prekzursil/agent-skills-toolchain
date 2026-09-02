"""Frozen local gold for WFA-0047 (G-family SKILL.md stage extraction).

WFA-0042's catalog gold-set artifact is absent on this worktree. This freeze
is the scoring set for THIS adapter: six EXTRACTED skills and ten
NOT-EXTRACTABLE skills. Titles are the body ordinals; frontmatter numbers
are mention, not use.
"""
from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures" / "skills"

GOLD = [
    {
        "id": "gold-freeze-hook",
        "verdict": "EXTRACTED",
        "titles": [
            "Write the hook file",
            "Register it in hooks.json",
            "Prove a write is rejected",
        ],
        "snippets": [
            "1. Write the hook file",
            "2. Register it in hooks.json",
            "3. Prove a write is rejected",
        ],
    },
    {
        "id": "gold-numbered-headings",
        "verdict": "EXTRACTED",
        "titles": [
            "Look before you speak",
            "One-line explanation",
            "Set up and save",
        ],
        "snippets": [
            "## 1. Look before you speak",
            "## 2. One-line explanation",
            "## 3. Set up and save",
        ],
    },
    {
        "id": "gold-step-labels",
        "verdict": "EXTRACTED",
        "titles": [
            "Parse the SKILL.md frontmatter as intent only",
            "Walk the body for ordinals",
            "Emit IR stages with line anchors",
        ],
        "snippets": [
            "Step 1: Parse the SKILL.md frontmatter as intent only",
            "Step 2: Walk the body for ordinals",
            "Step 3: Emit IR stages with line anchors",
        ],
    },
    {
        "id": "gold-phases",
        "verdict": "EXTRACTED",
        "titles": [
            "Discover requirements",
            "Draft the skill",
            "Verify the skill",
        ],
        "snippets": [
            "### Phase 1: Discover requirements",
            "### Phase 2: Draft the skill",
            "### Phase 3: Verify the skill",
        ],
    },
    {
        "id": "gold-nested-ol",
        "verdict": "EXTRACTED",
        "titles": [
            "Prepare the workspace",
            "Run the extractor",
            "Write the receipt",
        ],
        "snippets": [
            "1. Prepare the workspace",
            "2. Run the extractor",
            "3. Write the receipt",
        ],
    },
    {
        "id": "gold-body-beats-frontmatter",
        "verdict": "EXTRACTED",
        "titles": [
            "Read the body",
            "Emit IR stages",
            "Cite line numbers",
        ],
        "snippets": [
            "1. Read the body",
            "2. Emit IR stages",
            "3. Cite line numbers",
        ],
        "forbidden_titles": [
            "Mentioned only in frontmatter",
            "Should not become stages",
            "Ignore me",
        ],
    },
]

REFUSE = [
    {
        "id": "refuse-roles",
        "verdict": "NOT-EXTRACTABLE",
        "why": "role roster, no ordered procedure",
    },
    {
        "id": "refuse-glossary",
        "verdict": "NOT-EXTRACTABLE",
        "why": "unordered term list",
    },
    {
        "id": "refuse-bullets",
        "verdict": "NOT-EXTRACTABLE",
        "why": "unordered capability list",
    },
    {
        "id": "refuse-frontmatter-trap",
        "verdict": "NOT-EXTRACTABLE",
        "why": "numbered list exists only in frontmatter description (mention)",
    },
    {
        "id": "refuse-alternatives",
        "verdict": "NOT-EXTRACTABLE",
        "why": "parallel options, no required order",
    },
    {
        "id": "refuse-overview",
        "verdict": "NOT-EXTRACTABLE",
        "why": "conceptual prose",
    },
    {
        "id": "refuse-table",
        "verdict": "NOT-EXTRACTABLE",
        "why": "reference table",
    },
    {
        "id": "refuse-faq",
        "verdict": "NOT-EXTRACTABLE",
        "why": "Q&A, not a procedure",
    },
    {
        "id": "refuse-single-imperative",
        "verdict": "NOT-EXTRACTABLE",
        "why": "single rule, not a multi-stage sequence",
    },
    {
        "id": "refuse-codeblock-mention",
        "verdict": "NOT-EXTRACTABLE",
        "why": "ordinals appear only inside a fenced example",
    },
]


def skill_path(skill_id: str) -> Path:
    return FIX / skill_id / "SKILL.md"


def all_records() -> list[dict]:
    return list(GOLD) + list(REFUSE)
