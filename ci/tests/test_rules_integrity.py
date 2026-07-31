"""Integrity gate for the checked-in ``rules/`` tree.

Nothing in CI policed ``rules/`` before this suite: ``.github/workflows/quality.yml``
runs ruff, basedpyright, npm, pytest and opengrep, and none of them reads markdown.
Every invariant below was therefore unpoliced -- and every one of them was found
BROKEN at 27fb388.

What these tests can and cannot do (stated up front, because the artifact under
test is prose): a rule file is instructions for a model, so the only available
oracle is the TEXT CONTRACT. These assertions prove the written contract has a
satisfying value; they cannot prove an agent obeys it. The one exception is
:func:`test_relative_markdown_links_resolve`, which is a pure filesystem
algorithm with no judgement in it.

Each text-contract predicate ships a KNOWN-BROKEN control (the
``*_control_fires_on_the_broken_text`` tests). A predicate that stays silent in
the broken state measures nothing -- that is the both-states rule this repo
already applies to its other gates (``rules/common/single-signal-verification.md``,
cited by ``quality.yml`` at the claim-verify-gate step).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RULES = REPO / "rules"

# ``[text](target)`` -- non-greedy, and the target may not contain whitespace or
# a closing paren, which keeps image/nested-bracket noise out.
_LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
_FENCE = re.compile(r"^\s*(?:```|~~~)")


def _strip_fenced_blocks(text: str) -> str:
    """Blank out fenced code blocks, keeping line numbers stable.

    A link inside a fence is a TEMPLATE for some other file (``rules/README.md``
    line 89 shows exactly that), not a link rendered from this file, so it must
    not be resolved against this file's directory.
    """
    out: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if _FENCE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def _relative_links(path: Path) -> list[tuple[int, str]]:
    body = _strip_fenced_blocks(path.read_text(encoding="utf-8"))
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(body.splitlines(), start=1):
        for target in _LINK.findall(line):
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            found.append((lineno, target.split("#", 1)[0]))
    return found


def _section(text: str, heading: str) -> str:
    """Return ``heading`` and everything up to the next same-level heading."""
    lines = text.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    start = next((i for i, ln in enumerate(lines) if ln.startswith(heading)), None)
    if start is None:
        return ""
    for i in range(start + 1, len(lines)):
        stripped = lines[i].lstrip("#")
        depth = len(lines[i]) - len(stripped)
        if depth == level and lines[i].startswith("#"):
            return "\n".join(lines[start:i])
    return "\n".join(lines[start:])


# --------------------------------------------------------------------------
# A027 -- a relative link in rules/ must resolve to a file that exists.
# --------------------------------------------------------------------------


def test_relative_markdown_links_resolve() -> None:
    """Every relative markdown link under ``rules/`` points at a real file.

    Broken at 27fb388: ``rules/README.md`` rendered
    ``[common/coding-style.md](../common/coding-style.md)``, which resolves from
    ``rules/`` to ``<repo>/common/coding-style.md`` -- a 404. The prefix is only
    correct from ``rules/<language>/``.
    """
    broken: list[str] = []
    checked = 0
    for md in sorted(RULES.rglob("*.md")):
        for lineno, target in _relative_links(md):
            checked += 1
            if not (md.parent / target).resolve().exists():
                rel = md.relative_to(REPO).as_posix()
                broken.append(f"{rel}:{lineno} -> {target}")
    # Detector control: the walk must actually have found links to check.
    assert checked > 50, f"link extractor found only {checked} links -- broken walk"
    assert not broken, "unresolvable relative links:\n  " + "\n  ".join(broken)


# --------------------------------------------------------------------------
# A063 -- the precedence contract must be visible where the conflict loads.
# --------------------------------------------------------------------------

_LANGUAGE_NOTE = "**Language note**"


def _promises_language_note(readme: str) -> bool:
    return _LANGUAGE_NOTE in _section(readme, "### Common rules with override notes")


def test_common_immutability_rule_carries_the_promised_language_note() -> None:
    """The override marker ``rules/README.md`` promises must actually exist.

    ``rules/README.md`` is scoped to ``**/*.__never_load__``, so its "Rule
    Priority" text never enters a session. The only precedence signal that CAN
    load with the conflicting rule is the "Language note" marker the README
    promises -- and at 27fb388 that marker appeared 0 times anywhere under
    ``rules/common/``. An agent editing ``src/server.rs`` therefore loaded the
    common "NEVER mutate" absolute and ``rules/rust/coding-style.md``'s
    ``let mut`` permission with nothing in context to rank them.
    """
    readme = (RULES / "README.md").read_text(encoding="utf-8")
    assert _promises_language_note(readme), "README no longer promises the marker"

    common = (RULES / "common" / "coding-style.md").read_text(encoding="utf-8")
    immutability = _section(common, "## Immutability")
    assert immutability, "common/coding-style.md lost its Immutability section"
    assert _LANGUAGE_NOTE in immutability, (
        "rules/common/coding-style.md Immutability carries no 'Language note' "
        "marker, so the README's precedence promise is unreachable in context"
    )


def test_language_note_control_fires_on_the_broken_text() -> None:
    """Known-broken control for the marker predicate (both-states rule)."""
    assert _LANGUAGE_NOTE not in _section("## Immutability\n\nNEVER mutate.\n", "## I")


# --------------------------------------------------------------------------
# A031 -- the README's Go override example must be backed by the Go rule.
# --------------------------------------------------------------------------

# The two tokens may straddle a wrapped line, so the gap spans newlines -- but it
# is bounded, or "override" in one section would match a path in the next.
_MUTATION_OVERRIDE = re.compile(
    r"overrides?\b[\s\S]{0,120}?common/coding-style\.md", re.IGNORECASE
)


def _declares_override_of_common_coding_style(text: str) -> bool:
    return bool(_MUTATION_OVERRIDE.search(text))


def test_go_coding_style_actually_overrides_the_immutability_absolute() -> None:
    """``rules/README.md`` names a Go override that must exist in the Go rule.

    README lines 100-104 say ``golang/coding-style.md`` "can override" the
    common immutability principle. At 27fb388 that file was 32 lines long and
    contained no mutation, pointer-receiver or override provision at all, while
    ``rules/golang/patterns.md`` prescribed ``Option func(*Server)`` --
    a constructor whose options MUST mutate. Following the unqualified common
    ban while keeping that signature returns the default port 8080 instead of
    the requested 9090.
    """
    go_style = (RULES / "golang" / "coding-style.md").read_text(encoding="utf-8")
    assert _declares_override_of_common_coding_style(go_style), (
        "rules/golang/coding-style.md declares no override of "
        "common/coding-style.md, but rules/README.md advertises one"
    )
    assert "pointer receiver" in go_style.lower(), (
        "the Go override must name the pointer-receiver idiom the README cites"
    )


def test_go_override_control_fires_on_the_broken_text() -> None:
    """Known-broken control: the 27fb388 body must NOT satisfy the predicate."""
    broken = "# Go Coding Style\n\n> This file extends common/coding-style.md.\n"
    assert not _declares_override_of_common_coding_style(broken)
    # ... and the bound holds: 'override' far from the path must not match.
    assert not _declares_override_of_common_coding_style(
        "overrides something else.\n" + "x" * 200 + "\ncommon/coding-style.md\n"
    )
    assert _declares_override_of_common_coding_style(
        "overrides the rule in\n[common/coding-style.md](../common/coding-style.md)"
    )


# --------------------------------------------------------------------------
# A075 -- the coverage SSOT must outrank an agent's hard-coded default.
# --------------------------------------------------------------------------

_SSOT = ".coverage-thresholds.json"


def _ssot_outranks_agent_defaults(testing_md: str) -> bool:
    """True when the rule subordinates tdd-guide's flat 80% to the SSOT."""
    return (
        _SSOT in testing_md
        and "tdd-guide" in testing_md
        and re.search(r"80%[^\n]*fallback|fallback[^\n]*80%", testing_md) is not None
    )


def test_coverage_ssot_outranks_the_tdd_guide_hardcoded_default() -> None:
    """The named support agent's 80% must be a floor, never a pass mark.

    ``rules/common/testing.md`` declares ``.coverage-thresholds.json`` the SSOT
    and names **tdd-guide** as the support agent; ``agents/tdd-guide.md`` then
    promises a flat "80%+" and never reads that file. With
    ``tools/editor/metaswarm/.coverage-thresholds.json`` at 100 on all four
    metrics, a project at 80% is PASS under the agent and FAIL under the SSOT.
    """
    testing_md = (RULES / "common" / "testing.md").read_text(encoding="utf-8")
    assert _ssot_outranks_agent_defaults(testing_md), (
        "rules/common/testing.md names tdd-guide but never subordinates its "
        f"flat 80% to {_SSOT}, so the same state yields PASS and FAIL"
    )


def test_coverage_ssot_control_fires_on_the_broken_text() -> None:
    """Known-broken control: the 27fb388 wording must NOT satisfy it."""
    broken = (
        f"## Minimum Test Coverage: per `{_SSOT}` (100% on metaswarm; 80%+ "
        "where none is defined)\n\n- **tdd-guide** - Use PROACTIVELY\n"
    )
    assert not _ssot_outranks_agent_defaults(broken)


# --------------------------------------------------------------------------
# A035 -- an awaited >60s cross-vendor dispatch needs one compliant launch mode.
# --------------------------------------------------------------------------

AGENTS_MD = REPO / "agent-self" / "config" / "AGENTS.md"
DISPATCH_MD = RULES / "common" / "cross-vendor-dispatch.md"


def _agents_requires_background_over_60s(text: str) -> bool:
    section = _section(text, "## 4a.")
    return "run_in_background" in section and "never a blocking foreground call" in text


def _dispatch_forbids_background_outright(text: str) -> bool:
    """True when rule 1 bans backgrounding with no joined-background carve-out."""
    section = _section(text, "## 1.")
    bans = "NEVER" in section and "run_in_background" in section
    carve_out = "longrun" in section and "COMPLIANT" in section
    return bans and not carve_out


def _compliant_launch_modes(agents_md: str, dispatch_md: str) -> set[str]:
    """Launch modes satisfying BOTH documents for a 300s awaited dispatch."""
    needs_bg = _agents_requires_background_over_60s(agents_md)
    bans_bg = _dispatch_forbids_background_outright(dispatch_md)
    modes = set()
    for mode in ("foreground", "background"):
        if needs_bg and mode == "foreground":
            continue
        if bans_bg and mode == "background":
            continue
        modes.add(mode)
    return modes


def test_awaited_long_cross_vendor_dispatch_has_a_compliant_launch_mode() -> None:
    """A 300s awaited Codex generation must have at least one legal launch mode.

    At 27fb388 it had none. ``agent-self/config/AGENTS.md`` section 4a: any op
    over 60s -- expressly including "long Codex generations" -- MUST use
    ``run_in_background``/``Monitor`` and "never a blocking foreground call".
    ``rules/common/cross-vendor-dispatch.md`` rule 1: NEVER ``run_in_background``
    for a dispatch a barrier awaits. Foreground violates the first, background
    violates the second.
    """
    agents_md = AGENTS_MD.read_text(encoding="utf-8")
    dispatch_md = DISPATCH_MD.read_text(encoding="utf-8")
    modes = _compliant_launch_modes(agents_md, dispatch_md)
    assert modes, (
        "duration=300s awaited=True: AGENTS.md 4a requires background and "
        "cross-vendor-dispatch rule 1 forbids it -- no compliant launch mode"
    )


def test_launch_mode_control_fires_on_the_broken_text() -> None:
    """Known-broken control: the 27fb388 pair must yield the empty set."""
    agents_broken = (
        "## 4a. Wrap long operations\n\n- MUST run via `longrun` with\n"
        "  `run_in_background`/`Monitor` -- never a blocking foreground call.\n"
    )
    dispatch_broken = (
        "## 1. A work-unit dispatch MUST block.\n\n"
        "- NEVER `--background` or `run_in_background` for an awaited dispatch.\n"
    )
    assert _agents_requires_background_over_60s(agents_broken)
    assert _dispatch_forbids_background_outright(dispatch_broken)
    assert _compliant_launch_modes(agents_broken, dispatch_broken) == set()
