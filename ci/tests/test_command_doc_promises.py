"""Gate: a published command doc must not delegate to a skill that exists nowhere.

WHY THIS EXISTS
---------------
The recurring defect class on this estate is *documentation that names a
capability the code does not deliver*. ``commands/rollback.md`` promises an
automatic pre-edit checkpoint whose producer is undeployed; a ``claude-science``
SKILL.md documented a falsification probe ``install.ps1`` never deployed, and the
copy loop was ``if (Test-Path $src)`` guarded so the omission was **silent**.

This gate closes the mechanically-checkable half of that class. A command doc
that says *"Run the X skill (`skills/X/SKILL.md`)"* makes a promise a machine can
resolve: either a ``SKILL.md`` for ``X`` exists in some skill root, or the
command is 100% delegation to a void. Measured at the commit that introduced this
file: **6** such references across **72** tracked ``commands/*.md``, of which
exactly **1** — ``commands/context-budget.md`` -> ``skills/context-budget/SKILL.md``
— resolved nowhere, in the repo or in the live deploy trees
(``~/.claude/skills``, ``~/.agents/skills``). It was fixed by making the command
self-contained in the same change.

WHY THE RESOLVER IS MULTI-ROOT (this is the part that must not be "simplified")
------------------------------------------------------------------------------
A naive resolver that only checks ``<repo>/skills/<name>/SKILL.md`` reports
**3** misses, not 1. The other two are FALSE:

* ``commands/external-tools-health.md`` -> ``skills/external-tools/SKILL.md``
* ``commands/start-task.md``            -> ``skills/plan-review-gate/SKILL.md``

Both files are vendored copies of **metaswarm plugin** commands, and metaswarm
carries its own ``.claude-plugin/plugin.json``. Their references are
*plugin-root-relative* and resolve at
``tools/editor/metaswarm/skills/<name>/SKILL.md``. Reporting them would have been
a 3x overclaim against documentation that is correct — the use-vs-mention trap in
its path-context form. So resolution is a **suffix match against every tracked
path**, and ``test_multi_root_resolution_is_load_bearing`` fails if anyone
narrows it back to a single root.

WHAT THIS GATE DELIBERATELY DOES NOT DO
---------------------------------------
It does not lint command docs for dead PATH mentions generally. Measured over the
same 72 docs: **39** distinct backtick-quoted repo-relative paths do not resolve,
and the overwhelming majority are legitimate — user-supplied templates
(``path/to/file.ts``, ``src/components/ComponentName.tsx``), runtime-generated
artifacts (``.metaswarm/project-profile.json``, ``.beads/plans/active-plan.md``),
and other projects' layouts (``node_modules/vite/bin/vite.js``). A linter over
that surface would be dominated by false positives and disabled within a week.
Only the delegation promise — which names a specific artifact the command cannot
function without — is gated.

It also does not gate ``${CLAUDE_PLUGIN_ROOT}`` references inside ``hooks.json``.
That surface was measured here and is a real, larger finding (24 of 26 command
entries in ``hooks/hooks.json`` name ``scripts/hooks/*.js`` files that are absent
from VCS and present only in ``~/.claude/scripts/hooks/``) — but it belongs to
the hook-audit lane, not to a docs gate, and it cannot be made green by this lane.
It is routed in ``docs/_LANE-DOCS-BUILD-R4.md`` rather than gated red here.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

#: ``skills/<name>/SKILL.md`` inside backticks, optionally with a ``./`` prefix.
SKILL_REF = re.compile(r"`(?:\./)?skills/([A-Za-z0-9._-]+)/SKILL\.md`")

#: Frozen test data: a fixture of a ``$HOME`` tree, whose BYTES are what the
#: routing tests measure. Editing it would change the measurement, so its stale
#: copy of a command doc is excluded by path rather than fixed.
EXCLUDED_PREFIXES = ("platform/routing/fixtures/",)

#: Plausibility floors. A regex that silently stops matching would otherwise
#: report a clean pass over an empty corpus -- the "measurement collapsed to
#: zero, gate reports green" failure. Measured 72 docs / 6 refs; floors sit
#: below that with room for ordinary churn.
MIN_COMMAND_DOCS = 55
MIN_SKILL_REFS = 4

#: Phrases that make a reference a MENTION (a statement *about* the artifact)
#: rather than a USE (an instruction to load it). A retirement sentence naming
#: the path it retired is correct documentation, not a broken promise.
#:
#: This filter is not optional politeness -- the first version of this gate
#: flagged the very sentence that FIXED the defect it was built for
#: ("...pointed at `skills/context-budget/SKILL.md`, which has never existed"),
#: reproducing the use-vs-mention error inside the lane whose subject is
#: use-vs-mention. Scope is deliberately narrow: only the SENTENCE containing
#: the reference is inspected, and only explicit statements about existence
#: count. ``test_control_mention_filter_does_not_swallow_a_real_use`` pins that
#: the filter cannot suppress a genuine delegation.
MENTION_MARKERS = (
    "never existed",
    "does not exist",
    "did not exist",
    "no longer exists",
    "there is no",
    "has been removed",
    "was removed",
    "has been retired",
    "was retired",
    "was deleted",
)


def _tracked_paths() -> frozenset[str]:
    out = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return frozenset(out.replace("\\", "/").splitlines())


def _command_docs(tracked: frozenset[str]) -> list[str]:
    return sorted(
        p
        for p in tracked
        if "commands/" in p
        and p.endswith(".md")
        and not p.startswith(EXCLUDED_PREFIXES)
    )


def _sentence_around(text: str, start: int, end: int) -> str:
    """The single sentence containing ``text[start:end]``.

    Bounded first by the blank line (paragraph) around the match, then by
    sentence-terminating punctuation inside it. Keeping the window this tight is
    what stops a negation elsewhere in the paragraph from suppressing a genuine
    delegation two sentences away.
    """
    para_start = text.rfind("\n\n", 0, start) + 2 if "\n\n" in text[:start] else 0
    para_end = text.find("\n\n", end)
    para_end = len(text) if para_end == -1 else para_end
    para = text[para_start:para_end]
    rel_start, rel_end = start - para_start, end - para_start

    flat = para.replace("\r\n", " ").replace("\n", " ")
    left = max(flat.rfind(". ", 0, rel_start), flat.rfind("! ", 0, rel_start))
    left = 0 if left == -1 else left + 2
    right = flat.find(". ", rel_end)
    right = len(flat) if right == -1 else right + 1
    return flat[left:right]


def _is_mention(sentence: str) -> bool:
    """Is this reference a statement ABOUT the artifact rather than a USE of it?"""
    low = sentence.lower()
    return any(marker in low for marker in MENTION_MARKERS)


def _skill_references(
    tracked: frozenset[str], *, include_mentions: bool = False
) -> list[tuple[str, int, str]]:
    """Every ``(doc, line, skill_name)`` delegation promise in a command doc."""
    refs: list[tuple[str, int, str]] = []
    for rel in _command_docs(tracked):
        # newline="" so line endings are never rewritten on read; line numbers
        # are counted on the raw text.
        text = (REPO_ROOT / rel).read_text(encoding="utf-8", newline="")
        for match in SKILL_REF.finditer(text):
            if not include_mentions and _is_mention(
                _sentence_around(text, match.start(), match.end())
            ):
                continue
            line = text[: match.start()].count("\n") + 1
            refs.append((rel, line, match.group(1)))
    return refs


def _resolves(skill: str, tracked: frozenset[str], *, multi_root: bool = True) -> bool:
    """Does ``skills/<skill>/SKILL.md`` resolve under ANY tracked skill root?"""
    suffix = f"skills/{skill}/SKILL.md"
    if not multi_root:
        return suffix in tracked
    return any(p == suffix or p.endswith("/" + suffix) for p in tracked)


@pytest.fixture(scope="module")
def tracked() -> frozenset[str]:
    return _tracked_paths()


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------


def test_corpus_is_not_empty(tracked: frozenset[str]) -> None:
    """A collapsed corpus must fail loudly instead of passing vacuously."""
    docs = _command_docs(tracked)
    assert len(docs) >= MIN_COMMAND_DOCS, (
        f"only {len(docs)} command docs discovered (floor {MIN_COMMAND_DOCS}); "
        "the discovery glob is broken, so any 'no violations' result below is "
        "measuring an empty set"
    )


def test_skill_reference_extraction_is_not_empty(tracked: frozenset[str]) -> None:
    """A regex that stopped matching must fail loudly, not report zero misses."""
    refs = _skill_references(tracked)
    assert len(refs) >= MIN_SKILL_REFS, (
        f"only {len(refs)} skill delegation references extracted (floor "
        f"{MIN_SKILL_REFS}); SKILL_REF no longer matches the doc convention, so "
        "a clean result below would be a false green"
    )


def test_no_command_doc_delegates_to_a_missing_skill(tracked: frozenset[str]) -> None:
    """The gate proper: every delegation promise must resolve somewhere."""
    broken = [
        (doc, line, skill)
        for doc, line, skill in _skill_references(tracked)
        if not _resolves(skill, tracked)
    ]
    assert not broken, (
        "command docs promising a skill that exists in no skill root:\n"
        + "\n".join(
            f"  {doc}:{line} -> skills/{skill}/SKILL.md" for doc, line, skill in broken
        )
    )


def test_context_budget_command_is_self_contained(tracked: frozenset[str]) -> None:
    """Regression pin for the defect this gate was built on.

    ``/context-budget`` delegated every phase to ``skills/context-budget/SKILL.md``
    while stating "The skill handles all scanning logic, token estimation, issue
    detection, and report formatting" -- a command that was 100% delegation to a
    file that has never existed. Pinned so a future edit cannot restore the
    delegation without also creating the skill.
    """
    doc = "commands/context-budget.md"
    assert doc in tracked, f"{doc} is no longer tracked"
    assert not _resolves("context-budget", tracked), (
        "a context-budget skill now exists -- good. Restore the delegation in "
        f"{doc} and delete this assertion."
    )
    uses = [r for r in _skill_references(tracked) if r[0] == doc]
    assert not uses, (
        f"{doc} again DELEGATES to a skill that does not exist: {uses}. The "
        "command must carry its own phases, or the skill must be created."
    )
    # The doc is allowed -- and expected -- to NAME the retired path in its
    # explanatory sentence. Assert that is exactly what is there, so this test
    # cannot be satisfied by silently deleting the explanation.
    all_refs = [
        r for r in _skill_references(tracked, include_mentions=True) if r[0] == doc
    ]
    assert all_refs, (
        f"{doc} no longer explains that skills/context-budget/SKILL.md never "
        "existed; keep the retirement sentence so the history is not lost"
    )


# --------------------------------------------------------------------------
# Detector controls -- each must distinguish the two hypotheses, not merely
# prove the instrument ran.
# --------------------------------------------------------------------------


def test_control_negative_absent_skill_fires(tracked: frozenset[str]) -> None:
    """KNOWN-BROKEN state: a skill that cannot exist must be reported missing.

    Without this, a resolver that returns True unconditionally would make
    ``test_no_command_doc_delegates_to_a_missing_skill`` pass forever.
    """
    fake = "zzz-skill-that-does-not-exist-r4-control"
    assert not _resolves(fake, tracked), (
        "the resolver accepted a skill name that cannot exist; it is inert and "
        "the gate above proves nothing"
    )


def test_control_positive_present_skill_resolves(tracked: frozenset[str]) -> None:
    """KNOWN-GOOD state: a skill that plainly exists must resolve.

    Pairs with the negative control: together they show the resolver
    discriminates rather than always answering the same way.
    """
    assert _resolves("multi-ai-mingle", tracked), (
        "skills/multi-ai-mingle/SKILL.md no longer resolves; the resolver is "
        "over-strict and would manufacture false defects"
    )


def test_multi_root_resolution_is_load_bearing(tracked: frozenset[str]) -> None:
    """Two-hypothesis control for the resolver's ROOT SET.

    H1 (single root): only ``<repo>/skills/`` counts.
    H2 (multi root):  any tracked ``.../skills/<name>/SKILL.md`` counts.

    ``plan-review-gate`` exists ONLY under ``tools/editor/metaswarm/skills/``.
    Under H1 it reads as a broken promise; under H2 it resolves. The two
    hypotheses therefore produce DIFFERENT results here, which is what makes
    this a control rather than a readability check -- a PASS that looks the same
    under both hypotheses would prove only that the file was readable.
    """
    assert not _resolves("plan-review-gate", tracked, multi_root=False), (
        "plan-review-gate now exists under <repo>/skills/ too; this control no "
        "longer discriminates and must be re-pointed at a still-plugin-only skill"
    )
    assert _resolves("plan-review-gate", tracked, multi_root=True), (
        "multi-root resolution regressed to a single root. That change would "
        "report commands/start-task.md and commands/external-tools-health.md as "
        "broken promises -- both are FALSE, they resolve under the metaswarm "
        "plugin root"
    )


def test_control_injected_broken_promise_is_detected(tracked: frozenset[str]) -> None:
    """End-to-end both-states control over the real extraction path.

    Runs the regex + resolver over synthetic doc text rather than a mutated file
    on disk, so it exercises extraction and resolution together without writing
    to the tree.
    """
    good = "Run the **multi-ai-mingle** skill (`skills/multi-ai-mingle/SKILL.md`) now."
    bad = "Run the **ghost** skill (`skills/zzz-ghost-skill-r4/SKILL.md`) now."

    good_names = SKILL_REF.findall(good)
    bad_names = SKILL_REF.findall(bad)
    assert good_names == ["multi-ai-mingle"], (
        f"extraction failed on good text: {good_names}"
    )
    assert bad_names == ["zzz-ghost-skill-r4"], (
        f"extraction failed on bad text: {bad_names}"
    )

    assert _resolves(good_names[0], tracked), "control: present skill must stay silent"
    assert not _resolves(bad_names[0], tracked), "control: absent skill must fire"


def test_control_mention_filter_does_not_swallow_a_real_use() -> None:
    """Both-states control for the use-vs-mention filter.

    The filter is the one component that can turn a genuine defect into a false
    green, so it is exercised against BOTH states directly:

    * a USE sentence naming an absent skill must NOT be suppressed;
    * a MENTION sentence naming the same absent skill MUST be suppressed.

    A filter that answered the same way for both would be inert, and the gate
    above would be measuring nothing.
    """
    use = "Run the **ghost** skill (`skills/zzz-ghost-skill-r4/SKILL.md`) with these inputs."
    mention = (
        "This command is self-contained; an earlier revision pointed at "
        "`skills/zzz-ghost-skill-r4/SKILL.md`, which has never existed."
    )

    use_match = SKILL_REF.search(use)
    mention_match = SKILL_REF.search(mention)
    assert use_match is not None and mention_match is not None

    assert not _is_mention(_sentence_around(use, use_match.start(), use_match.end())), (
        "the mention filter suppressed a genuine delegation -- it would hide "
        "exactly the defect this gate exists to catch"
    )
    assert _is_mention(
        _sentence_around(mention, mention_match.start(), mention_match.end())
    ), "the mention filter failed to recognise a retirement sentence"


def test_control_mention_filter_is_sentence_scoped() -> None:
    """A negation in a NEIGHBOURING sentence must not suppress a real use.

    This is the failure mode a paragraph-wide or fixed-character-window filter
    would have: one retirement sentence would silence every delegation near it.
    """
    text = (
        "The old helper does not exist any more. "
        "Run the **ghost** skill (`skills/zzz-ghost-skill-r4/SKILL.md`) with these inputs."
    )
    match = SKILL_REF.search(text)
    assert match is not None
    assert not _is_mention(_sentence_around(text, match.start(), match.end())), (
        "a negation in the PREVIOUS sentence suppressed this delegation; the "
        "mention window is too wide"
    )
