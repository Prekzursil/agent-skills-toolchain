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
import io

from docs_count_anchors import ROUND5_COUNT_ANCHORS

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
        text = io.open((REPO_ROOT / rel), encoding="utf-8", newline="").read()
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


# --------------------------------------------------------------------------
# Round 5 arm: command-doc PROSE may not assert a repo path that is absent
# --------------------------------------------------------------------------
#
# Measured surface that motivated this arm (docs/_LANE-DOCS-BUILD-R5.md):
#   20 bare ``scripts/...`` references in command docs, 16 of which do not resolve
#   -- AS MEASURED AT COMMIT 67137879, the parent of the fix that motivated this arm.
#   From that fix (5d573583) onward the same probe returns 19 / 15; the delta of 1 IS
#   the reference this arm was written to stop.
#
#   Round-6 correction, recorded rather than deleted: these two lines originally said
#   "20 ... 16" with no anchor, which reads as a CURRENT count and had already gone
#   stale by one when it was committed. That is the exact defect class this file
#   exists to catch, reproduced inside the file that catches it. Both numbers are now
#   pinned to immutable commits and re-derivable:
#       py -3.11 docs/_lane_docs_r6_pinned_counts.py
#       -> SUCCESS:docs-r6-pinned pre_fix=20/16 post_fix=19/15
#   The pinned form is deliberate. A number tied to HEAD moves every time a sibling
#   adds a command doc, and a comment that must be re-edited on every sibling commit
#   is a comment that goes stale again -- so no assertion here is tied to a live count.
#
#   13 of those 16 sit inside fenced code blocks -- they are INVOCATIONS the user
#   runs against the deployed harness, not claims about this repo, and gating them
#   would fire on every vendored command doc. That is the false-positive class that
#   gets a gate switched off within a week.
#   Of the 3 in prose, exactly ONE was a genuine defect. The other two are
#   ``node scripts/orchestrate-worktrees.js plan.json`` (an invocation) and the
#   English phrase "scripts/commands" (not a path at all). Reporting 16, or even 3,
#   would have been an overclaim -- 16x and 3x respectively.
#
# The discriminator is therefore deliberately narrow: a backticked span containing
# NO whitespace is a bare path and reads as an assertion that the path exists; a
# backticked span with spaces is a command line.

#: A single backtick span on one line.
BACKTICK_SPAN = re.compile(r"`([^`\n]+)`")

#: An opening or closing code fence.
FENCE_LINE = re.compile(r"^\s*(?:```|~~~)")

#: A bare repo-relative path under ``scripts/`` that carries a file extension.
#: ``${CLAUDE_PLUGIN_ROOT}/scripts/...`` and ``~/.claude/...`` are excluded by the
#: anchor: they name their resolution root and so assert nothing about this repo.
BARE_REPO_SCRIPT = re.compile(r"^scripts/[A-Za-z0-9._/-]+\.[A-Za-z0-9]+$")

#: Floor for the number of backtick spans examined. A collapsed extractor must
#: fail loudly rather than pass vacuously.
MIN_PROSE_SPANS = 150


def _prose_backtick_spans(text: str) -> list[tuple[int, int, str, int]]:
    """``(abs_start, abs_end, span, lineno)`` for backtick spans OUTSIDE code fences.

    Offsets are absolute into ``text`` so the existing sentence window can be reused.
    ``text`` is split on ``\\n`` only, so a ``\\r`` stays inside its line and the
    offsets remain correct for CRLF bytes.
    """
    spans: list[tuple[int, int, str, int]] = []
    offset = 0
    in_fence = False
    for lineno, line in enumerate(text.split("\n"), 1):
        if FENCE_LINE.match(line):
            in_fence = not in_fence
        elif not in_fence:
            for match in BACKTICK_SPAN.finditer(line):
                spans.append(
                    (
                        offset + match.start(1),
                        offset + match.end(1),
                        match.group(1),
                        lineno,
                    )
                )
        offset += len(line) + 1
    return spans


