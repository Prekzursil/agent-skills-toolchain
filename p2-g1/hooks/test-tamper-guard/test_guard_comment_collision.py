"""Regression: a PROSE COMMENT must not cancel a real removed assertion.

`_ASSERT_RE` matches broad English words ("assert", "should", "verify", "must"),
and `_analyse_diff` computes `assertion_net_drop = removed - added`. Counting
comment text as an added assertion therefore let one comment neutralise one real
deletion. The exact fixture this guard's own README documents as "should WARN" --

    -    assert 1 + 1 == 2
    +    pass  # assert removed

-- produced NO signal, while the same diff with the word removed from the
comment produced the warning. Only the EXECUTABLE part of a line may count.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
README = HERE / "README.md"


def _load_guard():
    spec = importlib.util.spec_from_file_location(
        "_test_tamper_guard", HERE / "guard.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


GUARD = _load_guard()

README_FIXTURE = (
    "@@ -1,3 +1,3 @@\n"
    " def test_math():\n"
    "-    assert 1 + 1 == 2\n"
    "+    pass  # assert removed\n"
)
# Identical weakening, but the comment carries no assertion word. This one always
# warned, which is what proved the collision (and not a broken detector).
POSITIVE_CONTROL = (
    "@@ -1,3 +1,3 @@\n def test_math():\n-    assert 1 + 1 == 2\n+    pass  # removed\n"
)


def test_readme_fixture_warns():
    """The documented claimed-positive fixture must fire."""
    signals = GUARD._analyse_diff(README_FIXTURE)
    assert "assertion_net_drop" in signals, signals


def test_positive_control_still_warns():
    signals = GUARD._analyse_diff(POSITIVE_CONTROL)
    assert "assertion_net_drop" in signals, signals


def test_readme_documents_this_fixture():
    """Pin the fixture to the README so the two cannot drift apart."""
    text = README.read_text(encoding="utf-8")
    assert "pass  # assert removed" in text


@pytest.mark.parametrize(
    "comment_line",
    [
        "+    pass  # assert removed",
        "+    pass  // expect removed",
        "+    # should verify this later",
        "+    pass  # TODO restore the assertion we must keep",
    ],
)
def test_comment_only_additions_never_offset_a_removal(comment_line):
    diff = "@@ -1,2 +1,2 @@\n-    assert value == 2\n" + comment_line + "\n"
    assert "assertion_net_drop" in GUARD._analyse_diff(diff)


def test_real_replacement_assertion_still_offsets_a_removal():
    """Inverted-fix guard: a genuine swap is NOT a weakening and must stay silent."""
    diff = "@@ -1,2 +1,2 @@\n-    assert value == 2\n+    assert value == 3\n"
    assert "assertion_net_drop" not in GUARD._analyse_diff(diff)


def test_removed_comment_does_not_count_as_a_removed_assertion():
    """Symmetry: deleting a prose comment is not deleting an assertion."""
    diff = "@@ -1,2 +1,1 @@\n-    # we should verify the cache here\n+\n"
    assert "assertion_net_drop" not in GUARD._analyse_diff(diff)


# --- _code_part unit contract ------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("    pass  # assert removed", "    pass  "),
        ("    pass  // expect removed", "    pass  "),
        ("# assert", ""),
        ("    assert x == 1", "    assert x == 1"),
        # A comment marker INSIDE a string literal is not a comment.
        ('    assert tag == "a # b"', '    assert tag == "a # b"'),
        ("    assert url == 'http://x'", "    assert url == 'http://x'"),
        # Escaped quote must not end the string early.
        ('    assert s == "a\\"# b"', '    assert s == "a\\"# b"'),
        # Unterminated quote: keep the whole line rather than guess.
        ('    assert s == "oops # ', '    assert s == "oops # '),
    ],
)
def test_code_part(line, expected):
    assert GUARD._code_part(line) == expected


def test_skip_signals_are_not_comment_stripped():
    """`# type: ignore ... assert` and `TODO ... test` live ONLY inside comments.

    Comment-stripping the skip scan would silently disarm them, so that scan
    deliberately still reads the raw line.
    """
    for pattern in ("# type: ignore[attr] assert", "# TODO drop this test"):
        assert re.search(r"^\s*(#|//)", pattern.strip()) or pattern.startswith("#")
        diff = "@@ -1,1 +1,2 @@\n+    " + pattern + "\n"
        assert "skip_added" in GUARD._analyse_diff(diff), pattern
