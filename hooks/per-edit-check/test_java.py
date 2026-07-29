#!/usr/bin/env python3
"""Tests for the Java structural check in per-edit-check/check.py.

Regression cover for D-a036: before this suite, a `.java` file left in a state
that cannot compile fell through `_run_check`'s catch-all and the hook exited 0
with no output at all -- while the same shape of breakage in `.py` or `.json`
produced a diagnostic.  The reported fix (run google-java-format / Checkstyle /
javac / Maven / Gradle) is NOT what is implemented and is not what these tests
assert: none of those fit a per-edit hook's 8-second budget, and `javac` on a
single file without the project classpath false-flags any file that imports a
sibling class.  What IS asserted is the always-available structural invariant --
`()`, `[]` and `{}` balance once comments and literals are removed -- reported
as an ADVISORY that can never block an edit.

The bail-out tests are as load-bearing as the detection tests: this is a
heuristic, so every state it cannot resolve unambiguously must stay silent.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent


def load_check():
    """Return a freshly exec'd copy of check.py (bypasses import cache)."""
    spec = importlib.util.spec_from_file_location("check_mod_java", HERE / "check.py")
    assert spec is not None, "check.py not found next to test_java.py"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def run_hook(mod, fp: str) -> tuple[int, str, str]:
    """Invoke mod.main() for an Edit event on *fp*; return (rc, stdout, stderr)."""
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": fp},
        "session_id": "test-sess-java",
    }
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO(json.dumps(payload))
    cap_out, cap_err = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = cap_out, cap_err
    rc = 0
    try:
        with mock.patch.dict(os.environ, {}, clear=False):
            rc = mod.main()
    except SystemExit as exc:
        rc = int(exc.code) if exc.code is not None else 0
    finally:
        sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
    return rc, cap_out.getvalue(), cap_err.getvalue()


def _java(tmp_path: Path, src: str, name: str = "Sample.java") -> str:
    fp = tmp_path / name
    fp.write_text(src, encoding="utf-8")
    return str(fp)


# The exact source from the D-a036 probe.
BROKEN = "public class Broken {\n"

# Exercises every lexical form whose delimiters must NOT be counted:
# a line comment, a block comment, a string, a char literal and a text block.
WELLFORMED = (
    "package com.example;\n"
    "\n"
    "// closing brace in a line comment: }\n"
    "/* opening brace in a block comment: { */\n"
    "public class Sample {\n"
    '    private static final String OPEN = "{";\n'
    "    private static final char CLOSE = '}';\n"
    "    private static final String BLOCK = "
    + '"""\n'
    + "        { not real }\n"
    + '        """;\n'
    "\n"
    "    public java.util.List<String> items() {\n"
    "        return java.util.List.of(OPEN, String.valueOf(CLOSE), BLOCK);\n"
    "    }\n"
    "}\n"
)


# -- detection ----------------------------------------------------------------


def test_unclosed_brace_is_reported(tmp_path: Path):
    """The D-a036 probe file must no longer be silently accepted."""
    mod = load_check()
    issues, is_syntax = mod._run_check(_java(tmp_path, BROKEN, "Broken.java"))
    assert issues, "an unclosed class brace must produce an issue"
    assert is_syntax is False, "the heuristic must stay advisory, never a block"
    assert any("1" in ln for ln in issues), "the report must name the opening line"


def test_stray_closing_brace_is_reported(tmp_path: Path):
    mod = load_check()
    src = "public class Sample {\n}\n}\n"
    issues, is_syntax = mod._run_check(_java(tmp_path, src))
    assert issues, "a closing brace with no opener must produce an issue"
    assert is_syntax is False


def test_unclosed_paren_is_reported(tmp_path: Path):
    mod = load_check()
    src = "public class Sample {\n    void f( {\n    }\n}\n"
    issues, _ = mod._run_check(_java(tmp_path, src))
    assert issues


def test_broken_java_injects_and_never_blocks(tmp_path: Path):
    """End-to-end: a diagnostic is emitted, but the edit is never rejected."""
    mod = load_check()
    rc, out, err = run_hook(mod, _java(tmp_path, BROKEN, "Broken.java"))
    assert rc == 0, "a heuristic must not block an edit (exit 2 is for real parsers)"
    assert err.strip() == "", "advisory output belongs on stdout, not stderr"
    payload = json.loads(out)
    ctx = payload["hookSpecificOutput"]["additionalContext"]
    assert "Broken.java" in ctx


# -- conservative bail-outs (must stay silent) --------------------------------


def test_wellformed_java_is_silent(tmp_path: Path):
    mod = load_check()
    assert mod._run_check(_java(tmp_path, WELLFORMED)) == ([], False)


def test_empty_file_is_silent(tmp_path: Path):
    mod = load_check()
    assert mod._run_check(_java(tmp_path, "")) == ([], False)


def test_unicode_escape_bails_out(tmp_path: Path):
    """Java expands \\uXXXX before lexing, so an escape can BE a delimiter."""
    mod = load_check()
    src = "public class Sample \\u007B\n}\n"
    assert mod._run_check(_java(tmp_path, src)) == ([], False)


def test_unterminated_block_comment_bails_out(tmp_path: Path):
    mod = load_check()
    src = "public class Sample {\n}\n/* never closed\n"
    assert mod._run_check(_java(tmp_path, src)) == ([], False)


def test_unterminated_string_bails_out(tmp_path: Path):
    mod = load_check()
    src = 'public class Sample {\n    String s = "oops;\n}\n'
    assert mod._run_check(_java(tmp_path, src)) == ([], False)


def test_unterminated_text_block_bails_out(tmp_path: Path):
    mod = load_check()
    src = 'public class Sample {\n    String s = """\n    still open\n'
    assert mod._run_check(_java(tmp_path, src)) == ([], False)


def test_escaped_quote_in_literal_does_not_desync(tmp_path: Path):
    mod = load_check()
    src = 'public class Sample {\n    String s = "a\\"{b";\n}\n'
    assert mod._run_check(_java(tmp_path, src)) == ([], False)


def test_wellformed_java_is_silent_end_to_end(tmp_path: Path):
    mod = load_check()
    rc, out, err = run_hook(mod, _java(tmp_path, WELLFORMED))
    assert (rc, out.strip(), err.strip()) == (0, "", "")