def _path_resolves(path: str, tracked: frozenset[str]) -> bool:
    return path in tracked or (REPO_ROOT / path).exists()


def _prose_path_claims_in_text(
    text: str, tracked: frozenset[str]
) -> list[tuple[int, str]]:
    """``(lineno, path)`` for every prose assertion of an ABSENT repo path."""
    claims: list[tuple[int, str]] = []
    for start, end, span, lineno in _prose_backtick_spans(text):
        if any(ch.isspace() for ch in span):
            continue  # a command line, not a path assertion
        if not BARE_REPO_SCRIPT.match(span):
            continue
        if _is_mention(_sentence_around(text, start, end)):
            continue
        if not _path_resolves(span, tracked):
            claims.append((lineno, span))
    return claims


def _prose_path_claims(tracked: frozenset[str]) -> list[tuple[str, int, str]]:
    out: list[tuple[str, int, str]] = []
    for rel in _command_docs(tracked):
        text = io.open((REPO_ROOT / rel), encoding="utf-8", newline="").read()
        for lineno, path in _prose_path_claims_in_text(text, tracked):
            out.append((rel, lineno, path))
    return out


def test_prose_span_extraction_is_not_empty(tracked: frozenset[str]) -> None:
    """A collapsed extractor would make the arm below pass while measuring nothing."""
    total = sum(
        len(
            _prose_backtick_spans(
                io.open((REPO_ROOT / rel), encoding="utf-8", newline="").read()
            )
        )
        for rel in _command_docs(tracked)
    )
    assert total >= MIN_PROSE_SPANS, (
        f"only {total} prose backtick spans found across the command docs "
        f"(floor {MIN_PROSE_SPANS}); the extractor has collapsed and this arm "
        "is no longer measuring anything"
    )


def test_no_command_doc_prose_claims_a_missing_repo_path(
    tracked: frozenset[str],
) -> None:
    """Prose must not present a bare ``scripts/...`` path this repo does not ship."""
    claims = _prose_path_claims(tracked)
    assert not claims, (
        "command-doc prose asserts repo paths that do not exist:\n"
        + "\n".join(f"  {doc}:{line} -> {path}" for doc, line, path in claims)
        + "\n\nEither ship the file, or name the root the path actually resolves "
        "against (for example ${CLAUDE_PLUGIN_ROOT}/... or ~/.claude/...) so the "
        "sentence stops asserting that this repo contains it."
    )


def test_control_prose_claim_fires_on_a_missing_path(tracked: frozenset[str]) -> None:
    """H1 predicate discriminates vs H2 predicate always silent."""
    text = "Combine the metrics emitted by `scripts/hooks/zzz-absent-r5.js` for this.\n"
    assert _prose_path_claims_in_text(text, tracked) == [
        (1, "scripts/hooks/zzz-absent-r5.js")
    ], "the arm did not fire on an absent bare repo path"


def test_control_prose_claim_is_silent_on_a_present_path(
    tracked: frozenset[str],
) -> None:
    """H1 predicate discriminates vs H2 predicate always fires."""
    assert _path_resolves("scripts/longrun.ps1", tracked), (
        "precondition: scripts/longrun.ps1 must exist for this control to mean anything"
    )
    text = "Wrap it with `scripts/longrun.ps1` before running.\n"
    assert _prose_path_claims_in_text(text, tracked) == [], (
        "the arm fired on a path that DOES exist"
    )


def test_control_an_invocation_span_is_not_a_path_claim(
    tracked: frozenset[str],
) -> None:
    """The two hypotheses give DIFFERENT answers, which is what makes this a control.

    Same absent file, two spans: bare (a claim) and invoked (a command line). A
    predicate that ignored whitespace would return two hits here rather than one.
    """
    bare = "See `scripts/hooks/zzz-absent-r5.js` for details.\n"
    invoked = "Run `node scripts/hooks/zzz-absent-r5.js --flag` to start.\n"
    assert len(_prose_path_claims_in_text(bare, tracked)) == 1
    assert _prose_path_claims_in_text(invoked, tracked) == [], (
        "an invocation was misread as a path assertion; this is the "
        "false-positive class that gets the gate disabled"
    )


