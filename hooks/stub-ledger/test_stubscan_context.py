"""Both-states tests for context-aware stub scanning (open loop 6f8a224e).

The measured failure: 9 of 9 stub-ledger fires on `platform-redesign-2026-07-19` were prose ABOUT
stubs — a design document describing placeholder detection, and a doc honestly labelled
"Status: DESIGN (not implemented)" — not stubs. A scanner that cannot tell a document from code
reports the documentation of a problem as the problem.

Each test below is paired: the SAME construct must still be flagged in real source and must not be
flagged in prose. A one-directional test cannot distinguish a working discriminator from one that
suppresses everything, which is the more dangerous failure — a silently disarmed guard.
"""

from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent / "_shared"))

import stubscan  # noqa: E402

CODE = (
    "def foo(x):\n"
    "    pass\n"
    "\n"
    "# TODO: handle the edge case\n"
    "def bar():\n"
    '    raise NotImplementedError("later")\n'
    "value = 1  # placeholder until wired\n"
)

DESIGN_DOC = (
    "# Design notes\n"
    "\n"
    "The scanner flags a line containing `# TODO` as unfinished work.\n"
    "A paragraph describing placeholder detection is not itself a placeholder.\n"
    "\n"
    "Status: DESIGN (not implemented)\n"
)


def test_real_code_is_still_flagged_without_a_path():
    """Backward compatibility: omitting `path` must behave exactly as before."""
    assert len(stubscan.find_stubs(CODE)) > 0


def test_real_code_is_still_flagged_with_a_path():
    """The guard must NOT be disarmed — this is the direction that matters most."""
    assert len(stubscan.find_stubs(CODE, "src/foo.py")) > 0


def test_design_doc_false_positives_exist_without_context():
    """Pin the known-broken state, so the fix below is demonstrably doing something."""
    assert len(stubscan.find_stubs(DESIGN_DOC)) > 0, (
        "fixture must reproduce the original false positives or the paired test proves nothing"
    )


def test_design_doc_is_not_flagged_with_context():
    """The 9/9 measured false-positive class."""
    assert stubscan.find_stubs(DESIGN_DOC, "docs/design.md") == []


def test_fenced_code_inside_a_doc_is_still_real():
    """Prose polarity must not over-suppress: a fenced block in a doc is code being shown."""
    doc = "# Notes\n\nExample:\n\n```python\n# TODO: finish this\n```\n"
    assert len(stubscan.find_stubs(doc, "docs/notes.md")) > 0


def test_missing_discriminator_fails_open(monkeypatch=None):
    """A broken import must fall back to the previous behaviour, never to silence."""
    orig = stubscan._discriminator
    try:
        stubscan._discriminator = lambda path: None
        assert len(stubscan.find_stubs(CODE, "src/foo.py")) > 0
        assert len(stubscan.find_stubs(DESIGN_DOC, "docs/design.md")) > 0
    finally:
        stubscan._discriminator = orig


if __name__ == "__main__":
    import traceback

    fns = [
        v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)
    ]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except Exception:
            failed += 1
            print(f"  FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n  {len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
