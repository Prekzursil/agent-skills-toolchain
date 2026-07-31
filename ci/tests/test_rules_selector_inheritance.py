"""Selector-inheritance gates for ``rules/`` -- D-a050 (tree-wide) and A043 (pair).

This module carries TWO independently-adjudicated suites that were authored against
the same filename on two branches.  They are complementary, not duplicates: A043 pins
ONE prose-declared ``extends`` pair exactly (including an ``extends``-target check and
a both-states detector control), while D-a050 asserts the mechanical tree-wide
superset invariant across BOTH rule roots.  Neither subsumes the other, so both are
kept whole.

===========================================================================
Part 1 -- D-a050: universal ``common/`` selectors must cover every language
===========================================================================

``rules/README.md`` declares ``common/`` the UNIVERSAL layer and every
``rules/<lang>/`` directory an EXTENSION of it, and each language file repeats
that in prose (``> This file extends [common/testing.md] ...``).  Claude Code
realises that only through the ``paths:`` frontmatter: a conditional rule loads
**only while working with matching files**, so a universal rule whose selector
omits a language's own extensions is simply absent for that language's work.

Measured gap that motivated this suite (both rule roots, at 27fb388): the eight
universal ``rules/common/*.md`` selectors listed 17 extension globs and omitted
20 that language directories declare -- among them every Perl extension
(``.pl .pm .t .psgi .cgi``) and Dart (``.dart``), so a session editing only
``lib/Foo.pm`` or ``main.dart`` loaded the language addendum while the shared
TDD / coverage / review checklist it claims to extend never applied.

The invariant is mechanical on purpose (no judgement, no hand-maintained list):

    for every UNIVERSAL common rule file,
        {extension globs it selects} >= {extension globs any language dir selects}

SCOPE, stated so a reader does not over-read the gate:
  * Only ``**/*.<ext>``-shaped globs participate.  Named-file globs a language
    dir also declares (``**/pom.xml``, ``**/go.mod``, ``**/composer.json``,
    ``**/CMakeLists.txt``, ``**/Package.swift``, ``**/pubspec.yaml``, ...) are
    deliberately NOT pushed into the universal layer -- whether editing only a
    build manifest should pull in the full review/testing checklist is a policy
    question this gate does not decide.  Settling experiment: add one such glob
    to ``rules/common/testing.md`` and observe whether the loaded rule set for a
    manifest-only session reads as helpful or as noise.
  * "Universal" is detected STRUCTURALLY (``_ANCHORS`` below), not by filename,
    so deliberately narrow common rules keep their narrow selectors:
    ``static-analyzer.md`` (py/ts only, by its own charter), ``ci-hygiene.md``,
    ``hooks.md`` (``**/hooks/**``), ``owner-ops-authorization.md`` (``**/*``).
    Language ``hooks.md`` files say they extend ``common/hooks.md``; that is a
    documentation cross-reference, NOT a selector obligation, and is out of
    scope here.

==========================================================================
Part 2 -- A043: a rule that claims to EXTEND another must be loadable with it
==========================================================================

``rules/*/*.md`` files carry ``paths:`` frontmatter, and a rule is only loaded when
the file being edited matches one of its globs. That gating is not theoretical: the
repo relies on it deliberately -- ``rules/README.md`` sets
``paths: - "**/*.__never_load__"``, an intentional never-match whose only purpose is
to keep the README out of agent context.

So when ``rules/kotlin/patterns.md`` selects BOTH ``**/*.kt`` and ``**/*.kts`` while
declaring "this file extends common/patterns.md", but ``rules/common/patterns.md``
selects only ``**/*.kt``, then editing ``app/build.gradle.kts`` loads the Kotlin
extension WITHOUT its declared base. The ``extends`` sentence is false for ``.kts``,
and the base guidance (skeleton-projects, repository-pattern, API-response-format)
silently never reaches the agent. Rule precedence cannot rescue it: precedence only
orders rules that BOTH matched.

Scope of what this part pins, stated narrowly on purpose: the
``rules/kotlin/patterns.md -> rules/common/patterns.md`` pair, which is the state that
was adjudicated. A generic probe over all 12 language directories found the same shape
in 57 (language-file, common-base) pairs, and this part deliberately does NOT assert
that whole-tree invariant on the ``extends`` prose. Two disclosed residuals, neither
fixed here:

* ``kotlin/coding-style.md``, ``kotlin/security.md`` and ``kotlin/testing.md`` have the
  IDENTICAL ``.kts`` gap against their own common counterparts. The one-line fix is the
  same, but it edits three ``rules/common/`` files outside this change's ownership.
* The other 11 language directories mix genuine source-extension gaps (``.pyi``,
  ``.csx``, ``.hpp``, ``.dart``, ``.scss``, ...) with build-manifest globs
  (``**/go.mod``, ``**/CMakeLists.txt``, ``**/composer.json``) whose exclusion from a
  source-scoped common rule is plausibly intended. Separating those is a per-glob
  judgement call.

Settling work for both: extend ``PAIRS`` after deciding, per glob, whether the base
rule should select it -- the helpers below are already generic over any pair.

``test_detector_fires_on_a_synthetic_broken_pair`` is the both-states control required
by ``rules/common/single-signal-verification.md``: a green assertion is only evidence
if the same helper is shown to go RED against a known-broken input.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
#: A043 alias for the same root; both names are kept so each suite reads as authored.
REPO_ROOT = REPO
RULES = REPO_ROOT / "rules"

# ---------------------------------------------------------------------------
# Part 1 -- D-a050: universal common selectors vs every language extension
# ---------------------------------------------------------------------------

# Both tracked rule roots.  ``agent-self/config/rules`` is the committed deploy
# snapshot of the live ``~/.claude/rules``; it carries the same frontmatter and
# regresses independently, so it is gated too.
RULE_ROOTS = ("rules", "agent-self/config/rules")

_FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.S)
_GLOB = re.compile(r'-\s*"([^"]+)"')
_EXTENSION_GLOB = re.compile(r"\A\*\*/\*\.[A-Za-z0-9_+-]+\Z")

# A common rule is UNIVERSAL when it already spans these mutually unrelated
# language families.  Derived from the shipped selectors, not asserted about
# them: a narrow-by-charter common rule cannot accidentally satisfy this.
_ANCHORS = frozenset(
    {"**/*.py", "**/*.ts", "**/*.js", "**/*.go", "**/*.java", "**/*.swift", "**/*.kt"}
)


def _globs(path: Path) -> list[str]:
    """The ``paths:`` globs declared in *path*'s YAML frontmatter (may be empty)."""
    match = _FRONTMATTER.match(path.read_text(encoding="utf-8"))
    return _GLOB.findall(match.group(1)) if match else []


