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


def test_fenced_code_inside_a_doc_is_documentation_not_pending_work():
    """REFUTED 2026-07-24 — this assertion used to read the other way round.

    The retired wording was: *"Prose polarity must not over-suppress: a fenced block in a doc is
    code being shown"*, asserting `len(find_stubs(doc, "docs/notes.md")) > 0`. It was an
    assumption, and measurement refuted it. Replaying the live session ledger
    `~/.claude/stub-ledger/5c615def-….ndjson` (53 records) surfaced 20 fires, **20/20 false
    positives**, and **12 of the 20 were markers inside fenced blocks of .md files** — including
    `INPUT-ADDENDUM-live-fires.md:93`, a corpus row reading literally
    `P1  real source file:   # TODO: handle the empty-list case      <- in a .py, outside any
    fence`. Nothing structural separates that row from the fixture below, so "fenced in prose ⇒
    real" cannot be salvaged with a narrower pattern.

    Scope of the new claim: markers count in CODE files. Residual, disclosed inline — a design
    doc whose fenced snippet really is the author's pending work is now missed. Measured true
    positives of that kind so far: 0 of 12. The settling experiment is a labelled sweep of
    prose-origin fires across further sessions; if any turns out real, this rule needs a
    document-level opt-in rather than a pattern tweak.

    The paired assertion below is what keeps this from being a silent disarm: the SAME fenced
    text in a source file must still fire.
    """
    doc = "# Notes\n\nExample:\n\n```python\n# TODO: finish this\n```\n"
    assert stubscan.find_stubs(doc, "docs/notes.md") == []
    assert len(stubscan.find_stubs(doc, "src/notes.py")) > 0


def test_rust_incompleteness_macros_are_flagged_in_source():
    """F003: `todo!()` / `unimplemented!()` are owed work, not prose.

    Measured at 27fb388 BEFORE the `_MACRO_STUB` rule existed:
    `find_stubs("fn validate(u: &User) -> bool {\\n    todo!()\\n}\\n", "src/auth.rs") == []`
    while the `# TODO: implement validation` control fired — so a Write that declared an
    auth-validation body unfinished in the language's own syntax banked NOTHING in the
    ledger and Stop-time reporting had nothing to resurface.

    Paired both-states assertions, so the rule cannot be a silent word-matcher:
      * the macro form fires in a .rs source file,
      * the same construct inside a fenced block of a .md doc stays a MENTION, and
      * a bare identifier / prose use of the word does NOT fire (no `!(` -> no match).
    """
    rust = "fn validate(u: &User) -> bool {\n    todo!()\n}\n"
    assert [m for m, _ln, _s in stubscan.find_stubs(rust, "src/auth.rs")] == ["TODO!"]
    unimpl = 'fn authorize(u: &User) -> bool {\n    unimplemented!("wire it")\n}\n'
    assert [m for m, _ln, _s in stubscan.find_stubs(unimpl, "src/auth.rs")] == [
        "UNIMPLEMENTED!"
    ]

    doc = "# Notes\n\nRust marks a gap like this:\n\n```rust\ntodo!()\n```\n"
    assert stubscan.find_stubs(doc, "docs/notes.md") == []

    # Word-shaped, not macro-shaped -> must stay silent (this is what keeps the rule from
    # degenerating into `_WEAK` and flagging every identifier that contains "todo").
    benign = "let todo_list = build_todo_list();\nfn todo_count() -> usize { 3 }\n"
    assert stubscan.find_stubs(benign, "src/todo.rs") == []


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