def test_control_fenced_code_is_excluded(tracked: frozenset[str]) -> None:
    """Identical token inside vs outside a fence must give different answers."""
    prose = "See `scripts/hooks/zzz-absent-r5.js` here.\n"
    fenced = "```bash\n`scripts/hooks/zzz-absent-r5.js`\n```\n"
    assert len(_prose_path_claims_in_text(prose, tracked)) == 1
    assert _prose_path_claims_in_text(fenced, tracked) == [], (
        "a fenced code block was scanned as prose"
    )


def test_control_the_arm_is_eol_agnostic(tracked: frozenset[str]) -> None:
    """CRLF bytes must produce the same verdict as LF bytes.

    commands/sessions.md is a 333-CRLF file, so an offset bug that swallowed the
    ``\\r`` would silently change the sentence window on the very doc this arm fixed.
    """
    lf = "See `scripts/hooks/zzz-absent-r5.js` here.\nNext line.\n"
    crlf = lf.replace("\n", "\r\n")
    assert _prose_path_claims_in_text(lf, tracked) == _prose_path_claims_in_text(
        crlf, tracked
    ), "the arm is not EOL-agnostic"


# --------------------------------------------------------------------------
# Round 7 arm: the round-5 surface counts must keep their commit anchors
# --------------------------------------------------------------------------
#
# Round 5 shipped the pair "20 bare refs / 16 unresolved" with no anchor, in two
# files. It had already gone stale by one when it was committed; an audit refuted
# it; round 6 fixed both sentences by pinning each number to the immutable commit
# it was measured at. Nothing yet stopped a later edit from stripping the anchor
# back off -- which is exactly how the defect arrived the first time.
#
# This arm pins the ANCHOR, not the number. Pinning the number would re-create
# the defect, because a count tied to HEAD moves on every sibling commit.
#
# WHY THE EXPECTED SHAS LIVE IN ANOTHER MODULE
# --------------------------------------------
# The first version of this arm held them in a constant HERE -- inside one of the
# files it checks. ``docs/_lane_docs_r7_bothstates.py`` mutated the real file and
# proved that version INERT: stripping the anchor from the carrier also stripped
# it from the constant, so the expectation moved with the thing it was expecting
# and the gate stayed GREEN on a genuinely broken file. A gate whose expected
# value lives inside the artifact under test cannot detect that value's removal.
#
# It is deliberately cheap -- two file reads, no git history walk. That is the
# point: this suite runs in a checkout with fetch-depth 1, where a history walk
# fails closed. Re-deriving the counts themselves DOES need full history, so it
# stays an on-demand probe. Both states are measured in
# docs/_LANE-DOCS-BUILD-R7.md.
#
# SCOPE, stated so the arm is not read as wider than it is: it proves an anchor
# survives in the REGION that states the counts. It does not prove that every
# number in either file is anchored, nor that the anchor names the right commit
# -- the on-demand probe settles that.

#: The module holding the expected SHAs. MUST NOT be a carrier; a control pins it.
ANCHOR_SOURCE = "ci/tests/docs_count_anchors.py"

#: Tracked files that state the round-5 surface counts.
COUNT_CARRIERS = (
    "ci/tests/test_command_doc_promises.py",
    "docs/_LANE-DOCS-BUILD-R5.md",
)


def _carrier_source(rel: str) -> str:
    """Read a carrier with ``newline=""`` so its line endings survive verbatim."""
    return io.open((REPO_ROOT / rel), encoding="utf-8", newline="").read()