def _language_extension_globs(root: Path) -> dict[str, set[str]]:
    """Map each extension glob a language dir selects -> the dirs declaring it."""
    found: dict[str, set[str]] = {}
    for directory in sorted(root.iterdir()):
        if not directory.is_dir() or directory.name == "common":
            continue
        for rule_file in sorted(directory.glob("*.md")):
            for glob in _globs(rule_file):
                if _EXTENSION_GLOB.match(glob):
                    found.setdefault(glob, set()).add(directory.name)
    return found


def _universal_common_files(root: Path) -> list[Path]:
    return [
        f for f in sorted((root / "common").glob("*.md")) if _ANCHORS <= set(_globs(f))
    ]


@pytest.mark.parametrize("root_name", RULE_ROOTS)
def test_rule_roots_are_discoverable(root_name: str):
    """Guard the detector: a typo'd root must fail loudly, not vacuously pass."""
    root = REPO / root_name
    assert root.is_dir(), f"missing rule root {root_name}"
    languages = _language_extension_globs(root)
    assert len(languages) >= 20, (
        f"{root_name}: only {len(languages)} language extension globs parsed - "
        "the frontmatter parser is probably broken, not the rules"
    )
    universal = _universal_common_files(root)
    assert universal, f"{root_name}: no universal common rule detected"


@pytest.mark.parametrize("root_name", RULE_ROOTS)
def test_universal_common_rules_cover_every_language_extension(root_name: str):
    """A universal rule must match every extension a language dir claims to extend."""
    root = REPO / root_name
    languages = _language_extension_globs(root)
    gaps: list[str] = []
    for rule_file in _universal_common_files(root):
        missing = sorted(set(languages) - set(_globs(rule_file)))
        if missing:
            owners = sorted({d for g in missing for d in languages[g]})
            gaps.append(
                f"{rule_file.relative_to(REPO).as_posix()} omits {missing} "
                f"(declared by {owners})"
            )
    assert not gaps, (
        "universal common rules do not load for every supported language:\n  "
        + "\n  ".join(gaps)
    )


