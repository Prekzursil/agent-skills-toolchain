"""D-a016 -- the coverage-authority contract between the TDD specialist and the rules.

``rules/common/testing.md:23,38`` make ``.coverage-thresholds.json`` the single source
of truth for the coverage floor and keep ``80%+`` only as the fallback when a repository
defines no threshold file. ``rules/common/code-review.md:57,98`` and
``rules/common/development-workflow.md:48`` say the same thing in the same words.

``agents/tdd-guide.md`` is the agent those documents route coverage verification TO --
``agent-self/config/commands/orchestrate.md:18,24,30`` chain ``planner -> tdd-guide ->
code-reviewer``, and ``.agents/skills/plan-orchestrate/SKILL.md:124-125`` map both the
``impl`` and ``test`` intents onto it. Before this suite landed that agent stated a flat
``80%+`` requirement in its frontmatter description, its role list, its "Verify Coverage"
step and its completion checklist, and referenced ``.coverage-thresholds.json`` ZERO
times. On a repository whose threshold file sets a higher floor (100 on all four axes,
with ``blockTaskCompletion: true`` -- the shape shipped by
``skills-claude-only/metaswarm-setup/templates/coverage-thresholds.json`` and by
``tools/editor/metaswarm/.coverage-thresholds.json``) the specialist's own criterion goes
green at 80 while the SSOT is red, so the one agent whose job is verifying coverage is
the one that can report a false sufficient.

The invariant pinned here is deliberately narrow and mechanical:

    in these two documents, a line may state a coverage percentage ONLY if it names
    ``.coverage-thresholds.json`` on the same line

which forbids a bare floor while still allowing the repo's established
"``.coverage-thresholds.json`` (SSOT; 80%+ if none)" phrasing. It is checked in BOTH
directions -- the rule may not silently revert to a bare "Minimum Test Coverage: 80%"
either. That revert is not hypothetical: the live snapshot at
``agent-self/config/rules/common/testing.md:23,38`` is still in exactly that state.

``test_detector_fires_on_the_pre_fix_wording`` is the both-states check that
``rules/common/single-signal-verification.md`` requires: it runs the same predicate over
the verbatim pre-fix text and asserts it goes RED, so a green run above is evidence the
documents are clean rather than evidence the detector stopped working.

Wiring: ``ci/tests`` is invoked as a directory by ``.github/workflows/skill-dual-write.yml``
(``python -m pytest ci/tests tools/d001-dual-write/tests -q``) on every pull request, and
this file is additionally named in ``.github/workflows/quality.yml`` so it also runs in the
required lane. There is no repo-wide pytest autodiscovery here, so an unnamed suite would
be dead weight.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The single source of truth every coverage claim in these documents must defer to.
SSOT = ".coverage-thresholds.json"

#: Documents that jointly define the coverage floor for the TDD specialist.
COVERAGE_AUTHORITY_DOCS = (
    "agents/tdd-guide.md",
    "rules/common/testing.md",
)

#: A percentage figure, e.g. ``80%``, ``80 %``, ``100%``.
_PERCENT = re.compile(r"\d+\s*%")

#: Words that make a percentage a *coverage* percentage rather than any other number.
#: ``coverage`` catches the prose lines; the axis names catch the bare
#: ``# Required: 80%+ branches, functions, lines, statements`` comment, which never
#: says "coverage" at all and is exactly the line a coverage-only matcher would miss.
_COVERAGE_CONTEXT = re.compile(r"coverage|branches|functions|statements", re.IGNORECASE)


def bare_floor_lines(text: str) -> list[tuple[int, str]]:
    """Return ``(lineno, line)`` for every coverage floor stated without the SSOT.

    A line offends when it carries a percentage in a coverage context and does NOT
    name ``.coverage-thresholds.json``. Naming the SSOT on the same line is what makes
    ``(SSOT; 80%+ if none)`` legitimate: the fallback is scoped to its authority.
    """
    offenders: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        if not _PERCENT.search(line):
            continue
        if not _COVERAGE_CONTEXT.search(line):
            continue
        if SSOT in line:
            continue
        offenders.append((lineno, line.strip()))
    return offenders


@pytest.mark.parametrize("relpath", COVERAGE_AUTHORITY_DOCS)
def test_document_exists(relpath: str) -> None:
    assert (REPO_ROOT / relpath).is_file(), f"{relpath} is missing"


@pytest.mark.parametrize("relpath", COVERAGE_AUTHORITY_DOCS)
def test_names_the_coverage_ssot(relpath: str) -> None:
    """Each document must point at the threshold file, not at a memorised number."""
    text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert SSOT in text, (
        f"{relpath} never mentions {SSOT}; it therefore has no guard that resolves a "
        f"repository floor above its own hardcoded default"
    )


@pytest.mark.parametrize("relpath", COVERAGE_AUTHORITY_DOCS)
def test_no_bare_coverage_floor(relpath: str) -> None:
    """No line may assert a coverage floor without naming the SSOT on that line."""
    text = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    offenders = bare_floor_lines(text)
    rendered = "\n".join(f"  {relpath}:{n}: {line}" for n, line in offenders)
    assert not offenders, (
        f"{relpath} states a coverage floor without deferring to {SSOT}:\n{rendered}\n"
        f'Use the repo phrasing: "meets `{SSOT}` (SSOT; 80%+ if none defined)".'
    )


def test_tdd_guide_keeps_the_fallback() -> None:
    """The fix must not swing the other way and drop the no-threshold-file fallback.

    A project with no ``.coverage-thresholds.json`` still needs a number, and the repo's
    settled number is ``80%+`` (``rules/common/testing.md:23``).
    """
    text = (REPO_ROOT / "agents/tdd-guide.md").read_text(encoding="utf-8")
    assert "80%" in text, "the 80%+ no-threshold-file fallback was dropped entirely"


# --------------------------------------------------------------------------------------
# Both-states check: prove the predicate above still fires on the state it was written
# to catch, so a green suite is evidence about the documents and not about the detector.
# --------------------------------------------------------------------------------------

#: Verbatim pre-fix wording of the four offending anchors in agents/tdd-guide.md.
PRE_FIX_TDD_GUIDE = """\
---
name: tdd-guide
description: Test-Driven Development specialist. Ensures 80%+ test coverage.
---

