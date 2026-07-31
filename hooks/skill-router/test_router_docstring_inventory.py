#!/usr/bin/env python
"""Regression suite: the skill-router module docstring must not hardcode an inventory COUNT.

Defect pinned (C46 / D-a001). ``route.py``'s docstring advertised "the 16 agents, the 64
commands" while ``_build_index()`` globs ``~/.claude/agents/*.md`` and
``~/.claude/commands/**/*.md`` with no cap. Measured against this repo's mirror of that
live directory: 18 agent definitions and 71 command definitions. So the numbers were
already false, and ``rules/common/agents.md:3`` states the policy directly -- "the agent
roster is injected live every session ... do NOT keep a static list (it drifts)."

The implementation was never truncated to sixteen; only the documentation was wrong. That
is exactly why the detector below reads the DOCSTRING, not the behaviour.

KNOWN-BROKEN CONTROL IS MANDATORY. A "no hardcoded count found" result is worthless
unless the same predicate provably fires on the real pre-fix text, so
``PRE_FIX_DOCSTRING_LINE`` holds that byte-exact line and is asserted to trip.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

THIS = Path(__file__).resolve().parent
ROUTE = THIS / "route.py"
REPO = THIS.parent.parent

# The byte-exact clause as it stood at 27fb388, before the C46 fix.
PRE_FIX_DOCSTRING_LINE = (
    "lexical index over ALL routable units — skills (every SKILL.md), "
    "the 16 agents, the 64 commands — by"
)

# "the <N> <unit>s" -- a hardcoded inventory count for a directory the router globs.
_HARDCODED_COUNT = re.compile(
    r"\bthe\s+(\d+)\s+(agents|commands|skills)\b", re.IGNORECASE
)


def _hardcoded_counts(text: str) -> list[tuple[str, str]]:
    """Return every (count, unit) inventory claim in ``text``."""
    return [(m.group(1), m.group(2).lower()) for m in _HARDCODED_COUNT.finditer(text)]


def _module_docstring(path: Path) -> str:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    doc = ast.get_docstring(tree)
    assert doc, f"{path} lost its module docstring"
    return doc


# ----------------------------------------------------------------------------------
# known-positive control -- the detector must SEE the pre-fix defect
# ----------------------------------------------------------------------------------
def test_control_detector_fires_on_pre_fix_text() -> None:
    hits = _hardcoded_counts(PRE_FIX_DOCSTRING_LINE)
    assert ("16", "agents") in hits, (
        "detector is vacuous: it did not flag the pre-fix 'the 16 agents' clause, "
        f"so a clean live result proves nothing. hits={hits}"
    )
    assert ("64", "commands") in hits


def test_control_detector_ignores_non_inventory_numbers() -> None:
    """Polarity check: a number that is not an inventory count must not trip it."""
    assert _hardcoded_counts("Index cached 24h, rebuilt on version bump.") == []
    assert _hardcoded_counts("not the old 8") == []


# ----------------------------------------------------------------------------------
# the live assertion
# ----------------------------------------------------------------------------------
def test_route_docstring_has_no_hardcoded_inventory_count() -> None:
    hits = _hardcoded_counts(_module_docstring(ROUTE))
    assert not hits, (
        "route.py's module docstring hardcodes an inventory count "
        f"{hits}; the index is built by globbing, so any fixed number drifts "
        "(rules/common/agents.md:3). Use count-independent wording."
    )


def test_index_build_is_still_glob_driven() -> None:
    """The premise of the fix: nothing in the router imposes a fixed roster size."""
    src = ROUTE.read_text(encoding="utf-8")
    assert '"agents" / "*.md"' in src, (
        "agent harvest glob moved; re-check the docstring"
    )
    assert '"commands" / "**" / "*.md"' in src, "command harvest glob moved"


def test_repo_mirror_disproves_the_old_numbers() -> None:
    """Second, independent signal that 16/64 were stale: count the mirrored inventory.

    ``scripts/sync-from-live.ps1`` mirrors live ``.claude/agents`` -> repo ``agents/``,
    so these files are the roster the glob at route.py sees.
    """
    agents = sorted((REPO / "agents").glob("*.md"))
    commands = sorted((REPO / "commands").rglob("*.md"))
    assert len(agents) != 16, "if the mirror really is 16, revisit this suite's premise"
    assert len(commands) != 64
    assert len(agents) >= 17 and len(commands) >= 65
