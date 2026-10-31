#!/usr/bin/env python
"""Regression suite for the docs-hygiene dimension of the git-hygiene Stop hook.

THE THREAT MODEL IS USE-VS-MENTION. A documentation-rot detector is the single most
exposed guard on this box to the recorded defect class where a detector fires on prose
that merely DESCRIBES the thing it hunts (a filename in a sentence, a link shown as an
example, a paragraph asserting an absence). The corpus at
`~/.claude/harness-recovery-2026-07-18/FAILURE-REPLAY-CORPUS/use-vs-mention.jsonl`
(also mirrored in-repo -- see the loader) is the canonical record of those fires. This
suite replays it and adds the doclink-specific controls.

TWO detectors are pinned here:
  (1) the doclink polarity of the shared discriminator (hooks/_shared/use_vs_mention.py)
  (2) scan_docs_hygiene end to end -- broken relative links + committed cruft

The KNOWN-POSITIVE CONTROLS are mandatory: a detector trusted to report "no rot" without a
control that proves it can still SEE rot is exactly the failure this program was born from.
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

THIS = Path(__file__).resolve().parent
sys.path.insert(0, str(THIS))
sys.path.insert(0, str(THIS.parent / "_shared"))

import check  # noqa: E402
from use_vs_mention import Context, is_real_occurrence  # noqa: E402


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def _write_doc(root: Path, rel: str, body: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")


def _scan(root: Path, tracked, **cfg_over) -> check.DocsReport:
    cfg = check.Config()
    if cfg_over:
        cfg = dataclasses.replace(cfg, **cfg_over)
    return check.scan_docs_hygiene(root, frozenset(tracked), cfg)


def _doclink(text: str, needle: str, *, file_path: str = "d.md") -> bool:
    i = text.index(needle)
    ctx = Context(tool_name="", file_path=file_path, source="file")
    return is_real_occurrence(text, (i, i + len(needle)), ctx, kind="doclink")


# --------------------------------------------------------------------------------------
# (1) doclink polarity -- the discriminator kind the detector rides
# --------------------------------------------------------------------------------------
class TestDocLinkPolarity:
    """A link in a paragraph is a real USE; the same link shown as an example is a MENTION.
    This is the INVERSE of `marker`, and the inversion is the whole reason doclink exists."""

    def test_link_in_paragraph_is_a_real_use(self):
        body = "See [the plan](docs/plan.md) for details.\n"
        assert _doclink(body, "docs/plan.md") is True

    def test_link_inside_a_fenced_block_is_an_example(self):
        body = "How to link:\n\n```\n[label](docs/plan.md)\n```\n"
        assert _doclink(body, "docs/plan.md") is False

    def test_link_inside_an_inline_code_span_is_an_example(self):
        body = "Write it as `[label](docs/plan.md)` in your file.\n"
        assert _doclink(body, "docs/plan.md") is False

    def test_link_in_a_python_docstring_fence_is_an_example(self):
        # doclink polarity holds in source files too: a fenced example in a .py docstring
        # is being demonstrated, not asserted.
        body = 'x = 1\n"""\n```\n[a](b/c.md)\n```\n"""\n'
        assert _doclink(body, "b/c.md", file_path="mod.py") is False

    def test_negation_does_not_flip_a_doclink(self):
        # Unlike marker, doclink runs no negation test: the phrasing carries no signal.
        body = "This is no longer the [old plan](docs/old.md).\n"
        assert _doclink(body, "docs/old.md") is True


# --------------------------------------------------------------------------------------
# (2) scan_docs_hygiene -- broken relative links
# --------------------------------------------------------------------------------------
class TestBrokenLinks:
    def test_a_link_to_a_missing_sibling_fires(self, tmp_path):
        _write_doc(tmp_path, "docs/a.md", "See [gone](./gone.md).\n")
        r = _scan(tmp_path, {"docs/a.md"})
        assert r.broken_links == 1
        assert r.link_examples == ("docs/a.md -> ./gone.md",)

    def test_a_link_to_a_tracked_sibling_is_silent(self, tmp_path):
        _write_doc(tmp_path, "docs/a.md", "See [b](./b.md).\n")
        _write_doc(tmp_path, "docs/b.md", "hi\n")
        r = _scan(tmp_path, {"docs/a.md", "docs/b.md"})
        assert r.broken_links == 0

    def test_a_link_to_a_tracked_directory_is_silent(self, tmp_path):
        _write_doc(tmp_path, "README.md", "See [guides](guides/).\n")
        r = _scan(tmp_path, {"README.md", "guides/x.md"})
        assert r.broken_links == 0

    def test_an_untracked_but_real_target_is_silent(self, tmp_path):
        # Generated / gitignored output that exists on disk is not rot.
        _write_doc(tmp_path, "d.md", "See [build log](out.txt).\n")
        _write_doc(tmp_path, "out.txt", "generated\n")
        r = _scan(tmp_path, {"d.md"})
        assert r.broken_links == 0

    @pytest.mark.parametrize(
        "target",
        [
            "https://example.com/x.md",
            "http://example.com",
            "//cdn.example.com/x",
            "#section-anchor",
            "/site/absolute.md",
            "mailto:a@b.c",
            "C:/Users/x/note.md",
        ],
    )
    def test_non_relative_targets_are_skipped(self, tmp_path, target):
        _write_doc(tmp_path, "d.md", f"See [x]({target}).\n")
        r = _scan(tmp_path, {"d.md"})
        assert r.broken_links == 0

    @pytest.mark.parametrize(
        "target",
        ["{{cookiecutter.name}}.md", "<placeholder>.md", "$VAR/x.md", "a*.md"],
    )
    def test_templated_targets_are_skipped(self, tmp_path, target):
        _write_doc(tmp_path, "d.md", f"See [x]({target}).\n")
        r = _scan(tmp_path, {"d.md"})
        assert r.broken_links == 0

    def test_anchor_on_a_tracked_file_is_silent(self, tmp_path):
        _write_doc(tmp_path, "a.md", "See [b](b.md#heading).\n")
        _write_doc(tmp_path, "b.md", "# heading\n")
        r = _scan(tmp_path, {"a.md", "b.md"})
        assert r.broken_links == 0

    def test_a_link_shown_as_an_example_does_not_fire(self, tmp_path):
        # THE headline use-vs-mention control: a docs page teaching link syntax with a
        # target that does not exist must stay SILENT.
        _write_doc(
            tmp_path,
            "howto.md",
            "Link like this:\n\n```md\n[label](does/not/exist.md)\n```\n",
        )
        r = _scan(tmp_path, {"howto.md"})
        assert r.broken_links == 0

    def test_parent_relative_escape_is_skipped(self, tmp_path):
        _write_doc(tmp_path, "docs/a.md", "See [x](../../outside.md).\n")
        r = _scan(tmp_path, {"docs/a.md"})
        assert r.broken_links == 0


# --------------------------------------------------------------------------------------
# (2) scan_docs_hygiene -- committed cruft (pure filename, zero prose read)
# --------------------------------------------------------------------------------------
class TestCommittedCruft:
    @pytest.mark.parametrize(
        "name",
        [
            "notes.md.bak",
            "notes.bak-20260713",
            "config.orig",
            "PLAN-OLD.md",
            "design.md.txt",
        ],
    )
    def test_cruft_names_fire(self, tmp_path, name):
        _write_doc(tmp_path, name, "x\n")
        r = _scan(tmp_path, {name})
        assert r.cruft_files == 1

    def test_a_normal_doc_is_not_cruft(self, tmp_path):
        _write_doc(tmp_path, "README.md", "x\n")
        r = _scan(tmp_path, {"README.md"})
        assert r.cruft_files == 0

    def test_cruft_examples_are_sorted_and_capped(self, tmp_path):
        names = {f"f{i}.orig" for i in range(6)}
        for n in names:
            _write_doc(tmp_path, n, "x\n")
        r = _scan(tmp_path, names)
        assert r.cruft_files == 6
        assert list(r.cruft_examples) == sorted(names)[:3]


# --------------------------------------------------------------------------------------
# fail-safe behaviour
# --------------------------------------------------------------------------------------
class TestFailSafe:
    def test_discriminator_unavailable_stands_down_links_not_cruft(
        self, tmp_path, monkeypatch
    ):
        # If the shared module cannot be imported, the LINK half must go silent
        # (judged=False) rather than emit unjudged hits -- but cruft (no prose) still runs.
        monkeypatch.setattr(check, "_load_discriminator", lambda: (None, None))
        _write_doc(tmp_path, "a.md", "See [gone](./gone.md).\n")
        _write_doc(tmp_path, "old.orig", "x\n")
        r = _scan(tmp_path, {"a.md", "old.orig"})
        assert r.judged is False
        assert r.broken_links == 0
        assert r.cruft_files == 1

    def test_truncation_is_declared_when_the_cap_is_hit(self, tmp_path):
        names = set()
        for i in range(5):
            rel = f"d{i}.md"
            _write_doc(tmp_path, rel, "See [gone](./gone.md).\n")
            names.add(rel)
        r = _scan(tmp_path, names, docs_cap=2)
        assert r.truncated is True
        assert r.scanned == 2

    def test_unreadable_file_is_skipped_not_reported(self, tmp_path):
        # A doc named in `tracked` but absent on disk (sparse checkout) is not a broken link.
        r = _scan(tmp_path, {"ghost.md"})
        assert r.broken_links == 0
        assert r.actionable == 0


# --------------------------------------------------------------------------------------
# message integration
# --------------------------------------------------------------------------------------
class TestMessage:
    def test_clean_docs_add_no_line(self):
        docs = check.DocsReport()
        assert check._docs_lines(docs) == []

    def test_broken_link_and_cruft_render(self):
        docs = check.DocsReport(
            broken_links=2,
            cruft_files=1,
            link_examples=("a.md -> b.md",),
            cruft_examples=("x.orig",),
        )
        lines = check._docs_lines(docs)
        assert any("2 doc link(s)" in ln for ln in lines)
        assert any("1 committed backup" in ln for ln in lines)
        assert any("a.md -> b.md" in ln for ln in lines)

    def test_build_message_none_when_everything_clean(self):
        assert check.build_message([], [], check.DocsReport()) is None

    def test_build_message_includes_docs_when_only_docs_dirty(self):
        docs = check.DocsReport(cruft_files=1, cruft_examples=("x.orig",))
        msg = check.build_message([], [], docs)
        assert msg is not None
        assert "GIT-HYGIENE / docs" in msg


# --------------------------------------------------------------------------------------
# THE CORPUS REPLAY -- the recorded use-vs-mention fires
# --------------------------------------------------------------------------------------
def _load_corpus() -> list[dict]:
    """The 20 recorded fires. Prefer the live corpus; fall back to the in-repo copy so CI
    (which has no ~/.claude) still runs the replay. Skip only if neither is present."""
    candidates = [
        Path.home()
        / ".claude"
        / "harness-recovery-2026-07-18"
        / "FAILURE-REPLAY-CORPUS"
        / "use-vs-mention.jsonl",
        THIS.parent / "_shared" / "use-vs-mention-corpus.jsonl",
    ]
    for c in candidates:
        try:
            if c.exists():
                rows = [
                    json.loads(ln)
                    for ln in c.read_text(encoding="utf-8").splitlines()
                    if ln.strip()
                ]
                if rows:
                    return rows
        except OSError:
            continue
    return []


CORPUS = _load_corpus()
_needs_corpus = pytest.mark.skipif(
    not CORPUS, reason="use-vs-mention corpus not present"
)


@_needs_corpus
class TestCorpusReplay:
    """Two independent claims against the same recorded corpus.

    A. The shared discriminator, on every case whose kind it natively owns
       (command / marker), still returns the recorded verdict AFTER the doclink
       addition -- proving the extension did not regress the guard.
    B. The docs-cleaning detector is STRUCTURALLY IMMUNE to the prose-marker fires:
       pointed at a doc whose body is a recorded false-positive text, it emits zero
       broken-link fires (there is no link) -- and it still fires on a real broken link.
    """

    def test_corpus_has_the_expected_shape(self):
        assert len(CORPUS) >= 18
        # the four cases the task calls out by name
        ids = {row["id"] for row in CORPUS}
        assert {
            "STUB-FP-notaplaceholder",
            "STUB-FP-upstream-unimpl",
            "STUB-FP-negated-absence",
            "STUB-TP-control",
        } <= ids

    def test_A_discriminator_covered_cases_still_match(self):
        """Every command/marker case is judged exactly as recorded. This is the
        regression proof for the doclink edit."""
        checked = 0
        for row in CORPUS:
            if row["kind"] not in ("command", "marker"):
                continue
            text, pat = row["text"], row["pattern"]
            i = text.find(pat)
            assert i >= 0, f"{row['id']}: pattern not literally present"
            ctx = Context(
                tool_name=row["ctx"].get("tool_name", ""),
                file_path=row["ctx"].get("file_path", ""),
                source=(
                    "assistant_message"
                    if row["ctx"].get("source") in ("assistant_message", "message_text")
                    and not row["ctx"].get("file_path")
                    else row["ctx"].get("source", "file")
                ),
            )
            got = is_real_occurrence(text, (i, i + len(pat)), ctx, kind=row["kind"])
            want = row["expect"] == "FIRE"
            assert got is want, f"{row['id']}: expected {row['expect']}, got real={got}"
            checked += 1
        assert checked >= 9, f"only replayed {checked} command/marker cases"

    def test_B_docs_detector_silent_on_every_recorded_false_positive(self, tmp_path):
        """The docs detector, run over each SILENT-expected corpus body as a .md doc,
        must emit ZERO broken-link fires. It never does prose-marker matching, so the
        entire stub/placeholder/negated-absence FP class cannot occur in it."""
        fired = []
        for row in CORPUS:
            if row["expect"] != "SILENT":
                continue
            rel = "corpus_case.md"
            _write_doc(tmp_path, rel, row["text"] + "\n")
            r = _scan(tmp_path, {rel})
            if r.broken_links:
                fired.append((row["id"], r.link_examples))
        assert not fired, f"docs detector fired on recorded false positives: {fired}"

    def test_B_positive_control_a_real_broken_link_still_fires(self, tmp_path):
        """The paired positive control: if the detector is silent on the FPs only because
        it is inert, this catches it. A genuine broken link MUST fire."""
        _write_doc(
            tmp_path, "real.md", "A live reference to [a deleted plan](./deleted.md).\n"
        )
        r = _scan(tmp_path, {"real.md"})
        assert r.broken_links == 1