def _count_region(rel: str, source: str) -> str:
    """The slice of a carrier that states the round-5 surface counts.

    Scoping to a REGION rather than the whole file is load-bearing: both SHAs
    appear elsewhere in these files (in prose about the correction), so a
    whole-file search would pass even after the count itself lost its anchor.
    """
    lines = source.splitlines()
    if rel.endswith(".md"):
        for line in lines:
            if line.lstrip().startswith("| **R5-5** |"):
                return line
        raise AssertionError(f"{rel}: row R5-5 is gone, and it carried the counts")

    start = None
    for i, line in enumerate(lines):
        if line.lstrip().startswith("# Round 5 arm:"):
            start = i
            break
    if start is None:
        raise AssertionError(f"{rel}: the round-5 banner comment is gone")

    block: list[str] = []
    for line in lines[start:]:
        stripped = line.strip()
        if stripped == "" or stripped.startswith("#"):
            block.append(line)
        else:
            break
    return "\n".join(block)


def _missing_anchors(region: str) -> list[str]:
    return [sha for sha in ROUND5_COUNT_ANCHORS if sha not in region]


def test_round5_counts_keep_their_commit_anchors() -> None:
    """The gate proper: neither carrier may state the counts unanchored."""
    offenders = {}
    for rel in COUNT_CARRIERS:
        missing = _missing_anchors(_count_region(rel, _carrier_source(rel)))
        if missing:
            offenders[rel] = missing
    assert not offenders, (
        "a round-5 surface count lost the commit it was measured at, which is how "
        "it reads as CURRENT and goes stale:\n"
        + "\n".join(
            f"  {rel} -> missing {missing}" for rel, missing in offenders.items()
        )
    )


def test_control_the_expectation_does_not_live_in_a_carrier() -> None:
    """The control that the first version of this arm failed.

    H1: the expectation is independent of the artifact -> stripping an anchor
    from a carrier leaves ROUND5_COUNT_ANCHORS intact and the gate fires.
    H2: the expectation lives in the carrier -> it is stripped too and the gate
    stays green. The two give different answers only if this holds.
    """
    assert ANCHOR_SOURCE not in COUNT_CARRIERS, (
        f"{ANCHOR_SOURCE} became one of the files it is the expectation for; "
        "the gate is now inert -- see docs/_lane_docs_r7_bothstates.py"
    )
    assert ROUND5_COUNT_ANCHORS, "the expectation module declares no anchors"


def test_control_anchor_arm_fires_when_an_anchor_is_stripped() -> None:
    """Every anchor, every carrier: removing it must be detected."""
    for rel in COUNT_CARRIERS:
        source = _carrier_source(rel)
        for sha in ROUND5_COUNT_ANCHORS:
            broken = source.replace(sha, "")
            assert sha in _missing_anchors(_count_region(rel, broken)), (
                f"{rel}: stripping {sha} did not make the arm fire -- it is "
                "reading something other than the region that carries the count"
            )


def test_control_anchor_arm_is_silent_on_the_shipped_text() -> None:
    """The other direction: the arm must not fire on the state we ship."""
    for rel in COUNT_CARRIERS:
        assert _missing_anchors(_count_region(rel, _carrier_source(rel))) == []


def test_control_the_region_is_not_the_whole_file() -> None:
    """A region equal to the whole file would make the check trivially green."""
    rel = "ci/tests/test_command_doc_promises.py"
    source = _carrier_source(rel)
    marker = "WHY THE RESOLVER IS MULTI-ROOT"
    assert marker in source, "precondition: the module docstring still says this"
    assert marker not in _count_region(rel, source), (
        "the extracted region swallowed the module docstring; it is not scoped "
        "to the comment block that carries the counts"
    )


def test_control_anchor_arm_is_eol_agnostic() -> None:
    """A CRLF working tree and an LF blob must produce the same verdict."""
    for rel in COUNT_CARRIERS:
        lf = _carrier_source(rel).replace("\r\n", "\n")
        crlf = lf.replace("\n", "\r\n")
        assert _missing_anchors(_count_region(rel, lf)) == _missing_anchors(
            _count_region(rel, crlf)
        ), f"{rel}: the arm's verdict depends on line endings"


