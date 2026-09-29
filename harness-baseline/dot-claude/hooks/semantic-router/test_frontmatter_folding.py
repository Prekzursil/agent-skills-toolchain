#!/usr/bin/env python
"""Regression tests: YAML block-scalar descriptions must survive frontmatter parsing.

Known-broken (both routers, same defect): `_split_frontmatter` / `_meta` matched only
`^description:\\s*(.+)$`, so `description: >` yielded the literal marker `>` and every
descriptive word was dropped. Downstream that (a) poisoned the embedded doc head and the
200-char excerpt in the semantic index and (b) left the lexical unit with just its own
name as a token, which cannot clear route.py's 2-shared-token gate.

Six of the 345 canonical `.agents/skills/*/SKILL.md` files use a block scalar, so this is
live against the current corpus, not a hypothetical.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
BUILD_INDEX_PY = HERE / "build_index.py"
LEXICAL_ROUTE_PY = HERE.parent / "skill-router" / "route.py"
REPO_ROOT = HERE.parents[1]

FOLDED = """---
name: frontend-a11y
description: >
  Use when building accessible React components, keyboard navigation,
  focus management, and screen reader support for web UIs.
---

# Frontend a11y

Body prose that must not be mistaken for the description.
"""

LITERAL = """---
name: demo-literal
description: |-
  Use when doing literal block things with pipes.
---

# Demo
"""

PLAIN = """---
name: plain-one
description: Use when the description is a simple same-line scalar.
---

# Plain
"""

A11Y_PROMPT = (
    "Build a React modal with keyboard navigation, focus management, "
    "and screen reader support."
)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def build_index():
    return _load(BUILD_INDEX_PY, "semantic_router_build_index_fm_test")


@pytest.fixture(scope="module")
def lexical_route():
    return _load(LEXICAL_ROUTE_PY, "skill_router_route_fm_test")


# ------------------------------------------------------------------ semantic builder
def test_folded_description_is_not_read_as_its_block_marker(build_index):
    _name, desc, _body = build_index._split_frontmatter(FOLDED)

    assert desc not in (">", ">-", "|", "|-")
    assert desc.startswith("Use when building accessible React components")
    assert "screen reader support" in desc


def test_literal_block_description_is_also_folded(build_index):
    _name, desc, _body = build_index._split_frontmatter(LITERAL)

    assert desc == "Use when doing literal block things with pipes."


def test_same_line_description_is_unchanged(build_index):
    name, desc, body = build_index._split_frontmatter(PLAIN)

    assert name == "plain-one"
    assert desc == "Use when the description is a simple same-line scalar."
    assert body.lstrip().startswith("# Plain")


def test_no_frontmatter_still_yields_empty_metadata(build_index):
    name, desc, body = build_index._split_frontmatter("# Just a heading\n\ntext\n")

    assert (name, desc) == ("", "")
    assert body.startswith("# Just a heading")


def test_folded_excerpt_is_prose_not_a_marker(build_index):
    _name, desc, body = build_index._split_frontmatter(FOLDED)

    excerpt = build_index._excerpt(desc, body)

    assert excerpt.startswith("Use when building accessible React components")
    assert len(excerpt) <= 200


def test_folded_description_reaches_the_embedded_document_text(build_index):
    """The doc text feeds BOTH the vector and the change-hash, so repairing the parse
    invalidates every affected row's sha and the next incremental build re-embeds it."""
    name, desc, body = build_index._split_frontmatter(FOLDED)

    text = build_index._doc_text("skill", name, desc, body, build_index.BODY_CAP)
    marker_text = build_index._doc_text("skill", name, ">", body, build_index.BODY_CAP)

    assert "use when: Use when building accessible React components" in text
    assert build_index._sha(text) != build_index._sha(marker_text)


# ------------------------------------------------------------------ lexical router
def test_lexical_meta_recovers_the_folded_description(lexical_route, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text(FOLDED, encoding="utf-8")

    name, desc = lexical_route._meta(str(skill), "frontend-a11y")

    assert name == "frontend-a11y"
    assert desc.startswith("Use when building accessible React components")


def test_lexical_meta_falls_back_to_the_directory_name(lexical_route, tmp_path):
    skill = tmp_path / "SKILL.md"
    skill.write_text("# no frontmatter here\n", encoding="utf-8")

    name, desc = lexical_route._meta(str(skill), "fallback-name")

    assert (name, desc) == ("fallback-name", "")


def test_folded_skill_clears_the_two_shared_token_gate(lexical_route, tmp_path):
    """The concrete miss: with desc == '>' the only token was the skill's own name, so
    `len(shared) < 2` discarded the right skill for an obviously matching prompt."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(FOLDED, encoding="utf-8")
    name, desc = lexical_route._meta(str(skill), "frontend-a11y")

    unit_tokens = lexical_route._tok(f"{name} {name} {desc}")
    shared = lexical_route._tok(A11Y_PROMPT) & unit_tokens

    assert len(shared) >= 2, f"routing gate still discards the skill: {sorted(shared)}"


# ------------------------------------------------------------------ live corpus
def test_no_canonical_skill_indexes_a_bare_block_marker(build_index):
    """End-to-end over the tracked skill corpus: no SKILL.md may reduce to a marker."""
    skills = sorted((REPO_ROOT / ".agents" / "skills").glob("*/SKILL.md"))
    assert skills, "canonical skill corpus not found"

    offenders = []
    for md in skills:
        _name, desc, _body = build_index._split_frontmatter(
            md.read_text(encoding="utf-8", errors="replace")
        )
        if desc.strip() in (">", ">-", ">+", "|", "|-", "|+"):
            offenders.append(md.parent.name)

    assert offenders == []


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
