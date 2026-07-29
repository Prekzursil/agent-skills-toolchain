"""A HIGH-only code review must have ONE merge outcome, not a route-dependent one.

Measured defect (D-a002): ``rules/common/code-review.md`` grades HIGH as ``WARN`` and
its Approval Criteria allow "Only HIGH issues (merge with caution)", while
``agents/python-reviewer.md``, ``agents/typescript-reviewer.md`` and
``commands/code-review.md`` all **Block** on "CRITICAL or HIGH".  A review state of one
HIGH finding and zero CRITICAL findings therefore produced two mutually exclusive
authorizations depending on which surface the reader consulted.

The invariant pinned here is CONDITIONAL, so it survives either resolution:

    IF the common rule still grades a HIGH-only review as mergeable,
    THEN every surface that blocks on HIGH must say, in its own text, that it is
         deliberately stricter and takes precedence.

If a later change makes the common rule block on HIGH too, the precondition goes away
and the test passes without asserting anything about wording it no longer needs to.
That is deliberate: the contract is "no reader can derive two answers", not "these
exact sentences exist forever".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

COMMON_RULE = "rules/common/code-review.md"

# Surfaces that BLOCK on HIGH and therefore contradict a permissive common rule.
BLOCKING_SURFACES = (
    "agents/python-reviewer.md",
    "agents/typescript-reviewer.md",
    "commands/code-review.md",
)

# The common rule's permissive wording for a HIGH-only review.
_PERMISSIVE = re.compile(
    r"only\s+HIGH\s+issues\s*\(\s*merge\s+with\s+caution\s*\)", re.IGNORECASE
)
# A surface that blocks on HIGH.
_BLOCKS_ON_HIGH = re.compile(r"block[^\n.]{0,40}CRITICAL\s+or\s+HIGH", re.IGNORECASE)
# The precedence declaration that makes the outcome single-valued.
_PRECEDENCE = re.compile(r"STRICTER\s+than\s+the\s+general\s+default", re.IGNORECASE)


def _text(rel: str) -> str:
    """File contents with newlines and runs of whitespace collapsed to single spaces.

    The precedence note is a wrapped markdown paragraph, so its phrases straddle line
    breaks; matching the raw bytes would be a line-wrap-sensitive assertion.
    """
    path = REPO_ROOT / rel
    assert path.is_file(), f"missing review surface: {rel}"
    return re.sub(r"\s+", " ", path.read_text(encoding="utf-8", errors="replace"))


def test_common_rule_is_readable():
    """Control: the precondition is derived from a file that really exists."""
    assert _text(COMMON_RULE)


@pytest.mark.parametrize("rel", BLOCKING_SURFACES)
def test_high_only_review_has_one_outcome(rel: str):
    common = _text(COMMON_RULE)
    surface = _text(rel)

    if not _BLOCKS_ON_HIGH.search(surface):
        pytest.skip(f"{rel} no longer blocks on HIGH; nothing to reconcile")

    if not _PERMISSIVE.search(common):
        # The common rule was tightened; the contradiction is gone at the source.
        return

    assert _PRECEDENCE.search(surface), (
        f"{rel} blocks a HIGH-only review while {COMMON_RULE} still allows "
        '"Only HIGH issues (merge with caution)", and it does not say which wins. '
        "A reader gets two mutually exclusive merge authorizations for the same "
        "review state. Either tighten the common rule or state the precedence here."
    )