# --------------------------------------------------------------------------
# Round 8 arm: no command doc may add a NEW invocation of a missing script
# --------------------------------------------------------------------------
#
# The round-5 arm above gates PROSE path claims and deliberately excludes fenced
# code, on the reasoning that a fence holds an invocation rather than an
# assertion about this repo. Round 5 then scoped the fenced references out
# entirely -- "13 code-block invocations are out of scope by design".
#
# Round 8 measured that assumption instead of inheriting it
# (``docs/_lane_docs_r8_dead_invocations.py``, three-state control). Of the nine
# unresolved tokens, four resolve under ``~/.claude/...`` at runtime and one
# resolves against the metaswarm plugin root -- so the scoping was RIGHT for
# those. Two do not resolve in ANY root that was searched:
#
#   scripts/claw.js          commands/claw.md:12   "node scripts/claw.js"
#   scripts/harness-audit.js commands/harness-audit.md:17, which then calls it
#                            "the source of truth for scoring and checks"
#
# Those two are genuine dead promises and are ROUTED, not gated red: writing the
# missing tools is not a docs lane's call, and a gate that is red on arrival is
# a gate the next lane deletes. What this arm stops is the class GROWING -- a
# ratchet. A token absent from the baseline fails; the baseline may only shrink.
#
# The arm is repo-only on purpose. Classifying a token as RUNTIME needs
# ``~/.claude``, which does not exist on the CI runner, so a live-root check here
# would answer a different question on every machine. That classification stays
# in the on-demand probe; this gate asks only "does it resolve in this repo".

#: A repo-relative ``scripts/`` path carrying an extension, matched anywhere in a
#: line rather than anchored, because an invocation embeds it (``node scripts/x.js``).
#: Extension-less tokens are excluded for the same reason ``BARE_REPO_SCRIPT``
#: excludes them: round 8 read both of this corpus's (``scripts/commands`` in the
#: English phrase "scripts/commands with their descriptions", and
#: ``scripts/hooks/lib`` inside a block of sample AUDIT OUTPUT) and neither is a
#: path the doc promises.
INVOCATION_SCRIPT = re.compile(r"(?<![\w./$-])(scripts/[A-Za-z0-9._/-]+\.[A-Za-z0-9]+)")

#: Unresolved invocation tokens known at round 8, each with the reason it is
#: tolerated. Measured, not assumed -- see the probe named above.
#: RUNTIME  = absent here, present under a live deploy root.
#: SHORTHAND= resolves against another plugin root; 3 tracked copies in this repo.
#: DEAD     = resolves in no searched root. Routed for an implement-or-retire call.
KNOWN_UNRESOLVED_INVOCATIONS: dict[str, str] = {
    "scripts/lib/tmux-worktree-orchestrator.js": "RUNTIME",
    "scripts/orchestrate-worktrees.js": "RUNTIME",
    "scripts/orchestration-status.js": "RUNTIME",
    "scripts/setup-package-manager.js": "RUNTIME",
    "scripts/beads-fetch-pr-comments.ts": "SHORTHAND",
    "scripts/claw.js": "DEAD",
    "scripts/harness-audit.js": "DEAD",
}

#: Floor for tokens examined. A collapsed extractor must fail loudly, not pass.
MIN_INVOCATION_TOKENS = 7


def _invocation_tokens(text: str) -> set[str]:
    """Every ``scripts/...`` token a command doc invokes or names.

    Inside a fence the whole line is code, so the raw line is scanned. Outside
    one only backtick spans are scanned, so ordinary prose cannot contribute a
    false token. Split on ``\\n`` only, so a ``\\r`` stays inside its line.
    """
    tokens: set[str] = set()
    in_fence = False
    for line in text.split("\n"):
        if FENCE_LINE.match(line):
            in_fence = not in_fence
            continue
        haystack = line if in_fence else " ".join(BACKTICK_SPAN.findall(line))
        tokens.update(INVOCATION_SCRIPT.findall(haystack))
    return tokens


