"""Selector-inheritance gate for ``rules/`` (D-a050).

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
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

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