def test_both_rule_roots_agree_on_the_universal_selector():
    """The deploy snapshot must not drift from ``rules/`` on the shared selector."""
    selectors = {}
    for root_name in RULE_ROOTS:
        root = REPO / root_name
        for rule_file in _universal_common_files(root):
            selectors.setdefault(rule_file.name, {})[root_name] = sorted(
                _globs(rule_file)
            )
    for name, per_root in sorted(selectors.items()):
        if len(per_root) < len(RULE_ROOTS):
            continue  # file exists in only one root - not a drift signal
        distinct = {tuple(v) for v in per_root.values()}
        assert len(distinct) == 1, f"{name}: selector drift between rule roots"


# ---------------------------------------------------------------------------
# Part 2 -- A043: the adjudicated kotlin/patterns.md -> common/patterns.md pair
# ---------------------------------------------------------------------------

#: Language rule -> the common rule its prose claims to extend. Only the adjudicated
#: pair; its selectors are pure source extensions (``.kt``/``.kts``) with no
#: build-manifest glob to adjudicate. See the module docstring for the residuals.
PAIRS = [
    ("kotlin/patterns.md", "common/patterns.md"),
]

FRONTMATTER = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n", re.DOTALL)
GLOB = re.compile(r'^\s*-\s*"([^"]+)"\s*$')
EXTENDS = re.compile(r"extends \[([^\]]+)\]\(([^)]+)\)")


def selector_globs(text: str) -> list[str]:
    """Return the ``paths:`` globs declared in a rule's YAML frontmatter."""
    match = FRONTMATTER.match(text)
    if match is None:
        return []
    return [
        m.group(1) for line in match.group(1).splitlines() if (m := GLOB.match(line))
    ]


def extends_target(text: str) -> str | None:
    """Return the relative path a rule's prose claims to extend, if any."""
    match = EXTENDS.search(text)
    return match.group(2) if match else None


def unloadable_globs(lang_globs: list[str], base_globs: list[str]) -> list[str]:
    """Globs the extension selects but its declared base does not.

    Every entry is a concrete file kind for which the extension loads ALONE, so the
    ``extends`` claim does not hold for it.
    """
    return [g for g in lang_globs if g not in base_globs]


def read(rel: str) -> str:
    return (RULES / rel).read_text(encoding="utf-8")


def test_detector_fires_on_a_synthetic_broken_pair() -> None:
    """Both-states control: prove the helper reports a real gap before trusting a pass."""
    assert unloadable_globs(["**/*.kt", "**/*.kts"], ["**/*.kt"]) == ["**/*.kts"]
    assert unloadable_globs(["**/*.kt"], ["**/*.kt", "**/*.kts"]) == []


def test_frontmatter_parser_handles_a_rule_with_no_frontmatter() -> None:
    assert selector_globs("# Title\n\nbody\n") == []
    assert extends_target("# Title\n\nbody\n") is None


def test_kts_is_selected_by_the_common_patterns_rule() -> None:
    """The direct A043 regression: ``.kts`` must reach ``common/patterns.md``."""
    assert "**/*.kts" in selector_globs(read("common/patterns.md"))


@pytest.mark.parametrize(("lang_rel", "base_rel"), PAIRS)
def test_rule_selectors_are_covered_by_their_declared_base(
    lang_rel: str, base_rel: str
) -> None:
    lang_text = read(lang_rel)
    claimed = extends_target(lang_text)
    assert claimed is not None, (
        f"rules/{lang_rel} no longer declares an extends target; this pairing is "
        "asserted here, so removing the claim must be a deliberate, visible edit."
    )
    assert (RULES / lang_rel).parent.joinpath(claimed).resolve() == (
        RULES / base_rel
    ).resolve(), f"rules/{lang_rel} extends {claimed}, expected {base_rel}"

    gaps = unloadable_globs(selector_globs(lang_text), selector_globs(read(base_rel)))
    assert gaps == [], (
        f"rules/{lang_rel} selects {gaps} but rules/{base_rel} does not, so editing "
        f"such a file loads the extension without the base it claims to extend. Add "
        f"the glob to rules/{base_rel} or narrow the extends claim."
    )


if __name__ == "__main__":  # pragma: no cover - convenience runner
    raise SystemExit(pytest.main([__file__, "-q"]))