def _doc_root(rel: str) -> str:
    """The root a command doc's relative paths resolve against.

    A vendored plugin ships its own ``scripts/`` beside its ``commands/``, so
    ``tools/editor/metaswarm/.claude/commands/self-reflect.md`` naming
    ``scripts/beads-fetch-pr-comments.ts`` is a CORRECT reference to
    ``tools/editor/metaswarm/scripts/beads-fetch-pr-comments.ts``. Resolving
    every doc against the repo root reported that as a dead promise -- it is the
    root-anchoring error, the same shape as the round-5 substring overclaim.

    Strip the trailing ``commands/<name>.md``, then a trailing ``.claude``.
    ``commands/claw.md`` yields ``""`` -- the repo root -- which is right: a
    top-level command doc really is claiming a repo-root path.
    """
    parts = rel.split("/")[:-1]
    if parts and parts[-1] == "commands":
        parts = parts[:-1]
    if parts and parts[-1] == ".claude":
        parts = parts[:-1]
    return "/".join(parts)


def _resolves_for_doc(token: str, rel: str, tracked: frozenset[str]) -> bool:
    """Resolve against the doc's own root OR the repo root -- both are legitimate.

    Own-root is load-bearing for a vendored plugin, which ships ``scripts/``
    beside its ``commands/``. Repo-root is load-bearing for a mirror such as
    ``agent-self/config/commands/``, which has no ``scripts/`` of its own (0
    tracked paths) and whose relative references are the repo's. Dropping either
    leg reports a live, correct reference as a dead promise; the same multi-root
    reasoning already governs skill resolution in this module.
    """
    root = _doc_root(rel)
    if root and _path_resolves(f"{root}/{token}", tracked):
        return True
    return _path_resolves(token, tracked)


def _unresolved_invocations(tracked: frozenset[str]) -> dict[str, list[str]]:
    """token -> the command docs that invoke it, for tokens absent from this repo.

    Absence is judged against the doc's OWN root, not the repo root.
    """
    found: dict[str, list[str]] = {}
    for rel in _command_docs(tracked):
        for token in _invocation_tokens(_carrier_source(rel)):
            if not _resolves_for_doc(token, rel, tracked):
                found.setdefault(token, []).append(rel)
    return found


def test_no_command_doc_adds_a_new_invocation_of_a_missing_script(
    tracked: frozenset[str],
) -> None:
    """The ratchet: the set of unresolved invocations may shrink, never grow."""
    unresolved = _unresolved_invocations(tracked)
    added = {
        token: sorted(docs)
        for token, docs in unresolved.items()
        if token not in KNOWN_UNRESOLVED_INVOCATIONS
    }
    assert not added, (
        "a command doc now invokes a script that does not exist in this repo:\n"
        + "\n".join(f"  {token} <- {', '.join(docs)}" for token, docs in added.items())
        + "\n\nEither add the script, qualify the reference with the root it "
        "resolves against (the ${CLAUDE_PLUGIN_ROOT}/~ form is not matched here), "
        "or -- if it is genuinely absent everywhere -- classify it in "
        "KNOWN_UNRESOLVED_INVOCATIONS after measuring it with "
        "docs/_lane_docs_r8_dead_invocations.py."
    )


def test_the_unresolved_invocation_baseline_carries_no_paid_debt(
    tracked: frozenset[str],
) -> None:
    """A baseline entry that now resolves is a stale list read as current.

    That is this lane's own defect class, so the baseline is held to it: once a
    script lands in the repo its entry must go, or the list quietly overstates
    the debt forever.
    """
    still_unresolved = _unresolved_invocations(tracked)
    paid = sorted(
        token for token in KNOWN_UNRESOLVED_INVOCATIONS if token not in still_unresolved
    )
    assert not paid, (
        f"these resolve now and must leave KNOWN_UNRESOLVED_INVOCATIONS: {paid}"
    )