## Your Role

- Ensure 80%+ test coverage

### 6. Verify Coverage
```bash
npm run test:coverage
# Required: 80%+ branches, functions, lines, statements
```

## Quality Checklist

- [ ] Coverage is 80%+
"""

#: Verbatim pre-fix wording still live at agent-self/config/rules/common/testing.md.
PRE_FIX_TESTING_RULE = """\
# Testing Requirements

## Minimum Test Coverage: 80%

6. Verify coverage (80%+)
"""


def test_detector_fires_on_the_pre_fix_wording() -> None:
    """All four tdd-guide anchors, and both rule anchors, must be caught."""
    guide_hits = [line for _, line in bare_floor_lines(PRE_FIX_TDD_GUIDE)]
    assert len(guide_hits) == 4, guide_hits
    assert any("description:" in line for line in guide_hits)
    assert any(line == "- Ensure 80%+ test coverage" for line in guide_hits)
    assert any(line.startswith("# Required:") for line in guide_hits)
    assert any(line == "- [ ] Coverage is 80%+" for line in guide_hits)

    rule_hits = [line for _, line in bare_floor_lines(PRE_FIX_TESTING_RULE)]
    assert len(rule_hits) == 2, rule_hits


def test_detector_accepts_the_repo_ssot_phrasing() -> None:
    """The sanctioned "(SSOT; 80%+ if none)" form must NOT be flagged.

    Sampled verbatim from rules/common/code-review.md:57,98 and
    rules/common/development-workflow.md:48 so the predicate stays aligned with the
    phrasing those already-correct documents use.
    """
    sanctioned = (
        "- [ ] Test coverage meets `.coverage-thresholds.json` "
        "(single source of truth; 80%+ if none defined)\n"
        "5. Verify coverage meets `.coverage-thresholds.json` (SSOT; 80%+ if none)\n"
        "## Minimum Test Coverage: per `.coverage-thresholds.json` "
        "(100% on metaswarm; 80%+ where none is defined)\n"
    )
    assert bare_floor_lines(sanctioned) == []
