"""A043 -- a language rule that claims to EXTEND a common rule must be loadable
together with it.

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

Scope of what this suite pins, stated narrowly on purpose: the
``rules/kotlin/patterns.md -> rules/common/patterns.md`` pair, which is the state that
was adjudicated. A generic probe over all 12 language directories found the same shape
in 57 (language-file, common-base) pairs, and this suite deliberately does NOT assert
that whole-tree invariant. Two disclosed residuals, neither fixed here:

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

REPO_ROOT = Path(__file__).resolve().parents[2]
RULES = REPO_ROOT / "rules"

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