def test_control_the_doc_root_resolver_discriminates(tracked: frozenset[str]) -> None:
    """One token, two docs, two roots -> the verdict must differ.

    H1 resolution is relative to the doc's own root -> the vendored metaswarm
    copy resolves and the top-level copy does not.
    H2 everything is judged against the repo root -> both come back unresolved,
    and the vendored copy is reported as a dead promise it is not.

    A resolver that cannot tell these apart manufactured exactly that false
    finding before this control existed.
    """
    token = "scripts/beads-fetch-pr-comments.ts"
    vendored = "tools/editor/metaswarm/.claude/commands/self-reflect.md"
    top_level = "commands/self-reflect.md"
    assert _doc_root(vendored) == "tools/editor/metaswarm"
    assert _doc_root(top_level) == ""
    assert _resolves_for_doc(token, vendored, tracked), (
        "precondition: the vendored plugin ships this script beside its commands"
    )
    assert not _resolves_for_doc(token, top_level, tracked), (
        "precondition: the repo root does not carry scripts/ for this token"
    )


def test_control_invocation_arm_fires_on_a_new_missing_script(
    tracked: frozenset[str],
) -> None:
    """H1 the arm reads the doc -> an injected missing token is NEW and fires.

    H2 it reads something else -> the injection is invisible. Different answers.
    """
    injected = "scripts/zzz-round8-not-a-real-file.js"
    assert not _path_resolves(injected, tracked), "precondition: the token is absent"
    rel = _command_docs(tracked)[0]
    text = _carrier_source(rel) + f"\n\n```bash\nnode {injected}\n```\n"
    assert injected in _invocation_tokens(text)
    assert injected not in KNOWN_UNRESOLVED_INVOCATIONS


def test_control_invocation_arm_is_silent_on_a_resolving_script(
    tracked: frozenset[str],
) -> None:
    """The other direction: a script that DOES exist must not be reported."""
    present = "scripts/longrun.ps1"
    assert _path_resolves(present, tracked), "precondition: the token resolves"
    rel = _command_docs(tracked)[0]
    text = _carrier_source(rel) + f"\n\n```bash\npwsh -File {present}\n```\n"
    assert present in _invocation_tokens(text), "extractor missed a fenced token"
    assert present not in _unresolved_invocations(tracked)


def test_control_invocation_extraction_is_not_empty(tracked: frozenset[str]) -> None:
    """A collapsed extractor would make the ratchet vacuously green."""
    total: set[str] = set()
    for rel in _command_docs(tracked):
        total.update(_invocation_tokens(_carrier_source(rel)))
    assert len(total) >= MIN_INVOCATION_TOKENS, (
        f"only {len(total)} invocation tokens found across the corpus; the "
        "extractor has collapsed and the ratchet is measuring nothing"
    )


def test_control_a_root_qualified_reference_is_not_a_repo_claim() -> None:
    """``${CLAUDE_PLUGIN_ROOT}/scripts/x.js`` names its own root, so it is exempt.

    Without the leading ``$``/``/`` guard the regex would slice the tail out of a
    qualified path and report it as a bare repo claim -- the round-5 defect where
    a substring match produced a 16x overclaim.
    """
    qualified = "```bash\nnode ${CLAUDE_PLUGIN_ROOT}/scripts/qualified-example.js\n```"
    assert _invocation_tokens(qualified) == set()
    bare = "```bash\nnode scripts/qualified-example.js\n```"
    assert _invocation_tokens(bare) == {"scripts/qualified-example.js"}


def test_control_invocation_arm_is_eol_agnostic(tracked: frozenset[str]) -> None:
    """A CRLF working tree and an LF blob must produce the same token set."""
    for rel in _command_docs(tracked)[:12]:
        lf = _carrier_source(rel).replace("\r\n", "\n")
        assert _invocation_tokens(lf) == _invocation_tokens(lf.replace("\n", "\r\n")), (
            f"{rel}: the arm's token set depends on line endings"
        )
